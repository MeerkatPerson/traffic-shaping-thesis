import simpy
from typing import Dict
from message import Message


class DefaultMessageReceiver():

    env: simpy.Environment = None

    # event which will be emitted once all streams have finished, so that MessageEmitter can finish and write everything to file.
    completed: simpy.Event = None

    streams_finished: int = None
    # will contain entries of the form {stream_num: status}, where status == 0 if stream is not finished, 1 if it is
    stream_status: Dict[int, int] = None

    num_streams: int = None

    msg_queue_downstream: simpy.resources.store.Store = None

    def __init__(self, env: simpy.Environment, msg_queue_downstream: simpy.resources.store.Store, num_streams: int) -> None:

        self.env = env

        self.completed = env.event()

        # for tracking the number of streams that have finished, to know when we're done
        self.streams_finished = 0

        self.msg_queue_downstream = msg_queue_downstream

        self.num_streams = num_streams

        # we'll track the stream status to be sure no stream appears to finish more than once
        self.stream_status = {key: value for key, value in zip(
            list(map(lambda x: x, list(range(self.num_streams)))), [0]*self.num_streams)}

        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        while True:

            elem: Message = yield self.msg_queue_downstream.get()

            elem.sent = self.env.now

            # check what kind of message we got here
            msg_chunks = elem.content.decode().split('|')
            msg_type = msg_chunks[0]

            # if its a regular RCV message, record and continue
            if msg_type == "RCV":

                pass

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

                    # emit event to notify message receiver
                    self.completed.succeed()

                    break
