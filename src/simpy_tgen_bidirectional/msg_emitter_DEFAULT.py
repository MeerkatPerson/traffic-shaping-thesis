import simpy
from message import Message, record_emission, write_emissions_to_file
from typing import Dict
from msg_emitter import MessageEmitter


class DefaultMessageEmitter(MessageEmitter):

    filename: str = None

    def __init__(self, env: simpy.Environment, dir: str, network: simpy.resources.store.Store, msg_queue: simpy.resources.store.Store, participant: str, nr: int, run_nr: int) -> None:

        super().__init__(env, dir, network, msg_queue, participant)

        self.filename = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_DEFAULT.json'

        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        # write empty dict (we will continuously append to this dict)
        data: Dict[str, int] = dict()

        while True:

            try:

                elem: Message = yield self.msg_queue.get()

                elem.sent = self.env.now

                # write emission information to file
                record_emission(data=data, time_=self.env.now)

                # put in shared queue
                # TODO decide if we should put only content (= bytes) or
                # the entire thing, which depends on if we want to track forwarding
                # latency at the sender or destination (currently, it doesn't)
                # really matter as delivery is instant
                yield self.network.put(elem.content)

                # print(
                #    f"[{self.participant}] sent msg at {self.env.now} which was created at {elem.created}")

            except simpy.Interrupt:
                # write file
                write_emissions_to_file(filename=self.filename, data=data)

                print(
                    f"[{self.participant}] msg emitter DEFAULT has been interrupted, exiting!")
                break
