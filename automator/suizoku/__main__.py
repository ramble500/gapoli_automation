from dotenv import load_dotenv

from automator.utils.initial import initial_action

load_dotenv(verbose=True)

import argparse
import datetime
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from selenium.common.exceptions import NoSuchWindowException
from selenium.webdriver.common.by import By

from automator.login import Controller
from automator.suizoku.outside_action import focus_main_window, reset_suizoku
from automator.suizoku.tick import start_ticker
from automator.utils.detect import cv2pil
from automator.utils.error_reporter import ErrorReporter
from automator.utils.influx import init_influx, write_influx
from automator.utils.template import ImageMatcher, TemplateImage, vectorizer

from . import const

load_dotenv(verbose=True, override=True)
init_influx()

parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", default="INFO")
parser.add_argument("--no-continue", action="store_true", help="引き直しをしない")
parser.add_argument("--clearing-start", action="store_true", help="初回に清算する")
parser.add_argument(
    "--no-condition",
    action="store_true",
    help="水曜日のチャンスタイムでなくても実行する",
)
parser.add_argument("--no-low-exit", action="store_true", help="低設定チェックを飛ばす")
parser.add_argument("--reroll-count", type=int, default=999, help="何回まで引き直すか")
parser.add_argument("--rate", type=int, choices=[20, 100], default=100)


args = parser.parse_args()

NO_CONTINUE = args.no_continue
const.RATE = args.rate
const.REROLL_COUNT = args.reroll_count
const.NO_CONDITION = args.no_condition
const.NO_LOW_EXIT = args.no_low_exit

logging.basicConfig(level=args.loglevel.upper())
logging.getLogger().setLevel(args.loglevel.upper())
logger = logging.getLogger(__name__)

logger.info(f"rate: {const.RATE}")

LOGIN_ID = os.environ.get("LOGIN_ID")
PASSWORD = os.environ.get("PASSWORD")
logger.info(LOGIN_ID)

c = Controller(headless=False)

with ErrorReporter(c):
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
    c.wait_random()

    resumed_games = initial_action(c)
    newgame = "箱絵巻 まんぷくすいぞくかん" not in resumed_games
    if newgame:
        c.wait_loaded()
        c.wait_random()
        reset_suizoku(c)

    for i in range(5):
        try:
            focus_main_window(c)
        except:
            time.sleep(2)
        else:
            break

    start_ticker(c, auto=True, newgame=newgame)
