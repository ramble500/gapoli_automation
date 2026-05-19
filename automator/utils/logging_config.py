import datetime
import logging
from pathlib import Path


def setup_file_logging(loglevel: str, name: str) -> Path:
    log_dir = Path("./log/run_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    log_path = log_dir / f"{name}_{timestamp}.log"
    level = getattr(logging, loglevel.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(name)s:%(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=level,
        handlers=[stream_handler, file_handler],
        force=True,
    )
    logging.getLogger().setLevel(level)
    logging.getLogger(__name__).info("log file: %s", log_path)

    return log_path
