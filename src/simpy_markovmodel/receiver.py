import simpy


class Receiver(object):

    # network will be 'network_outward' or 'network_inward' depending on whether this is the server- or client-side receiver
    network: simpy.resources.store.Store = None
    # role = 'client' resp. 'server'
    participant: str = None

    def __init__(self, env: simpy.Environment, network: simpy.resources.store.Store, participant: str) -> None:
        self.network = network
        self.participant = participant

       # register 'run' as process
        self.process = env.process(self.run(env))

    def run(self, env: simpy.Environment) -> None:

        while True:

            # fetch incoming data
            msg = yield self.network.get()

            msg_decoded = msg.decode()

            # reconstruct the 'cell'/'message' from received bytestream
            # and respond appropriately (do nothing if msg starts with PADDING,
            # and send data if it starts with a web address)
            msg_chunks = msg_decoded.split('|')

            msg_type = msg_chunks[0]

            if msg_type == "PADDING":

                # print(f"[{env.now}] {self.participant} received dummy")
                pass

            elif msg_type == "DATA":

                # print(f"[{env.now}] {self.participant} received data from flow with id {msg_chunks[1]}, stream with id {msg_chunks[2]}, cell number {msg_chunks[3]}")
                pass

            else:

                # print(f"[{env.now}] {self.participant} received unknown msg type")
                pass
