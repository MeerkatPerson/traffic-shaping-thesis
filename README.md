# GAUGING THE OVERHEAD (in terms of bytes and latency) OF LOOPIX' TRAFFIC SHAPING STRATEGY (and compare with APE)

tl;dr
- we run [`tgen`](https://github.com/shadow/tgen)-over-Tor simulations in [`Shadow`](https://shadow.github.io/) and generate load based on the resulting `tgen` traces in the context of `SimPy` simulations. Idea therein: have a highly abstract setting in which we can analyze the effect of traffic-shaping strategies when applied to traffic typical of Tor (`tgen` generates traffic based on models learned at a number of actual Tor relays in a privacy preserving manner) 
- we are comparing two traffic shaping strategies: [**APE** (Adaptive Padding Early)](https://www.cs.kau.se/pulls/hot/thebasketcase-ape/) as well as the traffic shaping strategy used by the [**Loopix** Anonymity System](https://www.usenix.org/conference/usenixsecurity17/technical-sessions/presentation/piotrowska) (emit traffic according to a Poisson process)
- then we also have `SimPy` code that directly uses `tgen`'s traffic models (essentially, a bunch of Markov Models encoded as `graphml` files) to generate traffic, without requiring `tgen`-traces.

## REQUIRED TOOLS AND SET-UP

- `Shadow`: installation instructions [here](https://shadow.github.io/docs/guide/shadow.html)
- `tornettools`: a `Python` library for generating virtual Tor networks to use in `Shadow`-simulations, installation instructions [here](https://github.com/shadow/tornettools), requires installation of `oniontrace`: installation instructions [here](https://github.com/shadow/oniontrace); also requires `tgen`, but **DON'T INSTALL AS WE REQUIRE OUR CUSTOM TGEN WHICH IS INCLUDED IN THIS DIRECTORY**
- `Tor`: installation instructions included in `tornettools` installation instructions
- `Python3`, make a venv & install dependencies as per `requirements.txt`
- generate empty directories `results` and `plots`
- verify paths as needed; **note that our code assumes the present top level directory to be named `traffic_shaping`**

## BUILD OUR CUSTOM TGEN

We have added additional logging to `tgen`'s source code, so let's build our custom version.

```
cd tgen

mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local
make

make install
```

## RUN `tgen`-over-Tor experiments in `Shadow`

We'll run 500 experiments consisting of 8 client-server pairs engaging in one flow of communication each (a flow of communication refers to tgen's terminology here; essentially, a flow logically groups streams together in the same manner a Tor circuit does).

Navigate into the `tornettools` install directory. Let's assume you have set up the required venv, as per the installation instructions. Activate this venv. Generate a scaled-down tornet:

```
tornettools generate \
    relayinfo_staging_2023-04-01--2023-04-30.json \
    userinfo_staging_2023-04-01--2023-04-30.json \
    networkinfo_staging.gml \
    tmodel-ccs2018.github.io \
    --network_scale 0.0001 \
    --prefix tornet-0.0001
```

Now go ahead and check out our `config` directory. Replace the `shadow.config.yaml` file that `tornettools` has generated, respectively alter the generated file to match the `shadow.config.yaml` file found in `config`. Essentially, we want to remove all `perfclients` and also all except the first 8 `markovclients`. Each of these first 8 `markovclients` will communicate with one of the `fileservers`, and each `fileserver` communicates with one `markovclient` only. Replace the `tgenrc.graphml` files in `tornettools/tornet-0.0001/shadow.data.template/hosts/markovclient{i}exit`, i in {1,...,8} with the ones in `config/tgenrc_gc_flows`. 

In `src/scripts`, replace `home_dir` as required in `tgen_experiment_flows.py`. Run with `tornettools`'s venv active.

## RUN traffic shaping experiments in `SimPy`

To run a simulation that consumes the `tgen`-traces generated in the previous step and runs `LOOPIX` traffic shaping strategy on them as viewed **uni-directionally** (i.e., each participant in role client/server believes a flow to have finished once they have sent all data they were supposed to according to the underlying `tgen` trace), navigate into `src/simpy_tgen` and run `main_loopix_unidirectional.py`, with the venv active that has all the dependencies specified in `requirements.txt` (i.e., not `tornettools` venv, but the one generated for this project). Once finished, compute the overheads using `src/simpy_tgen/overheads_LOOPIX_unidirectional.py` and visualize using `src/notebooks/loopix_unidirectional.ipynb`.

To run a simulation that consumes the `tgen`-traces generated in the previous step and runs `LOOPIX` traffic shaping strategy on them as viewed **bi-directionally** (i.e., both participants in a client-server-pair have the same understanding of a flow's duration: it's over once BOTH participants have transferred all data they were supposed to according to the underlying `tgen`-trace), navigate into `src/simpy_tgen_bidirectional` and run `main_bidirectional.py`. Once finished, analyze overheads using `src/simpy_tgen_bidirectional/overheads_loopix_bidirectional.py` and visualize using `src/notebooks/ape_loopix_bidirectional.ipynb`.

To run a simulation that consumes the `tgen`-traces generated in the previous step and runs `APE` traffic shaping strategy on them (inherently bi-directional perspective as per the defense's design), run `src/simpy_tgen_bidirectional/main_ape.py`, compute overheads using `overheads_APE.py` and visualize using `src/notebooks/ape_loopix_bidirectional.ipynb`.

## Additional experiment: idle time in `tgen` & validation of pure `SimPy` approach

In an additional experiment, we gauge the amount of time Tor clients spend idle with no streams associated with them that are actively generating data (because `LOOPIX` is designed to provide un-observability, idle time requires having to continously generate cover traffic, resulting in a high overhead in terms of bytes).

For this experiment, we use a different configuration in the `tgen`-over-Tor portion: change simulation time in `shadow.config.yaml` to two hours (7200 seconds), and replace the 8 clients' `tgenrc.graphml` files with the ones in `config/graphml/tgenrc_gc_traffic`. Rather than generating just one flow and then exiting, clients now continuously generate flows for a period of two simulated hours. 

After having made these changes, adapt `home_dir` in `src/scripts/tgen_experiment_traffic.py` and run. After the simulation has finished, compute results using `src/scripts/tgen_analyze_idle_time.py` (prior to that, alter `home_dir` as needed).

We use these results to validate another `SimPy` traffic shaping experimentation approach, which does not require consuming `tgen` logs, but uses `tgen`'s Markov Models (which are encoded as `graphml` files) directly. To execute, run `src/simpy/markovmodel/main.py`. After experiment has finished, run `src/scripts/mmodel_analyze_idle_time.py`.

Visualize comparison of the `tgen`-log-consuming approach and the Markov-Model-consuming approach using `src/notebooks/idle_time.ipynb`.