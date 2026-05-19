import base64
import datetime
import json
import logging
import time
from pathlib import Path
from typing import List

from automator.login import Controller
from automator.utils.influx import write_influx
from automator.vslot.utils import shrink_window_if_clipped

logger = logging.getLogger(__name__)


def focus_main_window(c: Controller, game_type: str='green'):
    c.driver.switch_to.default_content()

    if1 = c.get_elements(f'//div[contains(@class, "{game_type}")]//iframe')
    c.driver.switch_to.frame(if1[0])

    c.wait_it("//canvas")


def finish_game(c: Controller, save_image: bool = True, from_dialog=False, is_bingo: bool=False, is_variety: bool=False, game_type: str='green'):
    # 精算する
    c.driver.switch_to.default_content()

    if not from_dialog:
        check_button_xpath = (
            f'//div[contains(@class, "{game_type}")]'
            '//div[contains(@class, "checkButtonWrapper") '
            'and not(contains(@class, "disabled")) '
            'and not(contains(@class, "item"))]'
        )
        c.wait_it(check_button_xpath, timeout=60)
        logger.info("click checkButtonWrapper")
        c.click_it(check_button_xpath)
        c.wait_random()
        el = c.wait_it('//div/div/span[text()[contains(.,"精算確認")]]', timeout=10)
    else:
        el = c.wait_it('//div/div/span[text()[contains(.,"精算確認")]]')

    c.wait_it(
        '//div/div/span[text()[contains(.,"精算確認")]]/../../../descendant::button[text()="精算"]'
    )
    c.click_it(
        '//div/div/span[text()[contains(.,"精算確認")]]/../../../descendant::button[text()="精算"]'
    )
    logger.info("精算！")
    c.wait_random()

    timeout = time.time() + 20  # 最大20秒

    while time.time() < timeout:
        # ① 次へ（最優先）
        next_button = c.get_element('//button[contains(normalize-space(.), "次へ")]')
        if next_button is not None:
            logger.info("『次へ』をクリック")
            c.click_it('//button[contains(normalize-space(.), "次へ")]')
            c.wait_random()
            time.sleep(0.8)
            continue

        # ② スキップ（次に優先）
        skip_button = c.get_element('//button[contains(normalize-space(.), "スキップ")]')
        if skip_button is not None:
            logger.info("『スキップ』をクリック")
            c.click_it('//button[contains(normalize-space(.), "スキップ")]')
            c.wait_random()
            time.sleep(0.8)
            continue

        # ③ プレイ終了（最後）
        play_end_button = c.get_element('//button[contains(normalize-space(.), "プレイ終了")]')
        if play_end_button is not None:
            logger.info("『プレイ終了』をクリック")
            c.click_it('//button[contains(normalize-space(.), "プレイ終了")]')
            c.wait_random()
            logger.info("終了")
            break

        # どれもない → UI遷移中
        time.sleep(0.5)

    else:
        raise Exception("精算後の画面遷移が完了しません（ボタン検出不可）")
        
def take_store_all(c):
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
        })()
    """
    return c.driver.execute_script(script)


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
        })()["game"]["commonBase"]["commonBaseGames"]
    """
    return c.driver.execute_script(script)


CACHED_GAME_INFO = None


def take_game_store(c):
    global CACHED_GAME_INFO

    if CACHED_GAME_INFO is None:
        CACHED_GAME_INFO = take_store_all(c)["entities"]["game"]

    stores = take_store(c)
    for item in stores.values():
        if item["gameCategory"] == 5:
            html_store = item["html"]
            selectGameKeyId = item["selectGameKeyId"]
            official_name = CACHED_GAME_INFO[str(selectGameKeyId)]["official_name"]

            logger.debug(f"{html_store}")
            fields = {
                "medal": html_store["medal"] // html_store["selectedRate"],
                "game_name": official_name,
                "total_coin": item["fsCoin"] + html_store["medal"],
            }
            write_influx(
                f"videoslot",
                fields,
            )
            return fields


def seat_and_check_payout(c: Controller, game_id: int, is_bingo: bool=False, is_variety: bool=False) -> int:
    game_type = 'pink' if is_variety else 'green'
    rate = 1
    credit = 1000

    c.click_it('//button[text()="プレイ"]')

    pulldown_xpath = '//div[contains(@class, "_pulldown")]'

    # --- レート選択 ---
    c.wait_it(pulldown_xpath, timeout=60)
    time.sleep(1.0)  # 表示が落ち着くのを少し待つ
    c.click_it(pulldown_xpath)

    # span ではなく、その親の行(div)をクリック対象にする
    rate_item_xpath = (
        f'(//div[contains(@class, "_pullDownItem")]'
        f'[.//span[contains(text(), "{rate}")]])[1]'
    )
    c.wait_it(rate_item_xpath, timeout=10)
    time.sleep(0.5)
    c.click_it(rate_item_xpath)
    c.wait_random()

    c.click_it('//button[text()="レート決定"]')
    c.wait_random()

    # --- クレジット選択 ---
    c.wait_it(pulldown_xpath, timeout=60)
    time.sleep(1.0)
    c.click_it(pulldown_xpath)

    credit_item_xpath = (
        f'(//div[contains(@class, "_pullDownItem")]'
        f'[.//span[contains(text(), "{credit:,}")]])[1]'
    )
    c.wait_it(credit_item_xpath, timeout=10)
    time.sleep(0.5)
    c.click_it(credit_item_xpath)
    c.wait_random()

    c.driver.execute_cdp_cmd("Network.enable", {})
    c.driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
    c.wait_random()

    c.click_it('//button[text()="プレイ開始"]')

    c.wait_random(3)
    shrink_window_if_clipped(c, game_type=game_type)
    payout = None

    try:
        p_logs = c.driver.get_log("performance")

        for entry in p_logs:
            msg = json.loads(entry["message"])["message"]
            # レスポンス受信イベントのみフィルター
            if (
                msg.get("method") == "Network.responseReceived"
                and "buy_medal" in msg["params"]["response"]["url"]
            ):

                request_id = msg["params"]["requestId"]
                # レスポンスボディを取得
                try:
                    body = c.driver.execute_cdp_cmd(
                        "Network.getResponseBody", {"requestId": request_id}
                    )
                    if body["base64Encoded"]:
                        body["body"] = base64.decodebytes(body["body"].encode())

                except:
                    # logger.exception("Error getResponseBody")
                    continue

                if "buy_medal" in msg["params"]["response"]["url"]:
                    payout = int(json.loads(body["body"])["data"]["payout"])
                    logger.info(f"{payout=}")
                    logger.info("search payout checked from buy_medal; no spin/auto")
                    c.driver.switch_to.default_content()
                    c.wait_random()

                    # 精算
                    finish_game(c, save_image=False, is_bingo=is_bingo, is_variety=is_variety, game_type=game_type)
                    c.wait_random(3)
                    break

    finally:
        c.driver.execute_cdp_cmd("Network.disable", {})
        c.driver.execute_cdp_cmd(
            "Network.setCacheDisabled", {"cacheDisabled": False}
        )

    if payout is None:
        raise Exception("buy_medal response was not found; payout could not be checked")

    return payout
