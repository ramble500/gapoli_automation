import datetime
import json
import time
from typing import List, Optional


class StateLogger:

    states: List[(float, dict)]

    def __init__(self):
        self.states = []
        self.start_time = None
        self.start_timestamp = None

    def start(self):
        self.start_time = time.time()
        self.start_timestamp = datetime.datetime.now()

    def add_state(self, obj: dict):
        t = time.time() - self.start_time
        self.states.append((t, obj))

    def save(self, path: Optional[str] = None):
        if path is None:
            path = "log/states/" + self.start_timestamp.fromisoformat() + ".log"
        with open(path, "w") as f:
            json.dump(self.states, f)
            self.states = []
