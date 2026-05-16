import datetime
import logging
import time
from pathlib import Path

from selenium.webdriver.common.by import By

from automator.login import Controller
from automator.utils.initial import initial_action

from . import const

logger = logging.getLogger(__name__)
logger.info("Logger initialized!")


def reset_suizoku(c: Controller):
    # すいぞくかんを精算
    c.driver.switch_to.default_content()

    windows = c.get_elements(
        '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
    )
    logger.info(f"HIDE {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display='none'", el)

    c.login("https://gapoli.net/game/20266")
    c.wait_loaded()

    initial_action(c)
    c.wait_loaded()
    c.wait_random()

    windows = c.get_elements(
        '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
    )
    logger.info(f"HIDE {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display='none'", el)

    c.click_it('//button[text()="プレイ"]')
    c.click_it('//div[contains(@class, "_pulldown")]')

    c.click_it(
        f'//div[contains(@class, "_pullDownItem")]//span[contains(text(), "{const.RATE}")]'
    )
    c.click_it('//button[text()="レート決定"]')

    c.wait_it(xpath='//span[text()="メダル交換"]', timeout=30)

    c.click_it('//div[contains(@class, "_pulldown")]')
    c.click_it(
        '//div[contains(@class, "_pullDownItem")]//span[contains(text(), "100")]'
    )
    c.click_it('//button[text()="プレイ開始"]')

    # 裏の大きいのを消しておく
    windows = c.get_elements('//div[contains(@style, "position: fixed;")]')
    logger.info(f"HIDE {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display='none'", el)

    el = c.get_element('//div[contains(@class, "closeIconOuter")]')
    if el is not None:
        c.click_it('//div[contains(@class, "closeIconOuter")]')
        logger.info("大きいのを消す")

    c.wait_random()

    el = c.get_element(
        '//div[contains(@class, "searchContainer")]/div[contains(@class, "iconWrapper")]'
    )
    if el is not None:
        c.click_it(
            '//div[contains(@class, "searchContainer")]/div[contains(@class, "iconWrapper")]'
        )
        logger.info("大きいのを消す2")

    windows = c.get_elements(
        '//div[contains(@class, "blue")]/div[contains(@style, "position: fixed;")]'
    )
    logger.info(f"SHOW {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display=''", el)

    windows = c.get_elements(
        '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
    )
    logger.info(f"SHOW {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display=''", el)

    time.sleep(3)

    focus_main_window(c)
    logger.info("入場完了")


def finish_game(c: Controller, final=False):
    # 精算する
    c.driver.switch_to.default_content()

    windows = c.get_elements(
        '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
    )
    logger.info(f"HIDE {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display='none'", el)

    c.wait_it(
        '//div[contains(@class, "blue")]//div[contains(@class, "checkButtonWrapper")]'
    )
    c.click_it(
        '//div[contains(@class, "blue")]//div[contains(@class, "checkButtonWrapper")]'
    )
    c.wait_random()

    el = c.wait_it('//div/div/span[text()[contains(.,"精算確認")]]')
    if el is not None:
        c.click_it(
            '//div/div/span[text()[contains(.,"精算確認")]]/../../../descendant::button[text()="精算"]'
        )
        logger.info("精算！")
        c.wait_random()

    # 精算後ダイアログ
    el = c.get_element(
        '//div/div/span[text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]'
    )
    result_path = f"./log/result_ss/suizoku_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    Path(result_path).parent.mkdir(parents=True, exist_ok=True)
    c.save_ss(result_path, c.take_photo())
    if final:
        return

    if el is not None:
        c.click_it(
            '//div/div/div/span[text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]/../../../../descendant::button[text()="続けて遊ぶ"]'
        )
        logger.info("続けて遊ぶ！")
        c.wait_random()

    c.wait_it(
        '//span[contains(@class, "gameTitle")][text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]'
    )
    c.click_it(
        '//span[contains(@class, "gameTitle")][text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]'
    )
    logger.info("入場")
    c.wait_random()

    c.click_it('//button[text()="プレイ"]')
    c.click_it('//div[contains(@class, "_pulldown")]')

    c.click_it(
        f'//div[contains(@class, "_pullDownItem")]//span[contains(text(), "{const.RATE}")]'
    )
    c.click_it('//button[text()="レート決定"]')

    c.wait_it(xpath='//span[text()="メダル交換"]', timeout=30)
    c.wait_random()

    c.click_it('//div[contains(@class, "_pulldown")]')
    c.click_it(
        '//div[contains(@class, "_pullDownItem")]//span[contains(text(), "100")]'
    )
    c.wait_random()

    c.click_it('//button[text()="プレイ開始"]')

    windows = c.get_elements(
        '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
    )
    logger.info(f"SHOW {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display=''", el)

    time.sleep(5)

    focus_main_window(c)
    logger.info("入場完了")


def detect_window(c: Controller, final=False):
    c.driver.switch_to.default_content()
    if (
        c.get_element(
            '//div[not(contains(@class, "blue"))]//*[text()[contains(.,"プレイ回数が上限に")]]'
        )
        is not None
    ):
        logger.info("精算します")
        windows = c.get_elements(
            '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
        )
        logger.info(f"HIDE {len(windows)} window elements")
        for el in windows:
            c.driver.execute_script("arguments[0].style.display='none'", el)

        c.click_it('//button[text()="精算"]')
        c.click_it(
            '//button[text()="キャンセル"]/preceding-sibling::button[text()="精算"]'
        )
        c.click_it('//button[text()="精算"]')

        # 精算後ダイアログ
        el = c.get_element(
            '//div/div/span[text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]'
        )
        result_path = f"./log/result_ss/suizoku_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        Path(result_path).parent.mkdir(parents=True, exist_ok=True)
        c.save_ss(result_path, c.take_photo())
        if final:
            return

        c.click_it('//button[text()="続けて遊ぶ"]')

        windows = c.get_elements(
            '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
        )
        logger.info(f"HIDE {len(windows)} window elements")
        for el in windows:
            c.driver.execute_script("arguments[0].style.display='none'", el)

        c.wait_it(
            '//span[contains(@class, "gameTitle")][text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]'
        )
        c.click_it(
            '//span[contains(@class, "gameTitle")][text()[contains(.,"箱絵巻 まんぷくすいぞくかん")]]'
        )
        logger.info("入場")
        c.wait_random()

        c.click_it('//button[text()="プレイ"]')
        c.click_it('//div[contains(@class, "_pulldown")]')

        c.click_it(
            f'//div[contains(@class, "_pullDownItem")]//span[contains(text(), "{const.RATE}")]'
        )
        c.click_it('//button[text()="レート決定"]')

        c.wait_it(xpath='//span[text()="メダル交換"]', timeout=30)
        c.wait_random()

        c.click_it('//div[contains(@class, "_pulldown")]')
        c.click_it(
            '//div[contains(@class, "_pullDownItem")]//span[contains(text(), "100")]'
        )
        c.wait_random()

        c.click_it('//button[text()="プレイ開始"]')

        windows = c.get_elements(
            '//div[not(contains(@class, "blue"))]/div[contains(@style, "position: fixed;")]'
        )
        logger.info(f"SHOW {len(windows)} window elements")
        for el in windows:
            c.driver.execute_script("arguments[0].style.display=''", el)

        time.sleep(5)

        focus_main_window(c)
        logger.info("入場完了")
        return True
    else:
        focus_main_window(c)
        return False


def focus_main_window(c: Controller):
    c.driver.switch_to.default_content()

    # blueはメダルで、メダルはこれしか起動してない前提
    if1 = c.driver.find_element(
        By.XPATH,
        '//div[contains(@class, "blue")]//div[contains(@class, "_controllerContainer_")]//iframe',
    )
    c.driver.switch_to.frame(if1)

    if2 = c.driver.find_element(By.XPATH, "//iframe")
    c.driver.switch_to.frame(if2)

    ss = c.take_image_from_video("//video")
