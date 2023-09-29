from typing import List, Dict, Tuple
import json
from os.path import exists

MICROSECONDS_PER_SECOND = 1000000
MICROSECONDS_TWO_HOURS = 120*60*MICROSECONDS_PER_SECOND

# TODO adjust as needed
home_dir = None


def compute_idle_time(ordered_events: List[Tuple[str, int, int]]) -> int:

    idle_time: int = 0

    num_active_flows: int = 0

    begin_idle_time: int = 0

    for event in ordered_events:

        type = event[0]
        timestamp = event[1]
        seed = event[2]

        if type == "CREATE":

            if num_active_flows == 0:

                idle_time += (timestamp - begin_idle_time)

            num_active_flows += 1

        elif type == "COMPLETE":

            if num_active_flows == 0:

                print("Something went wrong, can't complete a flow if none are active!")

            num_active_flows -= 1

            if num_active_flows == 0:

                begin_idle_time = timestamp

    return idle_time


def get_flow_stats(flows: Dict[int, Dict[str, int]]) -> Tuple[List[int], List[int]]:

    flow_durations: List[int] = []

    inter_flow_creation_intervals: List[int] = []

    last_creation_event: int = 0

    for key, val in flows.items():

        # if this flow was the last one, it was interrupted as the simulated ended, which is at 7200000000 microseconds after the experiment begun
        if val["time_completed"] == None:

            val["time_completed"] = MICROSECONDS_TWO_HOURS

        flow_durations.append(val["time_completed"] - val["time_created"])

        inter_flow_creation_intervals.append(
            val["time_created"] - last_creation_event)

        last_creation_event = val["time_created"]

    return flow_durations, inter_flow_creation_intervals


if __name__ == "__main__":

    ind = 0

    data_dict = dict()

    for run_nr in range(126):

        # 8 client-server pairs per run
        for nr in range(8):

            flow_dict = {"flows": dict(), "ordered_events": []}

            for i in range(100):

                filename = f"{home_dir}/traffic_shaping/results/verify-markov/run-{run_nr}/flowinfo-{nr}_{i}.json"

                if not exists(filename):

                    break

                else:

                    single_flow: Dict[str, Dict[str, int]] = None

                    with open(filename) as f:
                        single_flow = json.load(f)

                    flow_dict["flows"].update(single_flow)

                    for key, val in single_flow.items():

                        flow_dict["ordered_events"].append(
                            ("CREATE", val["time_created"], int(key)))

                        flow_dict["ordered_events"].append(
                            ("COMPLETE", val["time_completed"], int(key)))

            if len(flow_dict["flows"]) > 0:

                flow_dict["ordered_events"].sort(key=lambda a: a[1])

                data_dict[ind] = dict()

                data_dict[ind]["idle_time_total"] = compute_idle_time(
                    flow_dict["ordered_events"])

                data_dict[ind]["flow_durations"], data_dict[ind]["inter_flow_generation_intervals"] = get_flow_stats(
                    flow_dict["flows"])

                ind += 1

            else:

                continue

    # write back to file
    filename = f"{home_dir}/traffic_shaping/results/verify-markov/flow_stats.json"

    with open(filename, "w") as f:
        json.dump(data_dict, f)
