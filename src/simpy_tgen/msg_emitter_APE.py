import simpy
from numpy.random import default_rng, Generator, randint
from message import Message, record_emission, write_emissions_to_file
from typing import Callable, Tuple, Union
from typing import Dict
from msg_emitter import MessageEmitter
from globals import CELL_SIZE
from APE_state_machine import APEStateMachine


class APEMessageEmitter(MessageEmitter):

    # filename: str = None
    filename_data: str = None
    filename_dummy: str = None
    filename_overall: str = None
    seed: int = None
    rng: Generator = None

    # unlike the other message emitters, the APE message emitter also consumes data received from the communication partner (i.e., from the downstream link). The upstream link is the link from the application to the network, i.e., from the upstream linke we receive data that we ourself generate and send to the communication partner
    msg_queue_downstream: simpy.resources.store.Store = None

    def __init__(self, env: simpy.Environment, dir: str,  msg_queue_downstream: simpy.resources.store.Store, msg_queue_upstream: simpy.resources.store.Store, participant: str, num_streams: int, nr: int, run_nr: int, seed: int) -> None:

        super().__init__(env, dir, msg_queue_upstream, participant, num_streams)

        self.filename_data = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_APE_DATA.json'

        self.filename_dummy = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_APE_DUMMY.json'

        self.filename_overall = f'../../results/{dir}/run-{run_nr}/{self.participant}{nr}_APE_OVERALL.json'

        self.seed = seed

        self.rng = default_rng(self.seed)

        self.msg_queue_downstream = msg_queue_downstream

        self.action = self.env.process(self.run())

    def makeDist(self, mean: float, stddev: float, exitProbability: float, order: float) -> Callable[[], Tuple[float, bool]]:

        # [Comment taken from Tobias Pulls on https://github.com/pylls/basket2/blob/master/padding_ape.go] "firstly, reduce the mean by up to 50%, increasing padding: we do not want to increase the mean since this shifts the distribution towards being easier to distinguish (see WTF-PAD paper)"
        while True:

            f: float = self.rng.random()

            if f < 0.5:
                mean *= (1.0 - f)
                break

        # [Comment taken from Tobias Pulls on https://github.com/pylls/basket2/blob/master/padding_ape.go] "randomize stddev, exitProbability and order (because why not?)"
        def vary(d: float, value: float) -> float:

            while True:

                f: float = self.rng.random()

                if f < d:
                    return value * (1.0 + f)

                if f > 1-d:
                    return value*f

        stddev = vary(0.25, stddev)
        exitProbability = vary(0.1, exitProbability)
        order = vary(0.5, order)

        # [Comment taken from Tobias Pulls on https://github.com/pylls/basket2/blob/master/padding_ape.go] "// create our lognormal distribution that returns a timer or a flag indicating that the adaptive padding should change state (ininity bin in WTF-PAD)"
        def ret() -> Tuple[Union[float, None], bool]:

            if exitProbability > self.rng.random():
                return None, True

            return (self.rng.lognormal(mean, stddev))*order, False

        return ret

    def run(self) -> None:

        # write empty dicts (the send- and rcv state machines will append to these as appropriate)
        emissions_data: Dict[int, int] = dict()
        emissions_dummy: Dict[int, int] = dict()
        emissions_overall: Dict[int, int] = dict()

        # firstly, generate our probability distributions
        send_machine: APEStateMachine = None
        rcv_machine: APEStateMachine = None

        if self.participant == "CLIENT":

            # client uses the same burst- and gap-histograms for the send- and receive-machines
            hist_burst = self.makeDist(
                mean=2.5, stddev=0.8, exitProbability=0.65, order=1000.0)
            hist_gap = self.makeDist(
                mean=0.25, stddev=0.5, exitProbability=0.45, order=1000.0)

            send_machine = APEStateMachine(env=self.env, kind="send", participant=self.participant, hist_burst=hist_burst, hist_gap=hist_gap, msg_queue=self.msg_queue,
                                           num_streams=self.num_streams, emissions_dummy=emissions_dummy, emissions_overall=emissions_overall, emissions_data=emissions_data)

            rcv_machine = APEStateMachine(env=self.env, kind="rcv", participant=self.participant, hist_burst=hist_burst, hist_gap=hist_gap, msg_queue=self.msg_queue_downstream,
                                          num_streams=self.num_streams, emissions_dummy=emissions_dummy, emissions_overall=emissions_overall, emissions_data=None)

            # init & start the two machines

        elif self.participant == "SERVER":

            # server uses the same gap-, but different burst histograms for the send- and receive machines
            hist_burst_send = self.makeDist(
                mean=0.25, stddev=0.5, exitProbability=0.5, order=20*1000.0)
            hist_burst_rcv = self.makeDist(
                mean=0.05, stddev=0.4, exitProbability=0.5, order=1000.0)
            hist_gap = self.makeDist(
                mean=0.25, stddev=0.8, exitProbability=0.3, order=100.0)

            # init & start the two machines
            send_machine = APEStateMachine(env=self.env, kind="send", participant=self.participant, hist_burst=hist_burst_send, hist_gap=hist_gap, msg_queue=self.msg_queue,
                                           num_streams=self.num_streams, emissions_dummy=emissions_dummy, emissions_overall=emissions_overall, emissions_data=emissions_data)

            rcv_machine = APEStateMachine(env=self.env, kind="rcv", participant=self.participant, hist_burst=hist_burst_rcv, hist_gap=hist_gap, msg_queue=self.msg_queue_downstream,
                                          num_streams=self.num_streams, emissions_dummy=emissions_dummy, emissions_overall=emissions_overall, emissions_data=None)

        # wait for the state machines to finish; they will emit a 'completed' event once they have received an 'END'-cell for each stream.

        yield self.env.all_of([send_machine.completed, rcv_machine.completed])

        write_emissions_to_file(
            filename=self.filename_dummy, data=emissions_dummy)
        write_emissions_to_file(
            filename=self.filename_data, data=emissions_data)
        write_emissions_to_file(
            filename=self.filename_overall, data=emissions_overall, end_time=self.env.now)
