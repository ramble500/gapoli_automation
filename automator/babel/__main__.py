from dotenv import load_dotenv

load_dotenv(verbose=True, override=True)

import argparse
import datetime
import logging
import os
import sys

from selenium.common.exceptions import NoSuchWindowException
from selenium.webdriver.common.by import By

parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", default="INFO")
parser.add_argument("--no-continue", action="store_true")

args = parser.parse_args()

NO_CONTINUE = args.no_continue

logging.basicConfig(level=args.loglevel.upper())
logging.getLogger().setLevel(args.loglevel.upper())
logger = logging.getLogger(__name__)


import time

from selenium.webdriver.common.by import ByType

from automator.babel.main import tick
from automator.login import Controller
from automator.utils.influx import init_influx, write_influx

init_influx()

LOGIN_ID = os.environ.get("LOGIN_ID")
PASSWORD = os.environ.get("PASSWORD")


c = Controller()
c.login("https://gapoli.net/play")

c.wait_loaded()

c.click_it('//button[text()="ログイン"]')
c.wait_random()

c.input_text('//input[@id="loginID"]', LOGIN_ID)
c.wait_random()

c.input_text('//input[@id="loginPassword"]', PASSWORD)
c.wait_random()

c.click_it('//button[text()="ログイン"]')
c.wait_loaded()

try:
    try:
        c.click_it('//button[text()="スキップ"]')
    except:
        c.click_it('//button[text()="復帰する"]')

    try:
        while True:
            c.click_it('//button[text()="OK"]')
            time.sleep(0.5)
    except:
        pass

    try:
        c.click_it('//button[text()="スキップ"]')
    except:
        pass
    c.wait_loaded()

    c.click_it('//div[contains(@class, "closeContainer")]')
except:
    pass

# c.click_target_by_image("targets/medal_target.png")
# c.wait_random(3)

# c.click_target_by_image("targets/medaltower_game.png")

c.driver.switch_to.default_content()
if1 = c.driver.find_element(
    By.XPATH, '//div[contains(@class, "_controllerContainer_")]//iframe'
)
c.driver.switch_to.frame(if1)

if2 = c.driver.find_element(By.XPATH, "//iframe")
c.driver.switch_to.frame(if2)
logger.info("READY")

init_influx()

keep_alive = 0
while True:
    try:
        if keep_alive < time.time():
            c.click_relative_pos((0.999, 0.999), "//video")
            keep_alive = time.time() + 200
        tick(c, no_continue=NO_CONTINUE)
        time.sleep(0.1)
    except KeyboardInterrupt:
        c.close()
        raise
    except NoSuchWindowException:
        c.close()
        raise
    except:
        from selenium.webdriver.common.by import By

        log_path = f"./log/failed_screen/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if c.last_ss:
            c.save_ss(log_path, c.last_ss)
            logger.exception("Failed Screen: %s", log_path)
        # write_influx(
        #     "error", {
        #         "traceback": traceback.format_exc()
        #     }
        # )
        try:
            c.driver.switch_to.default_content()
            if1 = c.driver.find_element(
                By.XPATH, '//div[contains(@class, "_controllerContainer_")]//iframe'
            )
            c.driver.switch_to.frame(if1)

            if2 = c.driver.find_element(By.XPATH, "//iframe")
            c.driver.switch_to.frame(if2)
        except:
            logger.exception("Failed Move to Video Screen: %s", log_path)
            time.sleep(5)
