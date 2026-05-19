import logging
import time
from typing import List

from automator.login import Controller

logger = logging.getLogger(__name__)

INTERRUPTED_GAME_MESSAGE_XPATH = (
    '//div/div/span[text()[contains(.,"中断されたゲームがあります")]]'
)
INTERRUPTED_GAME_DIALOG_XPATH = f"{INTERRUPTED_GAME_MESSAGE_XPATH}/../../.."


def initial_action(c: Controller, interrupted_action: str = "resume") -> List[str]:
    handled_games = []

    if interrupted_action not in {"resume", "settle"}:
        raise ValueError(f"unsupported interrupted_action: {interrupted_action}")

    try:
        while True:
            c.click_it('//div[contains(@class, "_oKButton")]', timeout=3)
            logger.info("ログボスキップ")
            time.sleep(0.5)
    except:
        pass

    while True:
        el = c.get_element(INTERRUPTED_GAME_MESSAGE_XPATH)

        if el is not None:
            game_name = c.get_element(
                f"{INTERRUPTED_GAME_MESSAGE_XPATH}/../../../descendant::span[2]"
            ).text
            if interrupted_action == "settle":
                _settle_interrupted_game(c, game_name)
                logger.info("中断精算: %s", game_name)
            else:
                c.click_it(
                    f'{INTERRUPTED_GAME_DIALOG_XPATH}/descendant::button[text()="復帰する"]'
                )
                logger.info("中断復帰: %s", game_name)
            handled_games.append(game_name.strip())
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

    return handled_games


def _settle_interrupted_game(c: Controller, game_name: str):
    settle_button_xpaths = [
        f'{INTERRUPTED_GAME_DIALOG_XPATH}/descendant::button[contains(normalize-space(.), "精算")]',
        f'{INTERRUPTED_GAME_DIALOG_XPATH}/descendant::button[contains(normalize-space(.), "終了")]',
    ]

    for xpath in settle_button_xpaths:
        if _click_if_present(c, xpath, f"中断ゲーム精算ボタンをクリック: {game_name}"):
            _complete_interrupted_settlement(c, game_name)
            return

    raise Exception(f"中断ゲームの精算ボタンが見つかりません: {game_name}")


def _complete_interrupted_settlement(c: Controller, game_name: str):
    button_xpaths = [
        (
            '//div/div/span[text()[contains(.,"精算確認")]]/../../../descendant::button[text()="精算"]',
            f"中断ゲーム精算確認をクリック: {game_name}",
        ),
        (
            '//div/div/span[text()[contains(.,"精算確認")]]/../../../descendant::button[contains(normalize-space(.), "精算")]',
            f"中断ゲーム精算確認をクリック: {game_name}",
        ),
        (
            '//span[text()[contains(.,"精算します")]]/../..//button[text()="精算"]',
            f"中断ゲーム精算確認をクリック: {game_name}",
        ),
        (
            '//span[text()[contains(.,"精算します")]]/../..//button[contains(normalize-space(.), "精算")]',
            f"中断ゲーム精算確認をクリック: {game_name}",
        ),
        ('//button[normalize-space(.)="精算"]', f"中断ゲーム精算をクリック: {game_name}"),
        ('//button[contains(normalize-space(.), "次へ")]', "『次へ』をクリック"),
        ('//button[contains(normalize-space(.), "スキップ")]', "『スキップ』をクリック"),
        ('//button[contains(normalize-space(.), "プレイ終了")]', "『プレイ終了』をクリック"),
    ]
    timeout = time.time() + 30
    quiet_after_dialog_closed = None

    while time.time() < timeout:
        clicked = False
        for xpath, message in button_xpaths:
            if _click_if_present(c, xpath, message, timeout=2):
                clicked = True
                quiet_after_dialog_closed = None
                time.sleep(0.8)
                break

        if clicked:
            continue

        if c.get_element(INTERRUPTED_GAME_MESSAGE_XPATH) is None:
            if quiet_after_dialog_closed is None:
                quiet_after_dialog_closed = time.time() + 2
            elif time.time() >= quiet_after_dialog_closed:
                logger.info("中断ゲーム精算完了: %s", game_name)
                return
        else:
            quiet_after_dialog_closed = None

        time.sleep(0.5)

    raise Exception(f"中断ゲームの精算が完了しません: {game_name}")


def _click_if_present(c: Controller, xpath: str, message: str, timeout: int = 3) -> bool:
    if c.get_element(xpath) is None:
        return False

    logger.info(message)
    c.click_it(xpath, timeout=timeout)
    c.wait_random()
    return True
