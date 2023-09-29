from markov_model import *
import simpy
from globals import TGEN_MMODEL_PACKET_DATA_SIZE, HEADER_LEN, PAYLOAD_LEN
from message import Message

# basically represents a stream


class PacketGenerator(object):

    mmodel: MarkovModel = None
    msg_queue_client: simpy.resources.store.Store = None
    msg_queue_server: simpy.resources.store.Store = None
    parent_flow: int = None
    id: int = None
    num_cells_sent: int = None

    completed: simpy.Event = None  # will be emitted once we're done

    def __init__(self, mmodel: MarkovModel, env: simpy.Environment, msg_queue_client: simpy.resources.store.Store, msg_queue_server: simpy.resources.store.Store, parent_flow: int, id: int) -> None:
        self.mmodel = mmodel
        self.msg_queue_client = msg_queue_client
        self.msg_queue_server = msg_queue_server
        self.parent_flow = parent_flow
        self.id = id
        self.num_cells_sent = 0
        self.completed = env.event()
        # register 'run' as process
        self.process = env.process(self.run(env))

    def run(self, env: simpy.Environment) -> None:

        while True:
            # grab the next observation from markov model
            delay_microseconds, obs_type = self.mmodel.getNextObservation()

            # the msg queue into which we will insert data
            queue: simpy.resources.store.Store = None

            # check the obs_type
            if obs_type == "OBSERVATION_TO_ORIGIN":
                # insert into server queue
                queue = self.msg_queue_server
                # NOTE the 'delay' argument to env.timeout(delay) does not have a unit as such, so let's decide we regard it as microseconds
                yield env.timeout(delay_microseconds)
            elif obs_type == "OBSERVATION_TO_SERVER":
                # insert into client queue
                queue = self.msg_queue_client
                # sleep for delay_microseconds microseconds
                yield env.timeout(delay_microseconds)
            elif obs_type == "OBSERVATION_END":
                # we have reached the end, exit
                print(
                    f"Stream with id {self.id}, which was created by flow with id {self.parent_flow}, has finished!")

                self.completed.succeed()

                break
            # this shouldn't happen
            else:
                print("Got a non-packet model observation from the Markov model!")

            # insert into queue
            if queue is not None:

                # this is apparently ceiling division
                num_cells = -(TGEN_MMODEL_PACKET_DATA_SIZE // -(PAYLOAD_LEN))

                for _ in range(num_cells):

                    header = f"DATA|{self.parent_flow}|{self.id}|{self.num_cells_sent}|".encode(
                    )

                    # increment number of cells sent on this stream
                    self.num_cells_sent += 1

                    header += b'\x00' * (HEADER_LEN - len(header))

                    payload = b'\x00' * PAYLOAD_LEN

                    msg = Message(header + payload, env)

                    yield queue.put(msg)
