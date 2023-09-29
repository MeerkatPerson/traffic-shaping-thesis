import simpy
from message import Message, record_emission, write_emissions_to_file
from typing import Dict
from msg_emitter import MessageEmitter
from msg_receiver_DEFAULT_INCL_DOWNSTREAM import DefaultMessageReceiver


class DefaultMessageEmitter(MessageEmitter):

    filename: str = None

    streams_finished: int = None
    # will contain entries of the form {stream_num: status}, where status == 0 if stream is not finished, 1 if it is
    stream_status: Dict[int, int] = None

    msg_queue_downstream: simpy.resources.store.Store = None

    def __init__(self, env: simpy.Environment, dir: str, msg_queue_downstream: simpy.resources.store.Store, msg_queue_upstream: simpy.resources.store.Store, participant: str, num_streams: int, nr: int, run_nr: int) -> None:

        super().__init__(env, dir, msg_queue_upstream, participant, num_streams)

        # for tracking the number of streams that have finished, to know when we're done
        self.streams_finished = 0

        self.msg_queue_downstream = msg_queue_downstream

        # we'll track the stream status to be sure no stream appears to finish more than once
        self.stream_status = {key: value for key, value in zip(
            list(map(lambda x: x, list(range(self.num_streams)))), [0]*self.num_streams)}

        self.filename = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_DEFAULT.json'

        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        # write empty dict (we will continuously append to this dict)
        data: Dict[str, int] = dict()

        # if self.msg_queue_downstream != None, start a receiver process aswell
        receiver: DefaultMessageReceiver = None

        if self.msg_queue_downstream != None:

            receiver = DefaultMessageReceiver(
                env=self.env, msg_queue_downstream=self.msg_queue_downstream, num_streams=self.num_streams)

        while True:

            elem: Message = yield self.msg_queue.get()

            elem.sent = self.env.now

            # check what kind of message we got here
            msg_chunks = elem.content.decode().split('|')
            msg_type = msg_chunks[0]

            # if its a regular message, record and continue
            if msg_type == "DATA":

                # write emission information to dict
                record_emission(data=data,
                                time_=self.env.now)

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

                    # if we have a receiver that is not None, wait for it to finish
                    if receiver != None:

                        yield receiver.completed

                    # write data to file
                    write_emissions_to_file(
                        filename=self.filename, data=data, end_time=self.env.now)

                    print(
                        f"[{self.participant}] msg emitter DEFAULT is finished, exiting!")
                    break
