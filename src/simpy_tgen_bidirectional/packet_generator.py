import simpy
from globals import HEADER_LEN, PAYLOAD_LEN
from message import Message
from typing import Dict

# basically represents a stream


class PacketGenerator(object):

    env: simpy.Environment = None
    tmodel: Dict = None
    msg_queue_client: simpy.resources.store.Store = None
    msg_queue_server: simpy.resources.store.Store = None
    id: int = None
    num_outward_cells_sent: int = None
    num_inward_cells_sent: int = None

    def __init__(self, env: simpy.Environment, tmodel: Dict, msg_queue_client: simpy.resources.store.Store, msg_queue_server: simpy.resources.store.Store, id: int) -> None:
        self.env = env
        self.tmodel = tmodel
        self.msg_queue_client = msg_queue_client
        self.msg_queue_server = msg_queue_server
        self.id = id
        self.num_outward_cells_sent = 0
        self.num_inward_cells_sent = 0
        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        for emission_key, emission_val in self.tmodel.items():

            delay = emission_key[1]

            # now, 'emission_key' is our inter-emission-delay.
            yield self.env.timeout(delay)

            for sending_event in emission_val:

                bytes_to_send = sending_event['bytes']

                # this is apparently ceiling division
                num_cells = -(bytes_to_send // -(PAYLOAD_LEN))

                if sending_event['direction'] == 'TO_SERVER':

                    for _ in range(num_cells):

                        # increment number of cells sent on this stream
                        self.num_outward_cells_sent += 1

                        header = f"DATA|{self.id}|{self.num_outward_cells_sent}|".encode(
                        )

                        header += b'\x00' * (HEADER_LEN - len(header))

                        payload = b'\x00' * PAYLOAD_LEN

                        msg = Message(header + payload, self.env)

                        yield self.msg_queue_client.put(msg)

                elif sending_event['direction'] == 'TO_ORIGIN':

                    for _ in range(num_cells):

                        # increment number of cells sent on this stream
                        self.num_inward_cells_sent += 1

                        header = f"DATA|{self.id}|{self.num_inward_cells_sent}|".encode(
                        )

                        header += b'\x00' * (HEADER_LEN - len(header))

                        payload = b'\x00' * PAYLOAD_LEN

                        msg = Message(header + payload, self.env)

                        yield self.msg_queue_server.put(msg)

                else:

                    print("Unknown sending event direction!")

        # finish: send an END-cell [in both directions, slightly ugly but this is how we can let both receiver processes know the stream has finished]
        header = f"END|{self.id}|".encode(
        )

        header += b'\x00' * (HEADER_LEN - len(header))

        payload = b'\x00' * PAYLOAD_LEN

        msg = Message(header + payload, self.env)

        yield self.msg_queue_server.put(msg) & self.msg_queue_client.put(msg)

        print(
            f"Stream with ID {self.id} has finished! Sent {self.num_outward_cells_sent} in the outward-, {self.num_inward_cells_sent} in the inward direction!")
