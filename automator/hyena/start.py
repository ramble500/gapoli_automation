import logging
import sys

from dotenv import load_dotenv

from automator.hyena import ss_hokuto_musou

load_dotenv(verbose=True)

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--loglevel", default="INFO")

args = parser.parse_args()

logging.basicConfig(level=args.loglevel.upper())
logging.getLogger().setLevel(args.loglevel.upper())
logger = logging.getLogger(__name__)


import datetime
import os
import time

from automator.hyena.utils import enter_pachi_menu
from automator.login import Controller
from automator.utils.error_reporter import ErrorReporter
from automator.utils.initial import initial_action

if __name__ == "__main__":

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

        enter_pachi_menu(c)

        # 巡回対象ホール名
        from automator.hyena import codegeass, dunbine, kizu

        halls = ["ニューワン", "チャレンジスリー", "ビッグファイブ", "ビクトリーテン"]

        for i in range(100):
            # for hall in ["ニューワン", "チャレンジスリー", "ビッグファイブ", "ビクトリーテン"]:
            #     logger.info(f"ホール: {hall}")
            #     c.driver.switch_to.default_content()
            #     c.scroll_into(f"//span[contains(@class, '_storeName_')][contains(text(), '{hall}')]")
            #     c.wait_random()
            #
            #     c.click_it(f"//span[contains(@class, '_storeName_')][contains(text(), '{hall}')]")
            #     c.click_it(f"//button[contains(text(), '入店する')]")

            #     # 台を選択へ
            #     ss_hokuto_musou.main(c, hall)

            #     # svgはうまく選択できないので
            #     c.driver.switch_to.default_content()
            #     c.wait_it("//span[contains(@class, '_storeNameFont_')]/preceding-sibling::*")
            #     c.click_it("//span[contains(@class, '_storeNameFont_')]/preceding-sibling::*")
            #     logger.info(f"ホール: {hall} おわり")

            for hall in halls:
                logger.info(f"ホール: {hall}")
                c.driver.switch_to.default_content()
                c.scroll_into(
                    f"//span[contains(@class, '_storeName_')][contains(text(), '{hall}')]"
                )
                c.wait_random()

                c.click_it(
                    f"//span[contains(@class, '_storeName_')][contains(text(), '{hall}')]"
                )
                c.click_it(f"//button[contains(text(), '入店する')]")

                # 台を選択へ
                ss_hokuto_musou.main(c, hall)
                kizu.main(c, hall)
                codegeass.main(c, hall)
                if hall == "ビクトリーテン":
                    dunbine.main(c, hall)

                # svgはうまく選択できないので
                c.driver.switch_to.default_content()
                c.wait_it(
                    "//span[contains(@class, '_storeNameFont_')]/preceding-sibling::*"
                )
                c.click_it(
                    "//span[contains(@class, '_storeNameFont_')]/preceding-sibling::*"
                )
                logger.info(f"ホール: {hall} おわり")

            d = datetime.datetime.now()
            minute = (d.minute // 15 + 1) * 15
            if minute == 60:
                d = d.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(
                    hours=1
                )
            else:
                d = d.replace(minute=minute, second=0, microsecond=0)

            logger.info(f"Wait until {d}")
            while datetime.datetime.now() < d:
                time.sleep(5)
            logger.info(f"Wait End")
