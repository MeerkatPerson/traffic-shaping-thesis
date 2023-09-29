import simpy

# the parent class of our different message emitters
# TODO make abstract?


class MessageEmitter(object):

    env: simpy.Environment = None
    dir: str = None
    msg_queue: simpy.resources.store.Store = None
    filename: str = None
    participant: str = None  # client or server
    # how many streams do we expect? This info is used to know when to shut down (i.e., once num_streams/num_streams streams have finished). If we didn't have a mechanism shutting message emitters down once all data has been transferred, they'd continue infinitely in some scenarios (e.g., Loopix)
    num_streams: int = None

    def __init__(self, env: simpy.Environment, dir: str, msg_queue: simpy.resources.store.Store, participant: str, num_streams: int) -> None:

        self.env = env
        self.dir = dir
        self.msg_queue = msg_queue
        self.participant = participant
        self.num_streams = num_streams
