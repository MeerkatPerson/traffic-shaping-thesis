from markov_model import *
import simpy
from stream_generator import StreamGenerator


class FlowGenerator(object):

    mmodel: MarkovModel = None

    env: simpy.Environment = None
    run_nr: int = None
    part_nr: int = None

    msg_queue_client: simpy.resources.store.Store = None
    msg_queue_server: simpy.resources.store.Store = None
    flows_created: int = None

    def __init__(self, mmodel: MarkovModel, env: simpy.Environment, run_nr: int, part_nr: int, msg_queue_client: simpy.resources.store.Store, msg_queue_server: simpy.resources.store.Store) -> None:
        self.mmodel = mmodel
        self.env = env
        self.run_nr = run_nr
        self.part_nr = part_nr
        self.msg_queue_client = msg_queue_client
        self.msg_queue_server = msg_queue_server
        self.flows_created = 0
        # register 'run' as process
        self.process = env.process(self.run())

    def run(self) -> None:

        while True:

            # grab the next observation from markov model
            delay_microseconds, obs_type = self.mmodel.getNextObservation()

            if obs_type == "OBSERVATION_TO_ORIGIN" or obs_type == "OBSERVATION_TO_SERVER":

                stream_mmodel: MarkovModel = MarkovModel(
                    path="../../config/graphml/tgen.tor-streammodel-ccs2018.graphml", startVertex_id="s0")

                stream_generator: StreamGenerator = StreamGenerator(
                    env=self.env, run_nr=self.run_nr, part_nr=self.part_nr, mmodel=stream_mmodel, msg_queue_client=self.msg_queue_client, msg_queue_server=self.msg_queue_server, id=self.flows_created)

                print(f"Created a new flow with id={self.flows_created}.")

                self.flows_created += 1

                # sleep for 'delay_microseconds' microseconds
                yield self.env.timeout(delay_microseconds)

            else:

                # we reached the end state; exit
                print("Flow generator has reached end state, starting again.")

                # set the current vertex id back to start.
                self.mmodel.currVertex_id = "s0"
