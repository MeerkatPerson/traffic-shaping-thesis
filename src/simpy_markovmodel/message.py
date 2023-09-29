from datetime import datetime
import simpy


class Message():

    content: bytes = None
    created: datetime = None
    sent: datetime = None

    def __init__(self, content: bytes, env: simpy.Environment) -> None:
        self.content = content
        self.created = env.now
