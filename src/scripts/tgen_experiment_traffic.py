import subprocess
from numpy.random import default_rng, Generator
from typing import Dict
import json

# We re-use the same tornet for each experiment, since the network remains abstract.

# 500 times (times 8 client/server pairs = 4000):
# * generate & log a seed
# * run shadow simulation with this seed
# * store the respective data - how about to save storage we just make a results-dir in which we have one dir each for our tgen stdout files in which we only store those and delete everything else, that seems reasonable!

# TODO adjust as needed
home_dir = '/home/joerg_diesel_rules'

# init random number generator
rng: Generator = default_rng(6734923)

# make a dir which will contain our results
subprocess.run([f'mkdir tgen-traffic-results'], shell=True,
               cwd=f'{home_dir}/tgen-traces')

# 500 times
for i in range(126):

    # generate a seed
    seed = rng.integers(0, 9999999)

    # make a dir which will contain this simulation's results
    subprocess.run([f'mkdir run-{i}'], shell=True,
                   cwd=f'{home_dir}/tgen-traces/tgen-traffic-results')

    # run simulation
    subprocess.run(
        [f'tornettools simulate -a="--seed={seed} --template-directory=shadow.data.template" tornet-0.0001'], shell=True, cwd=f'{home_dir}/tornettools')

    # once finished, copy the files we're interested in to results/run-{i}
    for j in range(1, 9):
        subprocess.run(
            [f'cp markovclient{j}exit/tgen.1004.stdout /home/joerg_diesel_rules/traffic_shaping/tgen-traces/tgen-results/run-{i}/client{j}.tgen.stdout'], shell=True, cwd=f'{home_dir}/tornettools/tornet-0.0001/shadow.data/hosts')
        subprocess.run(
            [f'cp server{j}exit/tgen.1000.stdout {home_dir}/traffic_shaping/tgen-traces/tgen-results/run-{i}/server{j}.tgen.stdout'], shell=True, cwd=f'{home_dir}/tornettools/tornet-0.0001/shadow.data/hosts')

    # delete the shadow.data dir
    subprocess.run(
        [f'rm -r shadow.data'], shell=True, cwd=f'{home_dir}/tornettools/tornet-0.0001')
