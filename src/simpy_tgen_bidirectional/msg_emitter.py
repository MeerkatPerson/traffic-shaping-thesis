import simpy

# the parent class of our different message emitters
# TODO make abstract?


class MessageEmitter(object):

    env: simpy.Environment = None
    dir: str = None
    network: simpy.resources.store.Store = None
    msg_queue: simpy.resources.store.Store = None
    filename: str = None
    participant: str = None  # client or server

    def __init__(self, env: simpy.Environment, dir: str, network: simpy.resources.store.Store, msg_queue: simpy.resources.store.Store, participant: str) -> None:

        self.env = env
        self.dir = dir
        self.network = network
        self.msg_queue = msg_queue
        self.participant = participant
