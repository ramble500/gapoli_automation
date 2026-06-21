import base64
import datetime
import json
import logging
import time
from pathlib import Path
from typing import List

from selenium.common.exceptions import TimeoutException

from automator.login import Controller
from automator.utils.influx import write_influx
from automator.utils.recovery import CommunicationErrorRecovered, raise_if_communication_error
from automator.vslot.utils import (
    click_auto_progress_button,
    click_canvas_game_pos,
    shrink_window_if_clipped,
)

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
        disabled_check_button_xpath = (
            f'//div[contains(@class, "{game_type}")]'
            '//div[contains(@class, "checkButtonWrapper") '
            'and contains(@class, "disabled") '
            'and not(contains(@class, "item"))]'
        )
        check_button_xpath = (
            f'//div[contains(@class, "{game_type}")]'
            '//div[contains(@class, "checkButtonWrapper") '
            'and not(contains(@class, "disabled")) '
            'and not(contains(@class, "item"))]'
        )
        el = None
        for _ in range(30 if not is_variety else 999):
            if c.get_element(disabled_check_button_xpath):
                logger.info("search payoff disabled. press space...")
                focus_main_window(c, game_type=game_type)
                c.key_down(" ", "//canvas")
                c.driver.switch_to.default_content()
                time.sleep(1)

            c.wait_it(check_button_xpath, timeout=60)
            logger.info("click checkButtonWrapper")
            c.click_it(check_button_xpath)
            c.wait_random()
            try:
                el = c.wait_it('//div/div/span[text()[contains(.,"精算確認")]]', timeout=2)
            except CommunicationErrorRecovered:
                raise
            except Exception:
                el = None
                if not is_bingo and not is_variety:
                    logger.info("search still in game. press space...")
                    focus_main_window(c, game_type=game_type)
                    c.key_down(" ", "//canvas")
                    c.driver.switch_to.default_content()
                    time.sleep(5)
                else:
                    time.sleep(1.5)

            if el is not None:
                break

        if el is None:
            raise TimeoutException("精算確認ダイアログが表示されません")
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
    no_button_count = 0

    def safe_click(xpath: str):
        try:
            c.click_it(xpath)
        except CommunicationErrorRecovered:
            raise
        except Exception:
            logger.warning(f"通常クリック失敗: {xpath}", exc_info=True)
            raise

    while time.time() < timeout:
        next_xpath = '//button[contains(normalize-space(.), "次へ")]'
        skip_xpath = '//button[contains(normalize-space(.), "スキップ")]'
        end_xpath = '//button[contains(normalize-space(.), "プレイ終了")]'

        next_button = c.get_element(next_xpath)
        skip_button = c.get_element(skip_xpath)
        play_end_button = c.get_element(end_xpath)

        if next_button is None and skip_button is None and play_end_button is None:
            no_button_count += 1
        else:
            no_button_count = 0

        if no_button_count >= 4:
            logger.info("前面の終了ボタン群消失を連続確認")
            break

        if next_button is not None:
            logger.info("『次へ』をクリック")
            safe_click(next_xpath)
            no_button_count = 0
            c.wait_random()
            time.sleep(1.0)
            continue

        if skip_button is not None:
            logger.info("『スキップ』をクリック")
            safe_click(skip_xpath)
            no_button_count = 0
            c.wait_random()
            time.sleep(1.0)
            continue

        if play_end_button is not None:
            logger.info("『プレイ終了』をクリック")
            safe_click(end_xpath)
            no_button_count = 0
            c.wait_random()
            time.sleep(1.5)
            continue

        time.sleep(0.5)

    else:
        raise Exception("精算後の画面遷移が完了しません（前面ポップアップが消えない）")

    logger.info("終了")
        
def take_store_all(c):
    raise_if_communication_error(c)
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
    raise_if_communication_error(c)
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


def take_game_store(
    c,
    game_category: int = 5,
    game_id: int | None = None,
    game_name: str | None = None,
):
    global CACHED_GAME_INFO

    if CACHED_GAME_INFO is None:
        CACHED_GAME_INFO = take_store_all(c)["entities"]["game"]

    stores = take_store(c)
    if not stores:
        return None

    for item in stores.values():
        if item["gameCategory"] != game_category:
            continue

        html_store = item["html"]
        selectGameKeyId = item["selectGameKeyId"]
        official_name = CACHED_GAME_INFO[str(selectGameKeyId)]["official_name"]
        if game_id is not None or game_name is not None:
            matches_id = game_id is not None and int(selectGameKeyId) == int(game_id)
            matches_name = game_name is not None and official_name == game_name
            if not (matches_id or matches_name):
                continue

        if "medal" not in html_store:
            logger.debug("game store has no medal: %s", html_store)
            continue

        selected_rate = html_store.get("selectedRate") or 1
        logger.debug(f"{html_store}")
        fields = {
            "medal": html_store["medal"] // selected_rate,
            "game_name": official_name,
            "game_category": game_category,
            "total_coin": item["fsCoin"] + html_store["medal"],
        }
        write_influx(
            f"videoslot",
            fields,
        )
        return fields

    return None


def select_search_dropdown_item(
    c: Controller,
    item_xpath: str,
    pulldown_xpath: str,
    label: str,
    timeout: int = 10,
) -> bool:
    try:
        c.wait_it(item_xpath, timeout=timeout)
    except TimeoutException as e:
        c.driver.switch_to.default_content()
        raise TimeoutException(f"search option not found: {label}") from e

    time.sleep(0.5)
    c.click_visible_item(item_xpath, scroll_origin_xpath=pulldown_xpath)
    c.wait_random()
    return True


def get_search_exchange_settings(game_id: int, is_variety: bool) -> tuple[int, int]:
    if is_variety:
        return 10, 10000
    return 1, 1000


def read_search_game_medal(
    c: Controller,
    game_category: int,
    game_id: int,
) -> int | None:
    game_store = take_game_store(c, game_category=game_category, game_id=game_id)
    return game_store["medal"] if game_store else None


def wait_for_search_game_medal_change(
    c: Controller,
    game_category: int,
    game_id: int,
    before_medal: int | None,
    timeout: float = 12.0,
) -> bool:
    if before_medal is None:
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.5)
        current_medal = read_search_game_medal(c, game_category, game_id)
        if current_medal is not None and current_medal != before_medal:
            logger.info(
                "search game credit changed: game_id=%s %s -> %s",
                game_id,
                before_medal,
                current_medal,
            )
            return True

    return False


def play_variety_once_for_search(c: Controller, game_id: int, game_type: str) -> None:
    b_width = 560
    b_height = 960
    settings = {
        20205: {
            "name": "Hokuto",
            "reel_auto": (505 / b_width, 910 / b_height),
            "spec": (105 / b_width, 255 / b_height),
            "bet": (130 / b_width, 640 / b_height),
            "start": (300 / b_width, 710 / b_height),
        },
        20204: {
            "name": "Juoh",
            "reel_auto": None,
            "spec": (300 / b_width, 320 / b_height),
            "bet": (185 / b_width, 540 / b_height),
            "start": (300 / b_width, 605 / b_height),
        },
        20226: {
            "name": "Oshobu",
            "reel_auto": None,
            "spec": (110 / b_width, 280 / b_height),
            "bet": (140 / b_width, 660 / b_height),
            "start": (300 / b_width, 710 / b_height),
        },
    }
    setting = settings.get(game_id)
    if setting is None:
        logger.warning("search variety spin skipped; unsupported game_id=%s", game_id)
        return

    c.driver.switch_to.default_content()
    shrink_window_if_clipped(c, game_type=game_type)
    before_medal = read_search_game_medal(c, game_category=2, game_id=game_id)
    logger.info(
        "search variety %s: before credit=%s",
        setting["name"],
        before_medal,
    )

    focus_main_window(c, game_type=game_type)

    if setting["reel_auto"] is not None:
        logger.info("search variety %s: enable reel auto", setting["name"])
        click_auto_progress_button(
            c,
            game_type=game_type,
            fallback_pos=setting["reel_auto"],
        )
        time.sleep(0.5)

    if before_medal is None:
        logger.warning(
            "search variety %s: credit unavailable; click start once without retry",
            setting["name"],
        )
        focus_main_window(c, game_type=game_type)
        click_canvas_game_pos(c, setting["spec"])
        time.sleep(0.25)
        click_canvas_game_pos(c, setting["bet"])
        time.sleep(0.25)
        click_canvas_game_pos(c, setting["start"])
        time.sleep(20)
        c.driver.switch_to.default_content()
        return

    for attempt in range(1, 5):
        logger.info(
            "search variety %s: select spec/bet and spin once attempt=%s",
            setting["name"],
            attempt,
        )
        focus_main_window(c, game_type=game_type)
        click_canvas_game_pos(c, setting["spec"])
        time.sleep(0.25)
        click_canvas_game_pos(c, setting["bet"])
        time.sleep(0.25)
        click_canvas_game_pos(c, setting["start"])
        time.sleep(0.5)
        c.driver.switch_to.default_content()

        if wait_for_search_game_medal_change(
            c,
            game_category=2,
            game_id=game_id,
            before_medal=before_medal,
            timeout=12.0,
        ):
            time.sleep(8)
            return

        current_medal = read_search_game_medal(
            c,
            game_category=2,
            game_id=game_id,
        )
        logger.warning(
            "search variety %s: spin did not start attempt=%s before=%s current=%s",
            setting["name"],
            attempt,
            before_medal,
            current_medal,
        )

    raise RuntimeError(
        f"search variety spin did not start: game_id={game_id} name={setting['name']}"
    )


def seat_and_check_payout(c: Controller, game_id: int, is_bingo: bool=False, is_variety: bool=False) -> int:
    game_type = 'pink' if is_variety else 'green'
    rate, credit = get_search_exchange_settings(game_id, is_variety)
    logger.info(
        "search exchange settings: game_id=%s rate=%s credit=%s",
        game_id,
        rate,
        credit,
    )

    c.click_it('//button[text()="プレイ"]')

    pulldown_xpath = '//div[contains(@class, "_pulldown")]'

    # --- レート選択 ---
    c.wait_it(pulldown_xpath, timeout=60)
    time.sleep(1.0)  # 表示が落ち着くのを少し待つ
    c.click_it(pulldown_xpath)

    # span ではなく、その親の行(div)をクリック対象にする
    rate_item_xpath = (
        f'//div[contains(@class, "_pullDownItem")]'
        f'[.//span[normalize-space(.)="{rate}"]]'
    )
    select_search_dropdown_item(
        c,
        rate_item_xpath,
        pulldown_xpath,
        f"rate={rate} game_id={game_id}",
    )

    c.click_it('//button[text()="レート決定"]')
    c.wait_random()

    # --- クレジット選択 ---
    c.wait_it(pulldown_xpath, timeout=60)
    time.sleep(1.0)
    c.click_it(pulldown_xpath)

    credit_item_xpath = (
        f'//div[contains(@class, "_pullDownItem")]'
        f'[.//span[normalize-space(.)="{credit:,}"]]'
    )
    select_search_dropdown_item(
        c,
        credit_item_xpath,
        pulldown_xpath,
        f"credit={credit:,} game_id={game_id}",
    )

    c.driver.execute_cdp_cmd("Network.enable", {})
    c.driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
    c.wait_random()

    c.click_it('//button[text()="プレイ開始"]')

    c.wait_random(3)
    shrink_window_if_clipped(c, game_type=game_type)
    payout = None

    try:
        raise_if_communication_error(c)
        p_logs = c.driver.get_log("performance")

        for entry in p_logs:
            raise_if_communication_error(c)
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
                    if is_variety:
                        logger.info("search payout checked from buy_medal; spin variety once before settlement")
                        play_variety_once_for_search(c, game_id, game_type)
                    else:
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
