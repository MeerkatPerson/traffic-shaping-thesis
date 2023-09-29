import simpy
from packet_generator import PacketGenerator
from typing import Dict, List

from msg_emitter import MessageEmitter

from msg_emitter_default import DefaultMessageEmitter
from msg_emitter_APE import APEMessageEmitter
from msg_emitter_Loopix import LoopixMessageEmitter
from msg_emitter_CONSTANT import ConstantMessageEmitter

# basically represents a flow


class StreamGenerator(object):

    env: simpy.Environment = None

    tmodel: Dict = None

    # we need some shared data stores:

    # (1a) the msg queue at the client side (shared between client-packet generator and client-side msg emitter)
    msg_queue_client: simpy.resources.store.Store = None

    # (2b) the DOWNSTREAM msg queue at the client side, processing data received from the server - only required in the APE scenario (shared between reverse client-packet generator and client-side msg emitter)
    msg_queue_client_downstream: simpy.resources.store.Store = None

    # (2a) the msg queue at the server side (shared between server and server-side msg emitter)
    msg_queue_server: simpy.resources.store.Store = None

    # (2b) the DOWNSTREAM msg queue at the server side, processing data received from the client - only required in the APE scenario (shared between reverse server-packet generator and server-side msg emitter)
    msg_queue_server_downstream: simpy.resources.store.Store = None

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

        if msg_emitter_type == "APE" or msg_emitter_type == "DEFAULT_INCL_DOWNSTREAM":
            self.msg_queue_client_downstream = simpy.Store(env)
            self.msg_queue_server_downstream = simpy.Store(env)

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

        # the message emitters need to know how many streams this flow includes in total so they can shut down once they have received an "END"-cell from the respective PacketGenerator on all of them.
        num_streams: int = len(self.tmodel)

        # (I.) instantiate one of our three msg emitters depending on 'msg_emitter_type'
        # **************************************************************
        # NEW as of 13/09: DEFAULT message emitter optionally processes data reception events as well, for accurate comparison with APE.
        if self.msg_emitter_type == "DEFAULT":
            self.msg_emitter_client = DefaultMessageEmitter(
                self.env, self.dir, msg_queue_downstream=None, msg_queue_upstream=self.msg_queue_client, participant="CLIENT", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr)
            self.msg_emitter_server = DefaultMessageEmitter(
                self.env, self.dir, msg_queue_downstream=None, msg_queue_upstream=self.msg_queue_server, participant="SERVER", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr)
        elif self.msg_emitter_type == "DEFAULT_INCL_DOWNSTREAM":
            self.msg_emitter_client = DefaultMessageEmitter(
                self.env, self.dir, msg_queue_downstream=self.msg_queue_client_downstream,  msg_queue_upstream=self.msg_queue_client, participant="CLIENT", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr)
            self.msg_emitter_server = DefaultMessageEmitter(
                self.env, self.dir, msg_queue_downstream=self.msg_queue_server_downstream, msg_queue_upstream=self.msg_queue_server, participant="SERVER", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr)
        # **************************************************************
        elif self.msg_emitter_type == "APE":
            self.msg_emitter_client: APEMessageEmitter = APEMessageEmitter(
                self.env, self.dir, msg_queue_downstream=self.msg_queue_client_downstream, msg_queue_upstream=self.msg_queue_client, participant="CLIENT", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr, seed=self.seed)
            self.msg_emitter_server: APEMessageEmitter = APEMessageEmitter(
                self.env, self.dir, msg_queue_downstream=self.msg_queue_server_downstream, msg_queue_upstream=self.msg_queue_server, participant="SERVER", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr, seed=self.seed)
        elif self.msg_emitter_type == "LOOPIX":
            self.msg_emitter_client: LoopixMessageEmitter = LoopixMessageEmitter(
                self.env, self.dir, msg_queue=self.msg_queue_client, participant="CLIENT", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr, scales=self.scales, seed=self.seed)

            self.msg_emitter_server: LoopixMessageEmitter = LoopixMessageEmitter(
                self.env, self.dir, msg_queue=self.msg_queue_server, participant="SERVER", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr, scales=self.scales, seed=self.seed)
        elif self.msg_emitter_type == "CONSTANT":
            self.msg_emitter_client: ConstantMessageEmitter = ConstantMessageEmitter(
                self.env, self.dir, msg_queue=self.msg_queue_client, participant="CLIENT", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr, scales=self.scales)

            self.msg_emitter_server: ConstantMessageEmitter = ConstantMessageEmitter(
                self.env, self.dir, msg_queue=self.msg_queue_server, participant="SERVER", num_streams=num_streams, nr=self.nr, run_nr=self.run_nr, scales=self.scales)
        else:
            print("Unknown msg emitter type, aborting!")
            exit

        # (II.) luckily, we can derive the number of streams from the length of self.tmodel. Let's see how we're going to use that information now that we are getting rid of receivers

        for stream_key, stream_val in self.tmodel.items():

            # grab the next stream's delay
            delay_microseconds = stream_val['delay']

            # wait for this amount of time
            yield self.env.timeout(delay_microseconds)

            # start the stream (= PacketGenerators one each client/server)

            packet_generator_client: PacketGenerator = PacketGenerator(
                env=self.env, kind="upstream", tmodel=stream_val['emissions_client'], msg_queue=self.msg_queue_client, participant="CLIENT", id=self.streams_created)

            packet_generator_server: PacketGenerator = PacketGenerator(
                env=self.env, kind="upstream", tmodel=stream_val['emissions_server'], msg_queue=self.msg_queue_server, participant="SERVER", id=self.streams_created)

            # NEW: if APE, we're generating two more packet generators for the opposite direction
            if self.msg_emitter_type == "APE" or self.msg_emitter_type == "DEFAULT_INCL_DOWNSTREAM":

                packet_generator_client_reverse: PacketGenerator = PacketGenerator(
                    env=self.env, kind="downstream", tmodel=stream_val['rcv_client'], msg_queue=self.msg_queue_client_downstream, participant="CLIENT", id=self.streams_created)

                packet_generator_server_reverse: PacketGenerator = PacketGenerator(
                    env=self.env, kind="downstream", tmodel=stream_val['rcv_server'], msg_queue=self.msg_queue_server_downstream, participant="SERVER", id=self.streams_created)

            print(
                f"Flow created a new stream with id={self.streams_created}.")

            self.streams_created += 1

        print(
            f"Flow has created all (= {self.streams_created}) streams.")
