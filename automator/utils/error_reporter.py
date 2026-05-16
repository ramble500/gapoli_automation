import datetime
import os
import traceback
from types import TracebackType
from venv import logger

from automator.login import Controller


class ErrorReporter:
    c: Controller

    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, trace: TracebackType):
        if trace is not None:
            log_path = f"./log/error_reports/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}/"
            os.makedirs(log_path, exist_ok=True)
            self.c.save_ss(log_path + "ss.png", self.c.take_photo())
            with open(log_path + "error.txt", "w", encoding="utf8") as f:
                f.write(traceback.format_exc())
            logger.exception("Failed Screen: %s", log_path + "ss.png")

            dom_tree = self.c.get_dom()
            with open(log_path + "dom.txt", "w", encoding="utf8") as f:
                f.write(dom_tree)
