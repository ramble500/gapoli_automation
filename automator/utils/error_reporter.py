import datetime
import logging
import os
import traceback
from types import TracebackType

from automator.login import Controller
from automator.utils.recovery import CommunicationErrorRecovered

logger = logging.getLogger(__name__)


class ErrorReporter:
    c: Controller

    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, trace: TracebackType):
        if ex_type is not None and issubclass(ex_type, CommunicationErrorRecovered):
            return False
        if trace is not None:
            log_path = f"./log/error_reports/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}/"
            os.makedirs(log_path, exist_ok=True)

            try:
                with open(log_path + "error.txt", "w", encoding="utf8") as f:
                    f.write("".join(traceback.format_exception(ex_type, ex_value, trace)))
            except Exception:
                logger.exception("failed to write error traceback: %s", log_path + "error.txt")

            screenshot_path = log_path + "ss.png"
            try:
                self.c.save_ss(screenshot_path, self.c.take_photo())
            except Exception:
                logger.exception("failed to save failed-screen screenshot: %s", screenshot_path)

            logger.error(
                "Failed Screen: %s",
                screenshot_path,
                exc_info=(ex_type, ex_value, trace),
            )

            try:
                dom_tree = self.c.get_dom()
                with open(log_path + "dom.txt", "w", encoding="utf8") as f:
                    f.write(dom_tree)
            except Exception:
                logger.exception("failed to save failure DOM: %s", log_path + "dom.txt")

        return False
