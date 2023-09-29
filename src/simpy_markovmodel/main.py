import simpy
import numpy
from receiver import Receiver
from msg_emitter_default import DefaultMessageEmitter
from markov_model import *
from flow_generator import FlowGenerator
import subprocess
import os
from globals import MICROSECONDS_TWO_HOURS

if __name__ == "__main__":

    seed = 3567987

    rng: numpy.random.Generator = numpy.random.default_rng(seed)

    # the top level directory, i.e. two levels up from this file's dir (we're in top_level_dir/src/simpy here)
    p = os.path.dirname(os.path.dirname(os.getcwd()))

    print(f"Two dirs up, supposedly: {p}")

    # now get to the results directory from there
    results_dir = os.path.join(p, 'results')

    # make a dir to identify this experiment
    experiment_id = "verify-markov"

    subprocess.run([f'mkdir {experiment_id}'], shell=True,
                   cwd=results_dir)

    experiment_dir = os.path.join(
        results_dir, experiment_id)

    # 125 runs
    for run_nr in range(126):

        # make a dir which will contain this run's results
        subprocess.run([f'mkdir run-{run_nr}'], shell=True,
                       cwd=experiment_dir)

        env: simpy.Environment = simpy.Environment()

        # 8 client - server pairs at a time
        for part_nr in range(9):

            # we need 4 shared data stores:
            # (1) the queue representing the client -> server link (network_outward), shared between client and server
            network_outward: simpy.resources.store.Store = simpy.Store(env)

            # (2) the queue representing the server -> client link (network_inward), shared between client and server
            network_inward: simpy.resources.store.Store = simpy.Store(env)

            # (3) the msg queue at the client side (shared between client and client-side msg emitter)
            msg_queue_client: simpy.resources.store.Store = simpy.Store(env)

            # (4) the msg queue at the server side (shared between server and server-side msg emitter)
            msg_queue_server: simpy.resources.store.Store = simpy.Store(env)

            # we need: 2 receiver processes; 2 message emitter processes
            client_receiver: Receiver = Receiver(
                env, network=network_inward, participant="CLIENT")

            server_receiver: Receiver = Receiver(
                env, network=network_outward, participant="SERVER")

            client_msg_emitter: DefaultMessageEmitter = DefaultMessageEmitter(
                env, network=network_outward, msg_queue=msg_queue_client, participant="CLIENT")

            server_msg_emitter: DefaultMessageEmitter = DefaultMessageEmitter(
                env, network=network_inward, msg_queue=msg_queue_server, participant="SERVER")

            sim_seed: int = rng.integers(0, 2**32 - 1)

            # and then we also need our flow generator
            # firstly, generate a Markov Model to be usedby our flow generator
            # seed taken from the 'traffic'-action opts in tgenrc.graphml
            flow_mmodel: MarkovModel = MarkovModel(
                path="../../config/graphml/tgen.tor-flowmodel-300000000usec.graphml", startVertex_id="s0", seed=sim_seed)

            flow_generator: FlowGenerator(
                mmodel=flow_mmodel, env=env, run_nr=run_nr, part_nr=part_nr, msg_queue_client=msg_queue_client, msg_queue_server=msg_queue_server)

        # run for two hours (unit is microseconds)
        env.run(until=MICROSECONDS_TWO_HOURS)
