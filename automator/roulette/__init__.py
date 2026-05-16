from dotenv import load_dotenv

load_dotenv(verbose=True)

import argparse
import logging
import os
import time

from automator.login import Controller
from automator.roulette.automated import loop
from automator.utils.influx import init_influx, write_influx

load_dotenv(verbose=True, override=True)
init_influx()

parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", default="INFO")
parser.add_argument("--loop-count", type=int, default=999, help="何回まで引き直すか")
parser.add_argument(
    "--mode",
    type=str,
    choices=["win", "spin"],
    default="win",
    help="なにを稼ぐか(spinなら清算せずに1コインを続ける)",
)


args = parser.parse_args()

logging.basicConfig(level=args.loglevel.upper())
logging.getLogger().setLevel(args.loglevel.upper())
logger = logging.getLogger(__name__)

LOGIN_ID = os.environ.get("LOGIN_ID")
PASSWORD = os.environ.get("PASSWORD")
logger.info(LOGIN_ID)

c = Controller(headless=False)
c.login("https://gapoli.net/play")

c.wait_loaded()
logger.info("loaded")

c.click_it('//button[text()="ログイン"]')
c.wait_random()

c.input_text('//input[@id="loginID"]', LOGIN_ID)
c.wait_random()

c.input_text('//input[@id="loginPassword"]', PASSWORD)
c.wait_random()

c.click_it('//button[text()="ログイン"]')
c.wait_loaded()

newgame = True
try:
    c.click_it('//button[text()="スキップ"]', timeout=5)
except:
    time.sleep(5)
    try:
        c.click_it('//button[text()="精算する"]')
        c.click_it('//button[text()="閉じる"]')
    except:
        pass


try:
    while True:
        c.click_it('//div[contains(@class, "_oKButton")]', timeout=3)
        time.sleep(0.5)
except:
    pass

try:
    c.click_it('//button[text()="スキップ"]', timeout=3)
except:
    pass

try:
    while True:
        c.click_it('//div[contains(@class, "_oKButton")]', timeout=3)
        time.sleep(0.5)
except:
    pass


c.click_it('//div[contains(@class, "closeContainer")]')


loop(c, loop_count=args.loop_count, mode=args.mode)
