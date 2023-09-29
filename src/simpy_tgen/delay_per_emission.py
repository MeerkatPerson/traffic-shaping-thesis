from typing import Dict, List
import math
import os
import json
import pandas as pd
import seaborn as sns
# from overheads_tgen import load_data
from message import scales_to_str
from statistics import median, stdev


def load_data(dir: str, run_nr: int, nr: int, scenario: str, kind: str, participant: str, scales_str: str) -> Dict[str, int]:

    # get the dir from which to read data
    # the top level directory, i.e. two levels up from this file's dir
    p = os.path.dirname(os.path.dirname(os.getcwd()))

    # print(p)

    # now get to the results/{target-dir}/{dir-for-current-run} directory from there
    results_dir = os.path.join(p, 'results', dir, f'run-{run_nr}')

    filename: str = f'{participant}{nr}_{scenario}.json'

    # for the traffic shaping scenarios, we also have separate files containing info on just "DATA" resp. "DUMMY" emissions, but by default we want info on ALL emissions.
    if scenario in ["LOOPIX", "CONSTANT"]:
        filename = f'{participant}{nr}_{scenario}-{scales_str}_{kind}.json'
    elif scenario == "APE":
        filename = f'{participant}{nr}_{scenario}_{kind}.json'

    # abs_filename: str = os.path.join(
    #    results_for_run_dir, filename)
    abs_filename: str = os.path.join(
        results_dir, filename)

    data_dict: Dict[str, int] = None

    # read the file
    with open(abs_filename) as f:
        data_dict = json.load(f)

    # new dict which we will eventually return
    processed_data_dict: Dict[str, int] = dict()

    # handle floating point vals in the keys
    for key, val in data_dict.items():

        # try to split at dot (there will only be a dot if we have a floating point val)
        key_chunks = key.split(".")

        # check if we split the key string in two by splitting at the dot
        if len(key_chunks) == 1:

            # technically this shouldn't happen, but let's be extra safe
            if key in processed_data_dict:

                processed_data_dict[key] += val

            else:

                processed_data_dict[key] = val

        else:

            # round up
            ceil_key = int(math.ceil(float(key)))

            if str(ceil_key) in processed_data_dict:

                processed_data_dict[str(ceil_key)] += val

            else:

                processed_data_dict[str(ceil_key)] = val

    return processed_data_dict


def trace_to_emission_times(trace: Dict[str, int]) -> List[int]:

    emission_times: List[int] = []

    for key, val in trace.items():

        key_int = int(key)

        num_cells = val // 514

        assert (val == num_cells*514)

        emission_times.extend([key_int] * num_cells)

    return emission_times


if __name__ == "__main__":

    target_dir = "29-08-23"

    # load data for default scenario, for comparison purposes
    default_data = dict()

    for run_nr in range(500):

        default_data[run_nr] = dict()

        for part_nr in [1, 2, 3, 4, 5, 6, 7, 8]:

            default_data[run_nr][part_nr] = dict()

            default_trace_client = load_data(
                dir=target_dir, run_nr=run_nr, nr=part_nr, scenario="DEFAULT", kind=None, participant="CLIENT", scales_str=None)

            default_trace_server = load_data(
                dir=target_dir, run_nr=run_nr, nr=part_nr, scenario="DEFAULT", kind=None, participant="SERVER", scales_str=None)

            default_data[run_nr][part_nr]["emission_times_client"] = trace_to_emission_times(
                default_trace_client)

            default_data[run_nr][part_nr]["emission_times_server"] = trace_to_emission_times(
                default_trace_server)

    # dict which will contain our aggregated info
    """
    overhead_aggregated = {
        "scale": [],
        "scenario": [],
        "delay_per_emission_med_client": [],
        "delay_per_emission_std_client": [],
        "delay_per_emission_med_server": [],
        "delay_per_emission_std_server": []
    }
    """

    overhead_dist = {
        "delays_individual_traces": dict(),
        "all_delays_client_LOOPIX": [],
        "all_delays_server_LOOPIX": [],
        "all_delays_client_CONSTANT": [],
        "all_delays_server_CONSTANT": []
    }

    # compute (median, std) of emission delay (temporal distance between a specific emission in the default scenario, i.e. without traffic shaping, and traffic shaping scenario with a specific scale)
    # for scale_val in [0.0400, 0.0417, 0.0436, 0.0456, 0.0479, 0.0503, 0.0531, 0.0562, 0.0596, 0.0635, 0.0679, 0.0730,
    #                   0.0789, 0.0859, 0.0942, 0.1043, 0.1169, 0.1328, 0.1538, 0.1827, 0.2250, 0.2927, 0.4186, 0.7347, 3.0]:

    ind = 0

    for scale_val in [3.0]:

        scales = {"CLIENT": None, "SERVER": None, "OVERALL": scale_val}

        scale_str = scales_to_str(scales=scales)

        for run_nr in range(500):

            for part_nr in [1, 2, 3, 4, 5, 6, 7, 8]:

                overhead_dist["delays_individual_traces"][ind] = dict()

                for scenario in ["LOOPIX", "CONSTANT"]:

                    # load the data from file (just DATA for now as I haven't figured out yet how to visualize the fluctuations in bandwidth overhead)
                    data_dict_client: Dict[str, int] = load_data(
                        dir=target_dir, run_nr=run_nr, nr=part_nr, scenario=scenario, kind="DATA", participant="CLIENT", scales_str=scale_str)

                    data_dict_server: Dict[str, int] = load_data(
                        dir=target_dir, run_nr=run_nr, nr=part_nr, scenario=scenario, kind="DATA", participant="SERVER", scales_str=scale_str)

                    # retrieve the previously computed DEFAULT emission times
                    emission_times_client_default = default_data[run_nr][part_nr]["emission_times_client"]
                    emission_times_server_default = default_data[run_nr][part_nr]["emission_times_server"]

                    # transform the DATA-data (containing info on actual emissions) into a list of emission times, subtract from this the list of emission times for DEFAULT and this run/part_nr to get the per-emission delays, add to delay_per_emission_scale_scenario
                    emission_times_client_scenario_scale = trace_to_emission_times(
                        data_dict_client)

                    assert (len(emission_times_client_default) ==
                            len(emission_times_client_scenario_scale))

                    emission_times_server_scenario_scale = trace_to_emission_times(
                        data_dict_server)

                    assert (len(emission_times_server_default) ==
                            len(emission_times_server_scenario_scale))

                    emission_delays_client = [element1 - element2 for (element1, element2) in zip(
                        emission_times_client_scenario_scale, emission_times_client_default)]

                    # print(emission_delays_client)

                    emission_delays_server = [element1 - element2 for (element1, element2) in zip(
                        emission_times_server_scenario_scale, emission_times_server_default)]

                    overhead_dist["delays_individual_traces"][ind][
                        f"delays_client_{scenario}"] = emission_delays_client
                    overhead_dist["delays_individual_traces"][ind][
                        f"delays_server_{scenario}"] = emission_delays_server

                    overhead_dist[f"all_delays_client_{scenario}"].extend(
                        emission_delays_client)
                    overhead_dist[f"all_delays_server_{scenario}"].extend(
                        emission_delays_server)

                ind += 1

   # get the dir from which to read data
    # the top level directory, i.e. two levels up from this file's dir
    p = os.path.dirname(os.path.dirname(os.getcwd()))

    # now get to the results directory from there
    results_dir = os.path.join(p, 'results', target_dir)

    # now get to the dir containing the results for the respective run
    overall_results_path = os.path.join(
        results_dir, 'LOOPIX_vs_CONSTANT_3-00_01-09-23.json')

    # write the file
    with open(overall_results_path, "w") as f:
        json.dump(overhead_dist, f)
