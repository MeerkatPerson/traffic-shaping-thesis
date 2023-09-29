import simpy
from message import Message
import json
from typing import Dict
from globals import TGEN_MMODEL_MICROS_AT_ONCE, PAYLOAD_LEN
import math
from os.path import exists


class DefaultMessageEmitter(object):

    network: simpy.resources.store.Store = None
    msg_queue: simpy.resources.store.Store = None
    participant: str = None  # client or server
    # filename: str = None

    def __init__(self, env: simpy.Environment, network: simpy.resources.store.Store, msg_queue: simpy.resources.store.Store, participant: str) -> None:

        self.network = network
        self.msg_queue = msg_queue
        self.participant = participant
        # self.filename = f'results/{self.participant}_data.json'

        # register 'run' as process
        self.process = env.process(self.run(env))

    def run(self, env: simpy.Environment) -> None:

        # write empty dict (we will continuously append to this dict)
        # data: Dict[str, int] = dict()

        while True:

            elem: Message = yield self.msg_queue.get()

            elem.sent = env.now

            # put in shared queue
            # TODO decide if we should put only content (= bytes) or
            # the entire thing, which depends on if we want to track forwarding
            # latency at the sender or destination (currently, it doesn't)
            # really matter as delivery is instant
            yield self.network.put(elem.content)

            # print(
            #    f"[{self.participant}] sent msg at {env.now} which was created at {elem.created}")

            # tgen only flushes bytes every 10000 microseconds. So we also aggregate how many bytes we wrote per 10000 microsecond interval.
            # interval: int = math.ceil(env.now/TGEN_MMODEL_MICROS_AT_ONCE)

            """
            # this will be true unless we are right at the start
            if exists(self.filename):
                # load our data
                with open(self.filename) as f:
                    data = json.load(f)

            # add data point
            if str(interval) in data:
                # TODO only count payload as sent data?
                print("Interval exists, incrementing!")
                data[str(interval)] += PAYLOAD_LEN
            else:
                data.update({interval: PAYLOAD_LEN})

            # write back to file
            with open(self.filename, "w") as f:
                json.dump(data, f)
            """
