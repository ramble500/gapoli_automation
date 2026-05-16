import argparse
import logging

parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", default="INFO")

args = parser.parse_args()

logging.basicConfig(level=args.loglevel.upper())
logging.getLogger().setLevel(args.loglevel.upper())

logger = logging.getLogger(__name__)
logger.error("TEST1")
logger.warning("TEST2")
logger.info("TEST3")
logger.debug("TEST4")
