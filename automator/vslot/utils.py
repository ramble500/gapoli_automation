import base64
import datetime
import json
import logging
import random
import time
from pathlib import Path
from typing import List

from selenium.webdriver.common.keys import Keys

from automator.login import Controller
from automator.utils.influx import write_influx
from automator.utils.recovery import (
    CommunicationErrorRecovered,
    raise_if_communication_error,
)

logger = logging.getLogger(__name__)


def focus_main_window(c: Controller, game_type: str = 'green'):
    c.driver.switch_to.default_content()

    #bring_window_to_front(c, game_type=game_type)
    if1 = c.get_elements(f'//div[contains(@class, "{game_type}")]//iframe')
    c.driver.switch_to.frame(if1[0])

    c.wait_it("//canvas")

def buy_medal(c: Controller, game_type: str='green', credit: int=10000):
    # クレジット交換ボタンの押下
    c.driver.switch_to.default_content()
    c.click_it(
        f'//div[contains(@class, "{game_type}")]//div[contains(@class, "autoButtonWrapper") and not(contains(@class, "disabled"))]'
    )
    c.wait_random()

    # ダイアログの処理
    pulldown_xpath = '//div[contains(@class, "_pulldown")]'
    c.click_it(pulldown_xpath)
    credit_item_xpath = (
        f'//div[contains(@class, "_pullDownItem")]'
        f'[.//span[normalize-space(.)="{credit:,}"]]'
    )
    c.click_visible_item(credit_item_xpath, scroll_origin_xpath=pulldown_xpath)
    c.wait_random()

    c.click_it('//button[text()="プレイ開始"]')
    c.wait_random()


def finish_game(c: Controller, save_image: bool = True, from_dialog=False, is_bingo: bool=False, is_variety: bool=False, game_type: str='green'):
    # 精算する
    c.driver.switch_to.default_content()

    if not from_dialog:
        for i in range(30 if not is_variety else 999):
            if c.get_element(
                f'//div[contains(@class, "{game_type}")]//div[contains(@class, "checkButtonWrapper") and contains(@class, "disabled") and not(contains(@class, "item"))]'
            ):
                # WIN回収
                logger.info("payoff disabled. press space...")
                focus_main_window(c, game_type=game_type)
                c.key_down(" ", "//canvas")
                c.driver.switch_to.default_content()
                time.sleep(1)
            c.wait_it(
                f'//div[contains(@class, "{game_type}")]//div[contains(@class, "checkButtonWrapper") and not(contains(@class, "disabled")) and not(contains(@class, "item"))]'
            )
            #logger.info("click checkButtonWrapper")
            c.click_it(
                f'//div[contains(@class, "{game_type}")]//div[contains(@class, "checkButtonWrapper") and not(contains(@class, "disabled")) and not(contains(@class, "item"))]'
            )
            c.wait_random()
            try:
                el = c.wait_it(
                    '//div/div/span[text()[contains(.,"精算確認")]]', timeout=2
                )
            except CommunicationErrorRecovered:
                raise
            except:
                el = None
                # どこかでスタックしている可能性があるため、一度スペースボタンを押す (ビンゴ、バラエティを除く)
                if not is_bingo and not is_variety:
                    logger.info("still in game. press space...")
                    focus_main_window(c, game_type=game_type)
                    c.key_down(" ", "//canvas")
                    c.driver.switch_to.default_content()
                    time.sleep(5)
                else:
                    #logger.info('still in game. waiting...')
                    time.sleep(1.5)

            if el is not None:
                break
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
    end_clicked = False
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
        end_button = c.get_element(end_xpath)

        if next_button is None and skip_button is None and end_button is None:
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

        if end_button is not None:
            logger.info("『プレイ終了』をクリック")
            safe_click(end_xpath)
            end_clicked = True
            no_button_count = 0
            c.wait_random()
            time.sleep(1.5)
            continue

        time.sleep(0.5)

    else:
        raise Exception("精算後の画面遷移が完了しません（前面ポップアップが消えない）")

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
    try:
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
    except Exception as e:
        return None


CACHED_GAME_INFO = None


def take_game_store(
    c,
    no_influx=False,
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

        selectGameKeyId = item["selectGameKeyId"]
        official_name = CACHED_GAME_INFO[str(selectGameKeyId)]["official_name"]
        if game_id is not None or game_name is not None:
            matches_id = game_id is not None and int(selectGameKeyId) == int(game_id)
            matches_name = game_name is not None and official_name == game_name
            if not (matches_id or matches_name):
                continue

        html_store = item["html"]
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
        if not no_influx:
            write_influx(
                f"videoslot",
                fields,
            )
        return fields

    return None


# ウインドウサイズを小さくする
def shrink_window(c: Controller, game_type: str='green'):
    c.driver.switch_to.default_content()
    # ハンバーガーボタンをクリック
    logger.info(game_type)
    c.click_it(f'//div[contains(@class, "{game_type}")]//div[contains(@class, "marginRight6")]')
    time.sleep(1)

    c.click_it(f'//div[contains(@class, "{game_type}")]//span[text()[contains(., "画面サイズ設定")]]/..')
    time.sleep(1)

    # 0番目が「小」
    c.click_it(f'//div[contains(@class, "{game_type}")]//button[contains(@class, "resizeButton")]')
    time.sleep(1.5)

    c.click_it(f'//div[contains(@class, "{game_type}")]//div[contains(@class, "controlArea")]//div[contains(@class, "closeWrapper")]')
    time.sleep(1.5)


def shrink_window_if_clipped(c: Controller, game_type: str='green'):
    c.driver.switch_to.default_content()
    iframe = c.get_element(f'//div[contains(@class, "{game_type}")]//iframe')
    if iframe is None:
        return

    info = c.driver.execute_script(
        """
        const rect = arguments[0].getBoundingClientRect();
        return {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
        };
        """,
        iframe,
    )
    is_clipped = (
        info["left"] < 0
        or info["top"] < 0
        or info["right"] > info["viewportWidth"]
        or info["bottom"] > info["viewportHeight"]
    )
    if not is_clipped:
        return

    logger.info(f"game iframe is clipped; shrinking window: {info}")
    shrink_window(c, game_type=game_type)


def click_canvas_game_pos(
    c: Controller,
    relative_pos: tuple[float, float],
    canvas_xpath: str = "//canvas",
    base_width: int = 560,
    base_height: int = 960,
    aspect_tolerance: float = 0.04,
):
    canvas = c.get_element(canvas_xpath)
    if canvas is None:
        c.click_relative_pos(relative_pos, canvas_xpath)
        return

    width, height = c._get_element_size(canvas)
    if width <= 0 or height <= 0:
        c.click_relative_pos(relative_pos, canvas_xpath)
        return

    base_ratio = base_width / base_height
    canvas_ratio = width / height
    ratio_delta = abs(canvas_ratio - base_ratio) / base_ratio
    if ratio_delta <= aspect_tolerance:
        active_width = width
        active_height = height
        offset_x = 0
        offset_y = 0
        mode = "full"
    elif canvas_ratio > base_ratio:
        active_height = height
        active_width = height * base_ratio
        offset_x = (width - active_width) / 2
        offset_y = 0
        mode = "contain-x"
    else:
        active_width = width
        active_height = width / base_ratio
        offset_x = 0
        offset_y = (height - active_height) / 2
        mode = "contain-y"

    pos = (
        offset_x + relative_pos[0] * active_width,
        offset_y + relative_pos[1] * active_height,
    )
    logger.debug(
        "canvas game click: mode=%s relative=%s pos=%s canvas=%sx%s active=%sx%s offset=%sx%s ratio=%s base_ratio=%s",
        mode,
        relative_pos,
        pos,
        width,
        height,
        active_width,
        active_height,
        offset_x,
        offset_y,
        canvas_ratio,
        base_ratio,
    )
    c._click_element_point_with_mouse(canvas, pos)


def click_auto_progress_button(
    c: Controller,
    game_type: str = "green",
    fallback_pos: tuple[float, float] = (525 / 560, 910 / 960),
    candidate_index: int = 0,
):
    c.driver.switch_to.default_content()
    auto_button_xpath = (
        f'//div[contains(@class, "{game_type}")]'
        '//div[contains(@class, "autoButtonWrapper") '
        'and not(contains(@class, "disabled"))]'
    )
    if c.get_element(auto_button_xpath) is not None:
        try:
            logger.info("click autoButtonWrapper")
            c.click_it(auto_button_xpath, timeout=2)
            time.sleep(0.2)
            focus_main_window(c, game_type=game_type)
            return
        except CommunicationErrorRecovered:
            raise
        except Exception:
            logger.debug("autoButtonWrapper click failed; fallback to canvas", exc_info=True)

    candidate_seeds = [
        fallback_pos,
        (525 / 560, 925 / 960),
        (505 / 560, 925 / 960),
        (525 / 560, 910 / 960),
        (505 / 560, 910 / 960),
        (525 / 560, 895 / 960),
        (505 / 560, 895 / 960),
    ]
    candidates = list(dict.fromkeys(candidate_seeds))
    candidate = candidates[candidate_index % len(candidates)]

    focus_main_window(c, game_type=game_type)
    try:
        logger.info(
            "click canvas auto progress button: candidate=%s pos=%s",
            candidate_index,
            candidate,
        )
        click_canvas_game_pos(c, candidate)
        return
    except CommunicationErrorRecovered:
        raise
    except Exception:
        logger.warning(
            "canvas auto progress button click failed; fallback to DOM autoButtonWrapper",
            exc_info=True,
        )

    c.driver.switch_to.default_content()
    logger.info("click autoButtonWrapper fallback")
    c.click_it(auto_button_xpath, timeout=5)
    time.sleep(0.2)
    focus_main_window(c, game_type=game_type)


def start_auto_9999(
    c: Controller,
    game_id: int,
    game_type: str='green',
    no_fast: bool=False,
    auto_button_attempt: int = 0,
):
    b_width = 560
    b_height = 960

    # Use a visible point inside the lower-right round auto button; the center
    # can be clipped by the iframe on short viewports.
    button_auto_menu = (525 / b_width, 910 / b_height)
    if game_id == 20246:
        button_spin_count_9999 = (0.63, 0.44)
        button_fast_auto = (0.2, 0.5)
        button_ok = (0.5, 0.6)
    else:
        button_spin_count_9999 = (0.63, 0.51)
        button_fast_auto = (0.4, 0.57) if game_id == 20216 else (0.2, 0.56)
        button_ok = (0.5, 0.65)

    shrink_window_if_clipped(c, game_type=game_type)
    focus_main_window(c, game_type=game_type)
    logger.info("select auto menu button")
    click_auto_progress_button(
        c,
        game_type=game_type,
        fallback_pos=button_auto_menu,
        candidate_index=auto_button_attempt,
    )
    time.sleep(0.2)

    logger.info("select auto spin count 9999")
    click_canvas_game_pos(c, button_spin_count_9999)
    time.sleep(0.2)

    if not no_fast:
        logger.info("enable fast auto")
        click_canvas_game_pos(c, button_fast_auto)
        time.sleep(0.2)

    logger.info("confirm auto settings")
    click_canvas_game_pos(c, button_ok)


# ウインドウを定位置に移動する
def move_window_to_right(c: Controller, game_type: str='green'):
    pos = (0.95, 0) 
    c.driver.switch_to.default_content()
    c.dragdrop( (50, 5), pos, f'//div[contains(@class, "{game_type}")]//div[contains(@class, "header-info")]')
    time.sleep(1)


# ウインドウの上の方をクリックして前面にもってくる
def bring_window_to_front(c: Controller, game_type: str='green'):
    c.driver.switch_to.default_content()
    c.click_it(f'//div[contains(@class, "{game_type}")]//div[contains(@class, "header-info")]')
    time.sleep(0.5)

# 精算ウインドウなどが開いているとき用のbring_window_to_front
def bring_window_to_front_2(c: Controller, game_type: str='green'):
    c.driver.switch_to.default_content()
    c.click_relative_pos( (0, 0), f'//div[contains(@class, "{game_type}")]//div[contains(@class, "header-info")]')
    time.sleep(0.5)


def reset_search_page(c: Controller):
    c.driver.switch_to.default_content()
    if "search" not in c.driver.current_url:
        c.login("https://gapoli.net/search/")
        c.wait_loaded()
        time.sleep(1.5)


def click_search_close_if_present(c: Controller, xpath: str, label: str) -> bool:
    c.driver.switch_to.default_content()
    if c.get_element(xpath) is None:
        return True

    try:
        c.click_it(xpath, timeout=3)
        time.sleep(0.8)
        return True
    except CommunicationErrorRecovered:
        raise
    except Exception:
        logger.warning("failed to close search overlay: %s", label, exc_info=True)
        return False


def input_game_search_text(c: Controller, game_name: str):
    search_input_xpath = '//input[contains(@class, "gameSearchInput")]'
    el = c.wait_it(search_input_xpath, timeout=20)
    el.click()
    el.send_keys(Keys.CONTROL, "a")
    el.send_keys(Keys.BACKSPACE)
    el.send_keys(game_name)


def seat(c: Controller, rate: int = 10, credit: int = 10000, accept_payout: int = 6, is_bingo: bool = False, \
     is_variety: bool = False, game_type: str='green', game_name: str='', existing_window: bool = False):
    # ほかのウインドウを最小化 (あれば)
    minimized_window = False

    '''
    if  c.get_element(
        '//div[contains(@class, "toggleShowWindowIconOuter")]'
    ):
        logger.info('ほかのウインドウを最小化')
        c.click_it('//div[contains(@class, "toggleShowWindowIconOuter")]')
        time.sleep(1.5)
        minimized_window = True
    '''
    if existing_window:
        logger.info('ほかのウインドウを非表示')
        c.set_css_attribute_all('//div[contains(@class, "green") or contains(@class, "pink")]', 'display', 'none')
        time.sleep(1.5)
        minimized_window = True


    for i in range(20):  # TODO: fix me

        # 検索バーからたどる
        # 0. 検索用のウインドウが開いていない場合は、開き直す
        reset_search_page(c)
        # 1. ゲーム詳細ウインドウが開いている場合は、閉じる (検索画面に移る)
        if not click_search_close_if_present(
            c,
            '//div[contains(@class, "descImageButton")]/..//div[contains(@class, "closeIconOuter")]',
            "game detail",
        ):
            c.login("https://gapoli.net/search/")
            c.wait_loaded()
            time.sleep(1.5)
            continue
        # 2. 検索バーに何か文字が入っている (×ボタンがある) 場合は、消す
        if not click_search_close_if_present(
            c,
            '//div[contains(@class, "closeSearchIcon")]',
            "search text",
        ):
            c.login("https://gapoli.net/search/")
            c.wait_loaded()
            time.sleep(1.5)
            continue
        # 3. 検索バーにゲーム名を入力 → 反映されるまでしばらく待つ
        input_game_search_text(c, game_name)
        time.sleep(1.5)
        # 4. 一番上のエントリをクリック
        try:
            c.click_visible_item(
                '(//div[contains(@class, "gameItemContainer")])[1]//div[contains(@class, "rowWrapper")]',
                timeout=10,
                max_scrolls=2,
            )
        except CommunicationErrorRecovered:
            raise
        except Exception:
            logger.warning("failed to click search result; reload search and retry", exc_info=True)
            c.login("https://gapoli.net/search/")
            c.wait_loaded()
            time.sleep(1.5)
            continue
        c.wait_loaded()

        time.sleep(1.0)
        try:
            c.click_it('//button[text()="プレイ"]')
        except CommunicationErrorRecovered:
            raise
        except Exception:
            logger.info("プレイボタンが他要素に遮られたため、少し待って再クリック")
            time.sleep(1.5)
            c.click_it('//button[text()="プレイ"]', timeout=5)

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
        c.wait_it(rate_item_xpath, timeout=10)
        time.sleep(0.5)
        c.click_visible_item(rate_item_xpath, scroll_origin_xpath=pulldown_xpath)
        c.wait_random()

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
        c.wait_it(credit_item_xpath, timeout=10)
        time.sleep(0.5)
        c.click_visible_item(credit_item_xpath, scroll_origin_xpath=pulldown_xpath)
        c.wait_random()

        c.driver.execute_cdp_cmd("Network.enable", {})
        c.driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        c.wait_random()

        c.click_it('//button[text()="プレイ開始"]')

        c.wait_random(3)

        is_continue = False
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
                        continue
                        # logger.exception("Error getResponseBody")

                    if "buy_medal" in msg["params"]["response"]["url"]:
                        payout = json.loads(body["body"])["data"]["payout"]
                        logger.info(f"{payout=}")

                        # 以下の場合、何回かまわして台を捨てる
                        # 1. accept_payout に満たなかった場合
                        # 2. accept_payout を満たしていた場合でも、10%の確率で (検知対策)

                        if payout < accept_payout or random.randrange(0, 10) == 0:
                            if payout >= accept_payout:
                                logger.info('対策で捨てる')

                            focus_main_window(c, game_type=game_type)

                            if is_bingo:
                                # スピード3にして1回転まわす
                                b_width = 560
                                b_height = 960

                                button_leftpanel = (8/b_width, 830/b_height)
                                button_speed3 = (170/b_width, 830/b_height)
                                button_begin = (465/b_width, 825/b_height)
                                button_extraball_end = (100/b_width, 825/b_height)
                                button_extraball_end_confirm = (160/b_width, 650/b_height)

                                logger.info('スピード3に設定')
                                click_canvas_game_pos(c, button_leftpanel)
                                time.sleep(0.5)
                                click_canvas_game_pos(c, button_speed3)
                                time.sleep(0.5)

                                logger.info('1回転まわす')
                                click_canvas_game_pos(c, button_begin)
                                time.sleep(5.5)

                                click_canvas_game_pos(c, button_extraball_end)
                                time.sleep(0.8)
                                click_canvas_game_pos(c, button_extraball_end_confirm)
                                time.sleep(1)

                            elif is_variety:
                                # 北斗のオートは周回ではなくリール停止だけなので、
                                # 捨てゲーム時も手動スタート前に一度有効化する。
                                logger.info('バラエティ手動で1回転まわす')
                                b_width = 560
                                b_height = 960
                                button_start = (300/b_width, 710/b_height)
                                button_start_2 = (300/b_width, 605/b_height)

                                if '北斗の拳' in game_name:
                                    button_reel_auto = (525/b_width, 925/b_height)
                                    click_auto_progress_button(
                                        c,
                                        game_type=game_type,
                                        fallback_pos=button_reel_auto,
                                    )
                                    time.sleep(1)
                                    click_canvas_game_pos(c, button_start)
                                else:
                                    click_canvas_game_pos(c, button_start)
                                    click_canvas_game_pos(c, button_start_2)  # 場合分けが面倒なので両方押す

                                time.sleep(20)

                            else:
                                for i in range(10):
                                    time.sleep(1)
                                    c.key_down(" ", "//canvas")
                                c.driver.switch_to.default_content()

                                c.wait_random(3)

                            # 精算
                            finish_game(c, save_image=False, is_bingo=is_bingo, is_variety=is_variety, game_type=game_type)
                            c.wait_random(3)
                            is_continue = True
                            break

                        # OKの場合、is_continue フラグを立てずにbreak = この台で確定
                        else:
                            break

        finally:
            c.driver.execute_cdp_cmd("Network.disable", {})
            c.driver.execute_cdp_cmd(
                "Network.setCacheDisabled", {"cacheDisabled": False}
            )

        if is_continue:
            logger.info("continue")
            continue
        else:
            logger.info("start")
            if minimized_window:
                logger.info('ほかのウインドウを再表示')
                #c.click_it('//div[contains(@class, "toggleShowWindowIconOuter")]')
                c.set_css_attribute_all('//div[contains(@class, "green") or contains(@class, "pink")]', 'display', 'block')
                time.sleep(1.5)
            break
    else:
        raise ValueError("BAD PAYOUT")




