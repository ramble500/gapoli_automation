import datetime
import logging
from pathlib import Path
from typing import List

from automator.login import Controller

logger = logging.getLogger(__name__)


def get_seats_info(c: Controller):
    def take_fiber(c, el):
        script = """
        for (const key in arguments[0]) {
            if (key.startsWith('__reactFiber$')) {
                const fiberNode = arguments[0][key];
                console.log(fiberNode)
                return fiberNode.memoizedProps.children.map(x => x.props.children.props)
            }
        }
        """
        return c.driver.execute_script(script, el)

    el = c.get_element('//div[contains(@class, "_machineListContainer")]')
    return take_fiber(c, el)


def block_everyone(c: Controller):
    els = c.get_elements('//div[contains(@class, "AvatarIconContainer")]')
    for item in els:
        c.click_element(item)

        el = c.wait_it(
            '//div[contains(@class, "_relative_")]/div/button[contains(@class, "menu-button")]'
        )
        c.wait_random()
        c.click_it(
            '//div[contains(@class, "_relative_")]/div/button[contains(@class, "menu-button")]'
        )

        el = c.wait_it('//span[contains(text(), "ブロック")]')
        c.click_element(el)

        el = c.wait_it(
            '//button[contains(@class, "applyButton")][contains(text(), "ブロック")]'
        )
        c.click_element(el)

    return len(els)


def get_window_info(c: Controller):
    c.driver.switch_to.default_content()

    def take_fiber(c, el):
        script = """
        for (const key in arguments[0]) {
            if (key.startsWith('__reactFiber$')) {
                const fiberNode = arguments[0][key];
                console.log(fiberNode)
                return fiberNode.memoizedProps.children[1].props
            }
        }
        """
        return c.driver.execute_script(script, el)

    els = c.get_elements(
        '//div[contains(@class, "red")]//div[contains(@class, "relative")]'
    )
    return [take_fiber(c, item) for item in els]


def focus_main_window(c: Controller, window_id: int):
    c.driver.switch_to.default_content()

    if1 = c.get_elements(
        '//div[contains(@class, "red")]//div[contains(@class, "_controllerContainer_")]//iframe'
    )
    c.driver.switch_to.frame(if1[window_id])

    if2 = c.get_element("//iframe")
    c.driver.switch_to.frame(if2)

    c.wait_it("//video")

    ss = c.take_image_from_video("//video")


def finish_pachi_game(c: Controller, win_id: int, hall: str):
    # 精算する
    c.driver.switch_to.default_content()

    finish_buttons = c.get_elements(
        '//div[contains(@class, "red")]//div[contains(@class, "checkButtonWrapper")]'
    )
    finish_buttons[win_id].click()
    c.wait_random()

    el = c.get_element('//div/div/span[text()[contains(.,"現在の状況")]]')
    if el is not None:
        c.click_it(
            '//div/div/span[text()[contains(.,"現在の状況")]]/../../../descendant::button[text()="精算"]'
        )
        logger.info("精算！")
        c.wait_random()

    el = c.get_element(
        '//div/div/span[text()[contains(.,"ゲームを終了して精算しますか？")]]'
    )
    if el is not None:
        c.click_it(
            '//div/div/span[text()[contains(.,"ゲームを終了して精算しますか？")]]/../../../descendant::button[text()="精算"]'
        )
        logger.info("精算！")
        c.wait_random()

    # 精算後ダイアログ
    result_path = (
        f"./log/result_ss/pachi_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    )
    Path(result_path).parent.mkdir(parents=True, exist_ok=True)
    c.save_ss(result_path, c.take_photo())

    el = c.wait_it('//div[contains(@class, "_titleContainer_")]')
    if el is not None:
        if (
            c.get_element(
                '//div[contains(@class, "_titleContainer_")]/../../../descendant::button[text()="続けて遊ぶ"]'
            )
            is not None
        ):
            c.click_it(
                '//div[contains(@class, "_titleContainer_")]/../../../descendant::button[text()="続けて遊ぶ"]'
            )
            logger.info("続けて遊ぶ！")
        else:
            c.click_it(
                '//div[contains(@class, "_titleContainer_")]/../../../descendant::span[text()="店舗選択に戻る"]'
            )
            logger.info("店舗選択に戻る")
            c.wait_random()
            enter_hall(c, hall)


def enter_hall(c: Controller, hall: str):
    logger.info(f"ホール: {hall}")
    c.driver.switch_to.default_content()
    c.scroll_into(
        f"//span[contains(@class, '_storeName_')][contains(text(), '{hall}')]"
    )
    c.wait_random()

    c.click_it(f"//span[contains(@class, '_storeName_')][contains(text(), '{hall}')]")
    c.click_it(f"//button[contains(text(), '入店する')]")


import pickle

from automator.utils.template import ImageMatcher

with open("pachi-button.pkl", "rb") as f:
    pachi_template = pickle.load(f)


def enter_pachi_menu(c: Controller):

    windows = c.get_elements('//div[contains(@style, "position: fixed;")]')
    logger.info(f"HIDE {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display='none'", el)

    m = ImageMatcher()
    point = m.click_point(pachi_template, c.take_photo())

    logger.info(f"point: {point}")
    c.click_pos(point, no_mult=False)
    c.wait_random()
    if (
        c.get_element(
            "//div[contains(@class, '_overLayer_')]//button[contains(@class, '_close_')]"
        )
        is not None
    ):
        c.click_it(
            "//div[contains(@class, '_overLayer_')]//button[contains(@class, '_close_')]"
        )

    windows = c.get_elements('//div[contains(@style, "position: fixed;")]')
    logger.info(f"SHOW {len(windows)} window elements")
    for el in windows:
        c.driver.execute_script("arguments[0].style.display=''", el)


def take_store(c):
    c.driver.switch_to.default_content()
    script = """
        return (function() {
            if (window.__$TQ3XJJj5mk$__STORE) {
                return window.__$TQ3XJJj5mk$__STORE.getState();
            }
            const findReduxStore = function(fiber) {
                if (!fiber) return null;
                if (fiber.type && fiber.memoizedProps?.store) {
                    window.__$TQ3XJJj5mk$__STORE = fiber.memoizedProps.store
                    return fiber.memoizedProps.store.getState();
                }
                
                return (
                    findReduxStore(fiber.child) ||
                    findReduxStore(fiber.sibling)
                );
            }                
            const rootEl = document.querySelector("#root") || document.body;
            for (const key in rootEl) {
                if (key.startsWith("__reactContainer") || key.startsWith("__reactFiber$")) {
                    return findReduxStore(rootEl[key]);
                }
            }
        })()["game"]["yongou"]["yongouGames"]
    """
    return c.driver.execute_script(script)
