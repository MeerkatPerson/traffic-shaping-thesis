import simpy
import numpy
from message import Message


class LoopixMessageEmitter(object):

    network: simpy.resources.store.Store = None
    msg_queue: simpy.resources.store.Store = None
    participant: str = None  # client or server

    def __init__(self, env: simpy.Environment, network: simpy.resources.store.Store, msg_queue: simpy.resources.store.Store, participant: str) -> None:

        self.network = network
        self.msg_queue = msg_queue
        self.participant = participant

        # register 'run' as process
        self.process = env.process(self.run(env))

    def run(self, env: simpy.Environment) -> None:

        while True:

            # sample from an exponential distribution
            emission_interval: float = numpy.random.exponential(1)

            # time at which we will request
            emission_time = env.now + emission_interval

            # sleep for 'emission_interval' amount of time
            yield env.timeout(emission_interval)

            # print(f"[{self.participant}] emitting a message at {env.now}, was scheduled for {emission_time}")

            # check if msg_queue is empty
            if self.msg_queue.items:

                # print(f'[{datetime.now()}] msg qeue NOT empty at {participant}!')

                elem: Message = yield self.msg_queue.get()

                elem.sent = env.now

                # put in shared queue
                # TODO decide if we should put only content (= bytes) or
                # the entire thing, which depends on if we want to track forwarding
                # latency at the sender or destination (currently, it doesn't)
                # really matter as delivery is instant
                yield self.network.put(elem.content)

                print(
                    f"[{self.participant}] sent msg at {env.now} which was created at {elem.created}")

                # append msg info to json, TODO

            # no message available, generate & send a dummy message
            else:

                # print(f'[{datetime.now()}] msg qeue empty at {participant}!')

                dummy = "PADDING|".encode()

                # just append (514-len(dummy)) NULL bytes & send?
                dummy += b'\x00'*(514-len(dummy))

                # append to queue shared between processes
                yield self.network.put(dummy)

                # print(f"[{datetime.now()}] {participant} sent dummy")
