import subprocess
import os
import simpy
import numpy
from stream_generator import StreamGenerator
from parse_tgen_traffic import parse_tgen_traffic
from typing import Union, Dict

if __name__ == "__main__":

    # set a seed for reproducibility in seeding our APE- as well as Loopix-message-emitters' rngs
    seed = 689941

    rng: numpy.random.Generator = numpy.random.default_rng(seed)

    # the top level directory, i.e. two levels up from this file's dir (we're in top_level_dir/src/simpy here)
    p = os.path.dirname(os.path.dirname(os.getcwd()))

    print(f"Two dirs up, supposedly: {p}")

    # now get to the results directory from there
    results_dir = os.path.join(p, 'results')

    # make a dir to identify this experiment
    experiment_id = "LOOPIX_bidirectional"

    experiment_dir = os.path.join(
        results_dir, experiment_id)

    num_fails = 0

    # in total, there'll be 500 runs
    for run_nr in range(500):

        # make a dir which will contain this run's results
        subprocess.run([f'mkdir run-{run_nr}'], shell=True, cwd=experiment_dir)

        # Let's compare:
        # (I.) each of client and server gets their own scale param based on these exact values;
        # (II.) we're doing a one-size-fits-all value for both that's in the middle: 13/2 = 6.5, i.e., one cell every 1/6.5 seconds
        # (III.) ... more?

        scale_vals = [0.0400, 0.0417, 0.0436, 0.0456, 0.0479, 0.0503, 0.0531, 0.0562, 0.0596, 0.0635, 0.0679, 0.0730,
                      0.0789, 0.0859, 0.0942, 0.1043, 0.1169, 0.1328, 0.1538, 0.1827, 0.2250, 0.2927, 0.4186, 0.7347, 3.0]

        scenario_tuples = [("DEFAULT", None)] + list(zip(["LOOPIX"] *
                                                         len(scale_vals) + ["CONSTANT"]*len(scale_vals), scale_vals*2))

        for scenario_tuple in scenario_tuples:

            scenario_str = scenario_tuple[0]

            scale_val = scenario_tuple[1]

            scales = {"CLIENT": None, "SERVER": None, "OVERALL": scale_val}

            env: simpy.Environment = simpy.Environment()

            # 8 client-server pairs per run
            for nr in [1, 2, 3, 4, 5, 6, 7, 8]:

                # parse our traffic model from the tgen stdout logs
                data_dict = parse_tgen_traffic(
                    dir=f"tgen-traces/run-{run_nr}", num=nr)

                if data_dict == None:

                    num_fails += 1

                    continue

                # poll a seed from our rng to pass on to the LOOPIX- as well as APE-message emitter
                sim_seed: int = rng.integers(0, 2**32 - 1)

                sim_seed: Union[None,
                                int] = None if scenario_str in ["DEFAULT", "CONSTANT"] else sim_seed

                # stream generator (= Flow) is our main coordinator process; it creates and starts the message emitters as well as receivers on the client/server side and also starts streams
                stream_generator: StreamGenerator(
                    env=env, tmodel=data_dict["streams"], dir=experiment_id, nr=nr, run_nr=run_nr, msg_emitter_type=scenario_str, scales=scales, seed=sim_seed)

            # run until all processes have finished
            env.run()

    print(f"Number of fails: {num_fails}")
