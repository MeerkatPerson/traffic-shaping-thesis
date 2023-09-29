from markov_model import *
import simpy
import random
from packet_generator import PacketGenerator
import json

# basically represents a flow


class StreamGenerator(object):

    env: simpy.Environment = None

    filename: str = None
    mmodel: MarkovModel = None
    msg_queue_client: simpy.resources.store.Store = None
    msg_queue_server: simpy.resources.store.Store = None

    id: int = None
    streams_created: int = None

    def __init__(self, env: simpy.Environment, run_nr: int, part_nr: int, mmodel: MarkovModel, msg_queue_client: simpy.resources.store.Store, msg_queue_server: simpy.resources.store.Store, id: int) -> None:
        self.env = env
        self.filename = f"../../results/verify-markov/run-{run_nr}/flowinfo-{part_nr}_{id}.json"
        self.mmodel = mmodel
        self.msg_queue_client = msg_queue_client
        self.msg_queue_server = msg_queue_server
        self.id = id
        self.streams_created = 0
        # register 'run' as process
        self.process = env.process(self.run())

    def run(self) -> None:

        start_time: int = self.env.now

        stream_completion_events: List[simpy.Event] = []

        # generate streams according to MarkovModel
        while True:

            # grab the next observation from markov model
            delay_microseconds, obs_type = self.mmodel.getNextObservation()

            if obs_type == "OBSERVATION_TO_ORIGIN" or obs_type == "OBSERVATION_TO_SERVER":

                packet_mmodel: MarkovModel = MarkovModel(
                    path="../../config/graphml/tgen.tor-packetmodel-ccs2018.graphml", startVertex_id="s0")

                packet_generator: PacketGenerator = PacketGenerator(
                    mmodel=packet_mmodel, env=self.env, msg_queue_client=self.msg_queue_client, msg_queue_server=self.msg_queue_server, parent_flow=self.id, id=self.streams_created)

                stream_completion_events.append(packet_generator.completed)

                print(
                    f"Flow with id {self.id} created a new stream with id={self.streams_created}.")

                self.streams_created += 1

                # sleep for 'delay_microseconds' microseconds
                yield self.env.timeout(delay_microseconds)

            else:

                # we reached the end state; exit
                print("Stream generator has reached end state.")

                break

        # wait for packet generators (= streams) to finish
        yield self.env.all_of(stream_completion_events)

        print("All streams are finished from stream generator's perspective.")

        completion_time: int = self.env.now

        data: Dict[int, Dict[str, int]] = {self.mmodel.seed: {
            "time_created": start_time, "time_completed": completion_time}}

        # write back to file
        with open(self.filename, "w") as f:
            json.dump(data, f)
