import simpy
from packet_generator import PacketGenerator
from typing import Dict

from msg_emitter import MessageEmitter

from msg_emitter_DEFAULT import DefaultMessageEmitter
from msg_emitter_LOOPIX import LoopixMessageEmitter
from msg_emitter_CONSTANT import ConstantMessageEmitter

from receiver import Receiver

# basically represents a flow


class StreamGenerator(object):

    env: simpy.Environment = None

    tmodel: Dict = None

    # we need 4 shared data stores:

    # (1) the msg queue at the client side (shared between client and client-side msg emitter)
    msg_queue_client: simpy.resources.store.Store = None
    # (2) the msg queue at the server side (shared between server and server-side msg emitter)
    msg_queue_server: simpy.resources.store.Store = None

    # (3) the queue representing the client -> server link (network_outward), shared between client and server
    network_outward: simpy.resources.store.Store = None
    # (4) the queue representing the server -> client link (network_inward), shared between client and server
    network_inward: simpy.resources.store.Store = None

    # message emitter processes on the client/server side, will be instantiated as one of our three different message emitter types depending on 'msg_emitter_type'
    msg_emitter_client: MessageEmitter = None
    msg_emitter_server: MessageEmitter = None

    # one of "DEFAULT" (no traffic shaping), "APE" (adaptive padding early: inserts cover traffic into statistically unlikely gaps in traffic to prevent fingerprinting based on characteristic burst-gap-patterns), "LOOPIX" (traffic shaping so that message emission follows a Poisson process, i.e., the inter-message-delays are exponentially distributed)
    msg_emitter_type: str = None

    # the sub-dir of 'results' into which we'll write data
    dir: str = None

    nr: int = None  # within one run, there are 8 client-server-pairs
    # there are 500 runs of 8 client-server-pairs each => 4000 traces in total
    run_nr: int = None

    scales: Dict[str, float] = None
    # dict of the form  {"CLIENT": 1.0, "SERVER": 1/12, "OVERALL": None} resp. {"CLIENT": None, "SERVER": None, "OVERALL": 1/6.5};
    # if scales["OVERALL"] is not none, we are in a scenario where we are using the same parameter irrespective of the client/server roles, otherwise the parameters corresponding to the participants' respective roles are used.
    # in LOOPIX scenarios, the respective scale is used to parameterize an exponential distribution from which inter-emission delays are sampled (the scale param of an exponential distribution also corresponds to its mean).
    # in CONSTANT scenarios, the scale is the constant inter-cell delay (in seconds).

    streams_created: int = None

    def __init__(self, env: simpy.Environment, tmodel: Dict, dir: str, nr: int, run_nr: int, msg_emitter_type: str, scales: Dict[str, float] = None, seed: int = None) -> None:
        self.env = env
        self.tmodel = tmodel
        self.dir = dir
        self.msg_queue_client = simpy.Store(env)
        self.msg_queue_server = simpy.Store(env)
        self.network_outward = simpy.Store(env)
        self.network_inward = simpy.Store(env)
        self.msg_emitter_type = msg_emitter_type
        self.nr = nr
        self.run_nr = run_nr
        self.scales = scales  # this param is required by the LOOPIX and CONSTANT message emitters
        # this param is required by the APE and LOOPIX msg emitters which use randomness
        self.seed = seed
        self.streams_created = 0

        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        # create msg emitters as well as receivers:

        # (I.) instantiate one of our three msg emitters depending on 'msg_emitter_type'
        if self.msg_emitter_type == "DEFAULT":
            self.msg_emitter_client = DefaultMessageEmitter(
                self.env, self.dir, network=self.network_outward, msg_queue=self.msg_queue_client, participant="CLIENT", nr=self.nr, run_nr=self.run_nr)
            self.msg_emitter_server = DefaultMessageEmitter(
                self.env, self.dir, network=self.network_inward, msg_queue=self.msg_queue_server, participant="SERVER", nr=self.nr, run_nr=self.run_nr)
        elif self.msg_emitter_type == "LOOPIX":
            self.msg_emitter_client: LoopixMessageEmitter = LoopixMessageEmitter(
                self.env, self.dir, network=self.network_outward, msg_queue=self.msg_queue_client, participant="CLIENT", nr=self.nr, run_nr=self.run_nr, scales=self.scales, seed=self.seed)

            self.msg_emitter_server: LoopixMessageEmitter = LoopixMessageEmitter(
                self.env, self.dir, network=self.network_inward, msg_queue=self.msg_queue_server, participant="SERVER", nr=self.nr, run_nr=self.run_nr, scales=self.scales, seed=self.seed)
        elif self.msg_emitter_type == "CONSTANT":
            self.msg_emitter_client: ConstantMessageEmitter = ConstantMessageEmitter(
                self.env, self.dir, network=self.network_outward, msg_queue=self.msg_queue_client, participant="CLIENT", nr=self.nr, run_nr=self.run_nr, scales=self.scales)

            self.msg_emitter_server: ConstantMessageEmitter = ConstantMessageEmitter(
                self.env, self.dir, network=self.network_inward, msg_queue=self.msg_queue_server, participant="SERVER", nr=self.nr, run_nr=self.run_nr, scales=self.scales)
        else:
            print("Unknown msg emitter type, aborting!")
            exit

        # (II.) create/start the receivers; inform them of how many streams constitute the presently simulated flow (so they know they're finished once they have received an 'END'-cell on each of these streams), information which we luckily can derive from the length of self.tmodel

        num_streams: int = len(self.tmodel)

        client_receiver: Receiver = Receiver(
            self.env, network=self.network_inward, participant="CLIENT", num_streams=num_streams)

        server_receiver: Receiver = Receiver(
            self.env, network=self.network_outward, participant="SERVER", num_streams=num_streams)

        for stream_key, stream_val in self.tmodel.items():

            # grab the next stream's delay
            delay_microseconds = stream_val['delay']

            # wait for this amount of time
            yield self.env.timeout(delay_microseconds)

            # start the stream (= PacketGenerator)
            packet_tmodel = stream_val['emissions']

            packet_generator: PacketGenerator = PacketGenerator(
                env=self.env, tmodel=packet_tmodel, msg_queue_client=self.msg_queue_client, msg_queue_server=self.msg_queue_server, id=self.streams_created)

            print(
                f"Flow created a new stream with id={self.streams_created}.")

            self.streams_created += 1

        print(
            f"Flow has created all (= {self.streams_created}) streams.")

        # wait for the receivers to finish; they will emit a 'completed' event once they have received an 'END'-cell for each stream.
        yield self.env.all_of([client_receiver.completed, server_receiver.completed])

        print(
            f"All (= {self.streams_created}) streams have completed on the receiving end.")

        # interrupt the msg emitters as well as receivers
        self.msg_emitter_client.action.interrupt()
        self.msg_emitter_server.action.interrupt()
