from typing import Dict, List, Union
import os
import json
import math
import os.path
from message import scales_to_str

# since we're in a discrete event simulation here, start time is always at 0 microseconds and thus we only need to grab the timestamps of our last emissions


def latency(data_client: Dict[str, int], data_server: Dict[str, int]) -> int:
    # since dictionary keys aren't sorted generally, even if we put them in there in ascending order, got to determine the max like below to be sure
    last_emission_client: int = max(
        list(map(lambda x: int(x), list(data_client.keys())))) if len(data_client) > 0 else 0
    last_emission_server: int = max(
        list(map(lambda x: int(x), list(data_server.keys())))) if len(data_server) > 0 else 0

    if len(data_client) == 0 or len(data_server) == 0:
        print("No emissions!")

    return last_emission_client, last_emission_server

# how much longer did we take when applying a traffic shaping strategy as opposed to none?


def latency_ovhd(traffic_shaping_scenario_val: int, default_scenario_val: int) -> float:
    if default_scenario_val == 0.0:
        return 0.0
    return traffic_shaping_scenario_val / default_scenario_val

# self-explanatory


def bandwidth(data_dicts: List[Dict[str, int]], latency: int) -> float:
    if latency == 0.0:
        return 0
    total_bytes = 0
    for data_dict in data_dicts:
        total_bytes += sum(data_dict.values())
    return total_bytes / latency

# doesn't really make sense for Loopix because Loopix takes so much longer than default/APE (APE by contrast adds zero latency)


def bandwidth_ovhd(traffic_shaping_scenario_val: float, default_scenario_val: float) -> float:
    if default_scenario_val == 0.0:
        return 0.0
    return traffic_shaping_scenario_val / default_scenario_val

# just all the bytes


def bytes_transferred(data_dicts: List[Dict[str, int]]) -> float:
    total_bytes = 0
    for data_dict in data_dicts:
        total_bytes += sum(data_dict.values())
    return total_bytes

# ... and how many bytes were transferred compared to the default scenario with no traffic shaping


def bytes_ovhd(traffic_shaping_scenario_val: int, default_scenario_val: int) -> float:
    if default_scenario_val == 0:
        return 0.0
    return traffic_shaping_scenario_val / default_scenario_val


def load_data(dir: str, run_nr: int, nr: int, scenario: str, participant: str, scales_str: str, kind: str = "OVERALL") -> Dict[str, int]:

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

# helper funct for generating a dictionary key str
# scenario is one of ["LOOPIX", "CONSTANT", "DEFAULT", "APE"]
# perspective is one of ["CLIENT", "SERVER"]
# scales_str is only required for LOOPIX and CONSTANT; it corresponds to the (mean) inter-emission delay


def get_key_str(metric: str, scenario_str: str, perspective: str, scales_str: str = None) -> str:

    if scenario_str in ["LOOPIX", "CONSTANT"]:

        return f"{metric}_{scenario_str}_{perspective}_{scales_str}"

    else:

        return f"{metric}_{scenario_str}" if perspective == None else f"{metric}_{scenario_str}_{perspective}"


if __name__ == "__main__":

    res_dir: str = "APE"

    scenario_tuples = [("DEFAULT", None), ("APE", None)]

    data_dict: Dict[int, Dict[str, Union[int, float]]] = dict()

    ind = 0

    for run_nr in range(500, 516):
        # for run_nr in range(500):

        # 8 client-server-pairs per run
        for nr in [1, 2, 3, 4, 5, 6, 7, 8]:

            # this means in run 0, we have client-server-pairs 1-8,
            # in run 1, we have client-server-pairs 9-16, ...
            # ind: int = run_nr*39 + nr

            print(f"Index: {ind}")

            data_dict[ind]: Dict[str, Union[int, float]] = dict()

            # check if there was a fail in either of the scenarios, if so remove the entire index
            fail: bool = False

            # use tuples because Loopix uses different scale parameters
            # for scenario_tuple in [("DEFAULT", None), ("APE", None), ("LOOPIX", 2.0), ("LOOPIX", 0.5)]:
            for scenario_tuple in scenario_tuples:

                if fail == False:

                    scenario_str: str = scenario_tuple[0]
                    scenario_scales: str = scenario_tuple[1]

                    scales_str: str = scales_to_str(
                        scenario_scales) if scenario_scales is not None else None

                    # load the respective data for this combination of run_nr, run, participant, scenario, scale (the latter only relevant if scenario is LOOPIX)
                    try:
                        data_client: Dict[str, int] = load_data(dir=res_dir,
                                                                run_nr=run_nr, nr=nr, scenario=scenario_str, participant="CLIENT", scales_str=scales_str)
                    except:
                        fail = True
                        continue

                    try:
                        data_server: Dict[str, int] = load_data(dir=res_dir,
                                                                run_nr=run_nr, nr=nr, scenario=scenario_str, participant="SERVER", scales_str=scales_str)
                    except:
                        fail = True
                        continue

                    if (len(data_client) < 1 or len(data_server) < 1):
                        print(
                            f"Empty data for scenario {scenario_str} , with scale (if present) {scenario_scales}")
                        break

                    # (I.) compute & store runtime (all scenarios) as well as runtime overhead (latency overhead) for the traffic shaping scenarios

                    runtime_key_str_client = get_key_str(
                        metric="rt", scenario_str=scenario_str, perspective="CLIENT", scales_str=scales_str)

                    runtime_key_str_server = get_key_str(
                        metric="rt", scenario_str=scenario_str, perspective="SERVER", scales_str=scales_str)

                    # fill in the latency (= total runtime) into this dict key/column
                    runtime_client, runtime_server = latency(
                        data_client=data_client, data_server=data_server)

                    data_dict[ind][runtime_key_str_client] = runtime_client

                    data_dict[ind][runtime_key_str_server] = runtime_server

                    # for APE, we are computing runtime overhead globally, not separately for client and server
                    if scenario_str == "APE":

                        # grab the default scenario's runtime for comparison, here defined as the max of the client's and server's runtime
                        runtime_default_key_str_client = get_key_str(
                            metric="rt", scenario_str="DEFAULT", perspective="CLIENT", scales_str=None)

                        runtime_default_client = data_dict[ind][runtime_default_key_str_client]

                        runtime_default_key_str_server = get_key_str(
                            metric="rt", scenario_str="DEFAULT", perspective="SERVER", scales_str=None)

                        runtime_default_server = data_dict[ind][runtime_default_key_str_server]

                        runtime_default = max(
                            runtime_default_client, runtime_default_server)

                        # get the runtime in the traffic shaping scenario (APE) as the max of client's and server's runtime
                        runtime_scenario = max(runtime_client, runtime_server)

                        runtime_oh_key_str = get_key_str(
                            metric="rt_oh", scenario_str=scenario_str, perspective=None, scales_str=scales_str)

                        runtime_overhead = latency_ovhd(
                            traffic_shaping_scenario_val=runtime_scenario, default_scenario_val=runtime_default)

                        data_dict[ind][runtime_oh_key_str] = runtime_overhead

                    # for LOOPIX and CONSTANT, we're determining the runtime overhead separately for client and server
                    if scenario_str in ["LOOPIX", "CONSTANT"]:

                        for participant in ["CLIENT", "SERVER"]:

                            # grab the default scenario's runtime for comparison
                            runtime_default_key_str_participant = get_key_str(
                                metric="rt", scenario_str="DEFAULT", perspective=participant, scales_str=None)

                            runtime_default = data_dict[ind][runtime_default_key_str_participant]

                            # = "rt_oh_APE_{CLIENT, SERVER}" resp. "rt_oh_{LOOPIX, CONSTANT}_{CLIENT, SERVER}_{scales_str}" resp. "rt_oh_CONSTANT_{scales_str}"
                            runtime_oh_key_str_participant = get_key_str(
                                metric="rt_oh", scenario_str=scenario_str, perspective=participant, scales_str=scales_str)

                            runtime_overhead = latency_ovhd(
                                traffic_shaping_scenario_val=runtime_client, default_scenario_val=runtime_default) if participant == "CLIENT" else latency_ovhd(
                                traffic_shaping_scenario_val=runtime_server, default_scenario_val=runtime_default)

                            data_dict[ind][runtime_oh_key_str_participant] = runtime_overhead

                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

                    # (II.) compute total_bytes_{total, client, server}, bandwidth_{total, client, server} as well as the corresponding overhead for the traffic shaping scenarios
                    for perspective in [("TOTAL", [data_client, data_server]), ("CLIENT", [data_client]), ("SERVER", [data_server])]:

                        perspective_str = perspective[0]
                        perspective_data_dicts = perspective[1]

                        # bw_key_str = for example "bw_CLIENT_APE" resp. "bw_SERVER_LOOPIX_{scales_str}" resp. "bw_SERVER_CONSTANT_{scales_str}"
                        bw_key_str: str = get_key_str(
                            metric="bw", scenario_str=scenario_str, perspective=perspective_str, scales_str=scales_str)

                        # compute bandwidth for this scenario and the perspective, i.e. both client and server or just client resp. just server
                        bw_scenario_perspective = bandwidth(
                            data_dicts=perspective_data_dicts, latency=runtime_client) if perspective_str == "CLIENT" else bandwidth(
                            data_dicts=perspective_data_dicts, latency=runtime_server) if perspective_str == "SERVER" else bandwidth(
                            data_dicts=perspective_data_dicts, latency=max(runtime_server, runtime_client))

                        data_dict[ind][bw_key_str] = bw_scenario_perspective

                        # same for bytes; here we are only interested in the amount of data transferred, irrespective of transfer duration
                        bytes_key_str: str = get_key_str(
                            metric="bytes", scenario_str=scenario_str, perspective=perspective_str, scales_str=scales_str)

                        bytes_scenario_perspective = bytes_transferred(
                            data_dicts=perspective_data_dicts)

                        data_dict[ind][bytes_key_str] = bytes_scenario_perspective

                        # if we're in a traffic shapiung scenario, we also want to compute the overhead incurred compared to the default scenario with no traffic shaping
                        if scenario_str in ["APE", "LOOPIX", "CONSTANT"]:

                            # grab the default scenario's bw for this perspective (client/server)
                            bw_default_key_str = get_key_str(
                                metric="bw", scenario_str="DEFAULT", perspective=perspective_str, scales_str=None)

                            bw_default = data_dict[ind][bw_default_key_str]

                            # compute the overhead by dividing the bandwidth for this (scenario, scale, perspective) tuple by the (DEFAULT, perspective) value
                            bw_oh_key_str = get_key_str(
                                metric="bw_oh", scenario_str=scenario_str, perspective=perspective_str, scales_str=scales_str)

                            bw_oh_scenario_perspective = bandwidth_ovhd(
                                traffic_shaping_scenario_val=bw_scenario_perspective, default_scenario_val=bw_default)

                            data_dict[ind][bw_oh_key_str] = bw_oh_scenario_perspective

                            # grab the default scenario's bytes for this perspective (client/server)
                            bytes_default_key_str = get_key_str(
                                metric="bytes", scenario_str="DEFAULT", perspective=perspective_str, scales_str=None)

                            bytes_default = data_dict[ind][bytes_default_key_str]

                            # compute the overhead by dividing the bandwidth for this (scenario, scale, perspective) tuple by the (DEFAULT, perspective) value
                            bytes_oh_key_str = get_key_str(
                                metric="bytes_oh", scenario_str=scenario_str, perspective=perspective_str, scales_str=scales_str)

                            bytes_oh_scenario_perspective = bytes_ovhd(
                                traffic_shaping_scenario_val=bytes_scenario_perspective, default_scenario_val=bytes_default)

                            data_dict[ind][bytes_oh_key_str] = bytes_oh_scenario_perspective

            # check if there was a fail in either of the scenarios for this index, if so, remove the datapoint and do not increment index, otherwise do increment index
            if fail == True:

                data_dict.pop(ind)

            else:

                ind += 1

    # get the dir from which to read data
    # the top level directory, i.e. two levels up from this file's dir
    p = os.path.dirname(os.path.dirname(os.getcwd()))

    # now get to the results directory from there
    results_dir = os.path.join(p, 'results', res_dir)

    # now get to the dir containing the results for the respective run
    overall_results_path = os.path.join(
        results_dir, 'APE_overheads.json')

    # read the file
    with open(overall_results_path, "w") as f:
        json.dump(data_dict, f)
