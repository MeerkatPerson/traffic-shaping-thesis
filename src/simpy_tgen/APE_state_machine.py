
import simpy
from message import Message, record_emission, write_emissions_to_file
from typing import Callable, Tuple, Union
from typing import Dict
from globals import CELL_SIZE


class APEStateMachine(object):

    env: simpy.Environment = None
    # 'send' (reacting to upstream data arrival) vs 'rcv' (reacting to downstream data arrival)
    kind: str = None
    participant: str = None
    hist_burst: Callable[[], Tuple[float, bool]] = None
    hist_gap: Callable[[], Tuple[float, bool]] = None
    msg_queue: simpy.resources.store.Store
    num_streams: int
    streams_finished: int = None  # how many out of 'num_streams' are finished?
    # will contain entries of the form {stream_num: status}, where status == 0 if stream is not finished, 1 if it is
    stream_status: Dict[int, int] = None
    state: str = None  # state of the padding machine, one of "WAIT", "BURST", "GAP" - TODO enum type would be more elegant, but doesn't really matter for now
    # dicts for recording emissions of the different types; the recv machine will only record dummy emissions, so it only requires the 'emissions_dummy' and 'emissions_overall' dicts, whereas the send machine also records actual data emissions and thus additionally requires the 'emissions_data' dict.
    emissions_data: Dict[int, int] = None
    emissions_dummy: Dict[int, int] = None
    emissions_overall: Dict[int, int] = None

    # event which will be emitted once all streams have finished, so that stream_generator can interrupt the message_emitters and thus end the simulation
    completed: simpy.Event = None

    def __init__(self, env: simpy.Environment, kind: str, participant: str, hist_burst: Callable[[], Tuple[float, bool]], hist_gap: Callable[[], Tuple[float, bool]], msg_queue: simpy.resources.store.Store, num_streams: int, emissions_dummy: Dict[int, int], emissions_overall: Dict[int, int], emissions_data: Dict[int, int] = None) -> None:

        self.env = env
        self.kind = kind
        self.participant = participant
        self.hist_burst = hist_burst
        self.hist_gap = hist_gap
        self.msg_queue = msg_queue
        self.num_streams = num_streams
        self.emissions_dummy = emissions_dummy
        self.emissions_data = emissions_data
        self.emissions_overall = emissions_overall

        # for tracking the number of streams that have finished, to know when we're done
        self.streams_finished = 0

        # we'll track the stream status to be sure no stream appears to finish more than once
        self.stream_status = {key: value for key, value in zip(
            list(map(lambda x: x, list(range(self.num_streams)))), [0]*self.num_streams)}

        self.state = "WAIT"

        self.completed = env.event()

        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        # initialize the timeout duration as some super large value so we can be sure the entire process will start once we have received the first piece of data (and not because of timeout expiry)
        interval: int = 2**32 - 1

        # to decide: in the beginning, do we initialize a timer expiring instantly, or do we wait for data to arrive and begin the whole state machine once a piece of data has arrived? [In case of the latter, initialize interval to some very large number, possibly +INF if available?]

        while True:

            with self.msg_queue.get() as get:

                if get in (yield get | self.env.timeout(interval)):

                    # print(f"[{self.participant}] DATA event triggered")

                    # handle data arrival
                    self.state = "BURST"

                    # log message emission and handle stream completion if applicable, if it isn't just an internal dummy
                    if not (get.value.content == "0xcafebabe"):
                        # print(
                        #    f"[{self.participant}] DATA event triggered by actual msg")

                        # check what kind of message we got here
                        msg_chunks = get.value.content.decode().split('|')
                        msg_type = msg_chunks[0]

                        # if its a regular message, record and continue
                        if msg_type == "DATA":

                            # write emission information to dict
                            record_emission(data=self.emissions_data,
                                            time_=self.env.now)
                            record_emission(
                                data=self.emissions_overall, time_=self.env.now)

                        elif msg_type == "END":

                            stream_nr: int = int(msg_chunks[1])

                            if self.stream_status[stream_nr] == 1:
                                print(
                                    "Something went wrong, END cell received on a stream that was supposed to already have finished!!")
                                exit

                            self.stream_status[stream_nr] = 1
                            self.streams_finished += 1

                            # all streams have finished, write files and shut down
                            if self.streams_finished == self.num_streams:

                                print(
                                    f"[{self.participant}] state machine {self.kind} is finished!")

                                self.completed.succeed()

                                break

                        elif msg_type == "RCV":

                            pass
                            # print(
                            #     f"[{self.participant}] Received upstream data!")

                        else:

                            print(
                                f"[{self.participant}] Unknown message type!")

                    else:
                        # print(
                        #    f"[{self.participant}] DATA event triggered by internal dummy")
                        pass

                    sampled_time, transition_decision = self.hist_burst()

                    if transition_decision:
                        # print(
                        #    f"[{self.participant}] Transitioning from BURST to WAIT because hist_burst delivered state transition decision")
                        self.state == "WAIT"
                        interval = 2**32 - 1
                    else:
                        interval = sampled_time

                else:

                    # handle timer expiry
                    # print(
                    #    f"[{self.participant}] TIMER EXPIRY event triggered")

                    if self.state == "BURST":
                        # print(
                        #    f"[{self.participant}] Transitioning from BURST to GAP due to TIMER EXPIRY")
                        self.state = "GAP"
                        interval = 0
                    elif self.state == "GAP":
                        # print(
                        #    f"[{self.participant}] Emitting a DUMMY due to TIMER EXPIRY in GAP mode")
                        # emit a dummy
                        dummy = "PADDING|".encode()
                        # just append (514-len(dummy)) NULL bytes & send?
                        dummy += b'\x00'*(CELL_SIZE-len(dummy))
                        # write emission information to file
                        record_emission(data=self.emissions_overall,
                                        time_=self.env.now)
                        record_emission(data=self.emissions_dummy,
                                        time_=self.env.now)

                        sampled_time, transition_decision = self.hist_gap()

                        if transition_decision:
                            self.state = "BURST"
                            # print(
                            #    f"[{self.participant}] Transitioning from GAP to BURST because hist_gap delivered state transition decision")
                            # put an 'internal dummy' into msg_queue??
                            self.msg_queue.put(
                                Message(content="0xcafebabe", env=self.env))
                            interval = 2**32 - 1
                        else:
                            interval = sampled_time

                    else:
                        pass
