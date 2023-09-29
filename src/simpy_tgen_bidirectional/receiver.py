import simpy
from typing import Dict, Union


class Receiver(object):

    env: simpy.Environment = None
    # network will be 'network_outward' or 'network_inward' depending on whether this is the server- or client-side receiver
    network: simpy.resources.store.Store = None
    # role = 'client' resp. 'server'
    participant: str = None

    # event which will be emitted once all streams have finished, so that stream_generator can interrupt the message_emitters and thus end the simulation
    completed: simpy.Event = None

    # the number of streams constituting the presently simulated flow
    num_streams: int = None
    # will contain entries of the form {stream_num: status}, where status == 0 if stream is not finished, 1 if it is
    stream_status: Dict[int, int] = None
    streams_completed: int = None

    def __init__(self, env: simpy.Environment, network: simpy.resources.store.Store, participant: str, num_streams: int) -> None:
        self.env = env
        self.network = network
        self.participant = participant
        self.num_streams = num_streams

        # we'll track the stream status to be sure no stream appears to finish more than once
        self.stream_status = {key: value for key, value in zip(
            list(map(lambda x: x, list(range(self.num_streams)))), [0]*self.num_streams)}
        self.streams_completed = 0
        self.completed = env.event()

       # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        while True:

            # fetch incoming data
            msg = yield self.network.get()

            msg_decoded = msg.decode()

            # reconstruct the 'cell'/'message' from received bytestream
            # and respond appropriately (do nothing if msg starts with PADDING,
            # and send data if it starts with a web address)
            msg_chunks = msg_decoded.split('|')

            msg_type = msg_chunks[0]

            if msg_type == "PADDING":

                # print(f"[{env.now}] {self.participant} received dummy")
                pass

            elif msg_type == "DATA":

                stream_nr: int = msg_chunks[1]
                cell_nr: int = int(msg_chunks[2])

                # print(
                #   f"[{self.env.now}] {self.participant} received data from stream with id {stream_nr}, cell number {cell_nr}")

            elif msg_type == "END":

                stream_nr: int = int(msg_chunks[1])

                if self.stream_status[stream_nr] == 1:
                    print(
                        "Something went wrong, END cell received on a stream that was supposed to already have finished!!")
                    exit
                self.stream_status[stream_nr] = 1
                self.streams_completed += 1

                print(
                    f"[{self.participant}] stream with id {stream_nr} has completed on the receiving end! Completed {self.streams_completed}/{self.num_streams} streams.")

                if self.streams_completed == self.num_streams:
                    print(f"[{self.participant}] receiver is finished!")
                    self.completed.succeed()
                    break

            else:

                print(
                    f"[{self.env.now}] {self.participant} received unknown msg type")
