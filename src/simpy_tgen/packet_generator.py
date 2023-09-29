import simpy
from globals import HEADER_LEN, PAYLOAD_LEN
from message import Message
from typing import Dict

# basically represents a stream


class PacketGenerator(object):

    env: simpy.Environment = None
    # upstream (data arriving locally 'from the application' to be sent to the communication partner) vs. downstream (data arriving 'from the network', i.e., from the communication partner); only APE needs the latter
    kind: str = None
    tmodel: Dict = None
    msg_queue: simpy.resources.store.Store = None
    id: int = None
    num_cells_sent: int = None

    def __init__(self, env: simpy.Environment, kind: str, tmodel: Dict, msg_queue: simpy.resources.store.Store, participant: str, id: int) -> None:
        self.env = env
        self.kind = kind
        self.tmodel = tmodel
        self.msg_queue = msg_queue
        self.participant = participant
        self.id = id
        self.num_cells_sent = 0
        # register 'run' as process
        self.action = self.env.process(self.run())

    def run(self) -> None:

        for emission_key, num_bytes in self.tmodel.items():

            delay = emission_key[1]

            # now, 'emission_key' is our inter-emission-delay.
            yield self.env.timeout(delay)

            # this is apparently ceiling division
            num_cells = -(num_bytes // -(PAYLOAD_LEN))

            for _ in range(num_cells):

                # increment number of cells sent on this stream
                self.num_cells_sent += 1

                header = f"DATA|{self.id}|{self.num_cells_sent}|".encode(
                ) if self.kind == "upstream" else f"RCV|{self.id}|{self.num_cells_sent}|".encode(
                )

                header += b'\x00' * (HEADER_LEN - len(header))

                payload = b'\x00' * PAYLOAD_LEN

                msg = Message(header + payload, self.env)

                yield self.msg_queue.put(msg)

        # finish: send an END-cell
        header = f"END|{self.id}|".encode(
        )

        header += b'\x00' * (HEADER_LEN - len(header))

        payload = b'\x00' * PAYLOAD_LEN

        msg = Message(header + payload, self.env)

        yield self.msg_queue.put(msg)

        print(
            f"[{self.participant}] Stream with ID {self.id} has finished! Sent {self.num_cells_sent} cells!")
