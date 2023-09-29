import simpy
from message import Message, record_emission, write_emissions_to_file, scales_to_str
from typing import Dict, Union
from msg_emitter import MessageEmitter
from globals import CELL_SIZE, MICROSECONDS_PER_SECOND


class ConstantMessageEmitter(MessageEmitter):

    # filename: str = None
    filename_data: str = None
    filename_dummy: str = None
    filename_overall: str = None
    scale: float = None  # 'scale' here simply refers to the median inter-cell delay, which we will statically enforce in this scenario, without any randomness
    emission_interval: float = None

    def __init__(self, env: simpy.Environment, dir: str, network: simpy.resources.store.Store, msg_queue: simpy.resources.store.Store, participant: str, nr: int, run_nr: int, scales: Dict[str, float]) -> None:

        super().__init__(env, dir, network, msg_queue, participant)

        scales_str: str = scales_to_str(scales)

        self.filename_data = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_CONSTANT-{scales_str}_DATA.json'
        self.filename_dummy = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_CONSTANT-{scales_str}_DUMMY.json'
        self.filename_overall = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_CONSTANT-{scales_str}_OVERALL.json'
        self.scale = scales["OVERALL"] if scales["OVERALL"] is not None else scales[participant]
        self.emission_interval = self.scale * MICROSECONDS_PER_SECOND
        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        # write empty dict (we will continuously append to this dict)
        emissions_data: Dict[int, int] = dict()
        emissions_dummy: Dict[int, int] = dict()
        emissions_overall: Dict[int, int] = dict()

        while True:

            try:

                # time at which we will request
                emission_time = self.env.now + self.emission_interval

                # sleep for 'emission_interval' amount of time
                yield self.env.timeout(self.emission_interval)

                # print(f"[{self.participant}] emitting a message at {env.now}, was scheduled for {emission_time}")

                # check if msg_queue is empty
                if self.msg_queue.items:

                    # print(f'[{datetime.now()}] msg qeue NOT empty at {participant}!')

                    elem: Message = yield self.msg_queue.get()

                    elem.sent = self.env.now

                    # write emission information to file
                    record_emission(data=emissions_data, time_=self.env.now)
                    record_emission(data=emissions_overall, time_=self.env.now)

                    # put in shared queue
                    # TODO decide if we should put only content (= bytes) or
                    # the entire thing, which depends on if we want to track forwarding
                    # latency at the sender or destination (currently, it doesn't)
                    # really matter as delivery is instant
                    yield self.network.put(elem.content)

                    # print(
                    #   f"[{self.participant}] sent msg at {self.env.now} which was created at {elem.created}")

                    # append msg info to json, TODO

                # no message available, generate & send a dummy message
                else:

                    # print(f'[{datetime.now()}] msg qeue empty at {participant}!')

                    dummy = "PADDING|".encode()

                    # just append (514-len(dummy)) NULL bytes & send?
                    dummy += b'\x00'*(CELL_SIZE-len(dummy))

                    # write emission information to file
                    record_emission(data=emissions_dummy, time_=self.env.now)
                    record_emission(data=emissions_overall, time_=self.env.now)

                    # append to queue shared between processes
                    yield self.network.put(dummy)

                    # print(f"[{datetime.now()}] {participant} sent dummy")

            except simpy.Interrupt:
                # write emission info to file
                write_emissions_to_file(
                    filename=self.filename_data, data=emissions_data)
                write_emissions_to_file(
                    filename=self.filename_dummy, data=emissions_dummy)
                write_emissions_to_file(
                    filename=self.filename_overall, data=emissions_overall)
                print(
                    f"[{self.participant}] msg emitter CONSTANT has been interrupted, exiting!")
                break
