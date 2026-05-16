import logging
import time
from typing import List

from automator.login import Controller

logger = logging.getLogger(__name__)


def initial_action(c: Controller) -> List[str]:
    resumed_games = []

    try:
        while True:
            c.click_it('//div[contains(@class, "_oKButton")]', timeout=3)
            logger.info("ログボスキップ")
            time.sleep(0.5)
    except:
        pass

    while True:
        el = c.get_element(
            '//div/div/span[text()[contains(.,"中断されたゲームがあります")]]'
        )

        if el is not None:
            game_name = c.get_element(
                '//div/div/span[text()[contains(.,"中断されたゲームがあります")]]/../../../descendant::span[2]'
            ).text
            c.click_it(
                '//div/div/span[text()[contains(.,"中断されたゲームがあります")]]/../../../descendant::button[text()="復帰する"]'
            )
            logger.info("中断復帰: %s", game_name)
            resumed_games.append(game_name.strip())
            c.wait_random()
        else:
            break

    try:
        c.wait_random()
        while True:
            c.click_it('//div[contains(@class, "_oKButton")]', timeout=3)
            logger.info("ログボスキップ")
            time.sleep(0.5)
    except:
        pass

    el = c.get_element('//div/div/span[text()[contains(.,"GAPOLIの遊び方")]]')
    if el is not None:
        c.click_it(
            '//div/div/span[text()[contains(.,"GAPOLIの遊び方")]]/../../../descendant::button[text()="スキップ"]'
        )
        logger.info("GAPOLIの遊び方スキップ ")
        c.wait_random()

    try:
        c.wait_random()
        while True:
            c.click_it('//div[contains(@class, "_oKButton")]', timeout=3)
            logger.info("ログボスキップ")
            time.sleep(0.5)
    except:
        pass

    el = c.get_element(
        '//div/div/span[text()[contains(.,"GAPOLIをデスクトップに追加")]]'
    )
    if el is not None:
        c.click_it(
            '//div/div/span[text()[contains(.,"GAPOLIをデスクトップに追加")]]/../../../descendant::div[contains(@class, "closeContainer")]'
        )
        logger.info("GAPOLIをデスクトップに追加を閉じる ")
        c.wait_random()

    return resumed_games
