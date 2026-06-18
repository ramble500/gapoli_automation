import logging
import time
import csv

from dotenv import load_dotenv
import threading
from concurrent.futures import ThreadPoolExecutor

from automator.utils.error_reporter import ErrorReporter
from automator.utils.influx import init_influx
from automator.utils.recovery import CommunicationErrorRecovered
from automator.vslot.utils import (
    finish_game,
    focus_main_window,
    seat,
    take_game_store,
    take_store,
    take_store_all,
    buy_medal,
    shrink_window,
    shrink_window_if_clipped,
    start_auto_9999,
    move_window_to_right,
    bring_window_to_front,
    click_auto_progress_button,
    click_canvas_game_pos,
)

load_dotenv(verbose=True)

import argparse
import datetime
import os
import time
from pathlib import Path

from automator.login import Controller
from automator.utils.influx import init_influx
from automator.utils.initial import initial_action
from automator.utils.logging_config import setup_file_logging

logging.getLogger("urllib3").setLevel(logging.ERROR)  # ad hoc

parser = argparse.ArgumentParser()
parser.add_argument("game_id", type=int, nargs='+')

parser.add_argument("--loglevel", default="INFO")

parser.add_argument(
    "--casino-rate", type=int, choices=[1, 3, 10], default=10, help="カジノ用レート"
)
parser.add_argument(
    "--variety-rate", type=int, choices=[5, 10], default=10, help="バラエティ用レート"
)

parser.add_argument("--credit", type=int, default=10000, help="初めに交換するクレジット数 (バラエティではこの3倍になります)")
parser.add_argument("--casino-credit", type=int, default=0, help="カジノ用クレジット (デバッグ用)")
parser.add_argument(
    "--limit_coin",
    type=int,
    default=1000000,
    help="これ以下の所持コインだったら止めます",
)
parser.add_argument(
    "--no-fast",
    action="store_true",
    help="フリーの場合は高速オートを無効にしてください",
)
parser.add_argument(
    "--accept-payout",
    type=int,
    choices=[1, 4, 5, 6],
    default=6,
    help='許容する最低ペイアウト設定',
)
parser.add_argument(
    '--no-mute',
    action='store_true',
    help='ミュートをオフにします。BGMを聴きたいときに',
)

parser.add_argument(
    '--variety-bet',
    type=int,
    choices=[1, 2, 3],
    default=3,
    help='バラエティのベット単価 (低い順に1, 2, 3)',
)
parser.add_argument(
    '--variety-spec',
    type=int,
    choices=[1, 2],
    default=1,
    help='バラエティのスペック (1: 安定, 2: 荒波)',
)
parser.add_argument(
    '--no-influx',
    action='store_true',
    help='Influxデータベースへの書き込み抑止'
)


args = parser.parse_args()

LOG_PATH = setup_file_logging(args.loglevel, "vslot")
logging.getLogger("urllib3").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
logger.info("log file: %s", LOG_PATH)

GAME_ID_LIST = args.game_id

FS_COIN_LIMIT = args.limit_coin
REROLL_COUNT = 10
CREDIT = args.credit
CASINO_CREDIT = args.casino_credit

CASINO_RATE = args.casino_rate
VARIETY_RATE = args.variety_rate
NO_FAST = args.no_fast
ACCEPT_PAYOUT = args.accept_payout
NO_MUTE = args.no_mute

VARIETY_BET = args.variety_bet
VARIETY_SPEC = args.variety_spec

NO_INFLUX = args.no_influx

# 機種リストの作成
MACHINE_LIST = {}
try:
    with open('./automator/utils/machine_list.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == '1':
                key = int(row[1])
                value = row[2]
                MACHINE_LIST[key] = value
except Exception as e:
    print(e)
    logger.error('failed to load machine list. is machine_list.csv present?')
    exit(1)

# 画面位置管理用 (GAME_IDをキーとして、左なら0 or 右なら1)
POSITION_STACK = {}

LOGIN_ID = os.environ.get("LOGIN_ID")
PASSWORD = os.environ.get("PASSWORD")
logger.info(LOGIN_ID)

c = Controller(headless=False, network_logging=True, no_mute=NO_MUTE)


def read_game_medal(
    game_category: int,
    game_id: int,
    game_name: str,
) -> int | None:
    game_store = take_game_store(
        c,
        no_influx=NO_INFLUX,
        game_category=game_category,
        game_id=game_id,
        game_name=game_name,
    )
    return game_store["medal"] if game_store else None


def save_play_data_screenshot(game_name: str, game_type: str) -> str:
    result_path = f"./log/vs_result_ss/vs_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    Path(result_path).parent.mkdir(parents=True, exist_ok=True)
    focus_main_window(c, game_type=game_type)
    c.wait_random()
    try:
        image = c.take_image_from_canvas("//canvas")
    except CommunicationErrorRecovered:
        raise
    except Exception:
        logger.debug("[%s] canvas capture failed; falling back to screenshot crop", game_name, exc_info=True)
        image = c.take_photo_of("//canvas")
    c.save_ss(result_path, image)
    logger.info("[%s] play data screenshot saved: %s", game_name, result_path)
    c.driver.switch_to.default_content()
    return result_path


def wait_for_game_medal_change(
    processing_lock: threading.Lock,
    game_category: int,
    game_id: int,
    game_name: str,
    before_medal: int | None,
    timeout: float = 25.0,
) -> bool:
    if before_medal is None:
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2.0)
        with processing_lock:
            current_medal = read_game_medal(game_category, game_id, game_name)

        if current_medal is not None and current_medal != before_medal:
            logger.info(
                "[%s] credit変化を確認: %s -> %s",
                game_name,
                before_medal,
                current_medal,
            )
            return True

    return False


def game_loop(GAME_ID: int, processing_lock: threading.Lock):
    game_name = MACHINE_LIST.get(GAME_ID, str(GAME_ID))
    while True:
        try:
            return _game_loop(GAME_ID, processing_lock)
        except CommunicationErrorRecovered:
            logger.warning(
                "[%s] 通信エラー復帰後、着席状態を再確認してオート設定をやり直します",
                game_name,
            )
            time.sleep(2)


def _game_loop(GAME_ID: int, processing_lock: threading.Lock):
    global POSITION_STACK
    with ErrorReporter(c):
        IS_BINGO = GAME_ID in [20256, 20218]
        IS_VARIETY = GAME_ID in [20205, 20204, 20226]
        GAME_TYPE = 'green' if not IS_VARIETY else 'pink'
        GAME_NAME = MACHINE_LIST[GAME_ID]
        RATE = CASINO_RATE if not IS_VARIETY else VARIETY_RATE

        FIRST_START_DAY = datetime.datetime.now() - datetime.timedelta(hours=12)
        FIRST = True

        def bonus_time():
            # 日が変わったら落とす
            dt = datetime.datetime.now() - datetime.timedelta(hours=12)
            return FIRST_START_DAY.day == dt.day

        while FIRST or bonus_time():
            FIRST = False
            seated = False

            # 着席処理を行う間はロック
            with processing_lock:
                logger.warning(f"[{GAME_NAME}] {GAME_ID} 着席処理の開始")
                c.driver.switch_to.default_content()
                stores = take_store(c) or {}
                logger.debug(stores)
                game_info_by_id = take_store_all(c)["entities"]["game"] if stores else {}

                for item in stores.values():
                    a_game_category = 2 if IS_VARIETY else 5
                    try:
                        select_game_key_id = item.get("selectGameKeyId")
                        same_game = int(select_game_key_id) == GAME_ID
                        if not same_game:
                            official_name = game_info_by_id.get(str(select_game_key_id), {}).get("official_name")
                            same_game = official_name == GAME_NAME
                    except Exception:
                        same_game = False
                    if item["gameCategory"] == a_game_category and same_game:
                        seated = True

                # 台を確保
                if seated:
                    logger.warning(f"[{GAME_NAME}] Already Seated.")
                    #time.sleep(10)  # ad hoc (remove this)
                else:
                    coin_amount = take_store_all(c)["user"]["currency"]["fCoin"]

                    if coin_amount < FS_COIN_LIMIT:
                        raise ValueError("!!!!!!  coin value less than FS_COIN_LIMIT !!!!!!")

                    logger.warning(f'[{GAME_NAME}] {GAME_ID} seat')
                    seat(c, rate=RATE, credit=CREDIT if (CASINO_CREDIT == 0 or IS_VARIETY) else CASINO_CREDIT, accept_payout=ACCEPT_PAYOUT, is_bingo=IS_BINGO, 
                        is_variety=IS_VARIETY, game_type=GAME_TYPE, game_name=GAME_NAME, existing_window=(len(POSITION_STACK) >= 1))

                    if not GAME_ID in POSITION_STACK:
                        POSITION_STACK[GAME_ID] = len(POSITION_STACK)

                # ウインドウサイズを小さくする
                shrink_window_if_clipped(c, game_type=GAME_TYPE)

                logger.info(POSITION_STACK)
                # ウインドウを定位置に移動する
                if not seated and POSITION_STACK[GAME_ID] >= 1:
                    bring_window_to_front(c, game_type=GAME_TYPE)
                    move_window_to_right(c, game_type=GAME_TYPE)


            # オート開始 (通常カジノ台)
            if not IS_BINGO and not IS_VARIETY:

                auto_started = False
                for auto_attempt in range(1, 5):
                    # オート開始処理を行う間はロック
                    with processing_lock:
                        before_auto_medal = read_game_medal(5, GAME_ID, GAME_NAME)
                        bring_window_to_front(c, game_type=GAME_TYPE)
                        start_auto_9999(
                            c,
                            game_id=GAME_ID,
                            game_type=GAME_TYPE,
                            no_fast=NO_FAST,
                            auto_button_attempt=auto_attempt - 1,
                        )

                        c.driver.switch_to.default_content()

                    logger.warning(f"[{GAME_NAME}] オート開始設定を実行 ({auto_attempt}/2).")
                    auto_started = wait_for_game_medal_change(
                        processing_lock,
                        5,
                        GAME_ID,
                        GAME_NAME,
                        before_auto_medal,
                    )
                    if auto_started:
                        logger.warning(f"[{GAME_NAME}] オート開始をcredit変化で確認.")
                        break

                    logger.warning(f"[{GAME_NAME}] オート開始後のcredit変化なし。再設定します.")

                if not auto_started:
                    logger.warning(f"[{GAME_NAME}] オート開始確認失敗。スペース補助ループで監視継続.")
                
                # スペースキーを押す間隔の設定
                # 0.65 くじらさん
                # 0.75 きつねさん、西遊記、クインパ、ヒーローズ
                # 0.85 スピワイ、カスイチ
                # ほかは未調査

                if GAME_ID == 20238:
                    space_interval = 0.65
                elif GAME_ID in (20224, 20231, 20220, 20215):
                    space_interval = 0.75
                elif GAME_ID in (20246, 20254):
                    space_interval = 0.85
                elif GAME_ID in (20280, -2):
                    space_interval = 0.975
                else:  # ad hoc
                    space_interval = 0.85

                for i in range(100000):
                    with processing_lock:
                        v = take_game_store(
                            c,
                            no_influx=NO_INFLUX,
                            game_category=5,
                            game_id=GAME_ID,
                            game_name=GAME_NAME,
                        )

                    if v and v["medal"] < 100:
                        with processing_lock:
                            c.driver.switch_to.default_content()
                            credit_dialog_found = c.get_element(
                                f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"クレジット")]/../..//button[text()="閉じる"]'
                            ) is not None
                        if credit_dialog_found:
                            # 残念、尽きた
                            logger.warning(f"[{GAME_NAME}] Credit 切れ 精算開始.")

                            # 精算処理を行う間はロック
                            with processing_lock:
                                c.click_it(
                                    f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"クレジット")]/../..//button[text()="閉じる"]'
                                )

                                focus_main_window(c, game_type=GAME_TYPE)

                                c.click_relative_pos((0.05, 0.95), "//canvas")
                                save_play_data_screenshot(GAME_NAME, GAME_TYPE)

                                finish_game(c, game_type=GAME_TYPE)
                            break

                    with processing_lock:
                        c.driver.switch_to.default_content()
                        completed_dialog_found = c.get_element(
                            f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"プレイ回数が上限")]/../..//button[text()="精算"]'
                        ) is not None
                    if completed_dialog_found:
                        # 完走!
                        logger.warning(f"[{GAME_NAME}] 完走 精算開始.")
                        # 精算処理を行う間はロック
                        with processing_lock:
                            c.click_it(
                                f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"プレイ回数が上限")]/../..//button[text()="精算"]'
                            )
                            c.wait_random()

                            c.click_it(
                                '//span[text()[contains(., "精算します")]]/../..//button[text()="精算"]'
                            )
                            c.wait_random()
                            save_play_data_screenshot(GAME_NAME, GAME_TYPE)
                            finish_game(c, from_dialog=True)
                        break

                    time.sleep(space_interval)
    
                    with processing_lock:
                        focus_main_window(c, game_type=GAME_TYPE)
                        c.key_down(" ", "//canvas")
                        c.driver.switch_to.default_content()


            # 手動開始 (バラエティ)
            elif IS_VARIETY:
                b_width = 560
                b_height = 960
                button_reel_auto = (525/b_width, 925/b_height) if GAME_ID == 20205 else None

                if GAME_ID == 20205:
                    button_spec = [
                        (105/b_width, 255/b_height),
                        (105/b_width, 340/b_height),
                    ]
                    button_bet = [
                        (130/b_width, 540/b_height),
                        (130/b_width, 590/b_height),
                        (130/b_width, 640/b_height),
                    ]
                    button_start_candidates = [
                        (300/b_width, 710/b_height),
                    ]
                
                elif GAME_ID == 20204:
                    button_spec = [  # 個別に処理したくないのでダミーの位置をクリック
                        (300/b_width, 320/b_height),
                        (300/b_width, 320/b_height),
                    ]
                    button_bet = [
                        (185/b_width, 460/b_height),
                        (185/b_width, 500/b_height),
                        (185/b_width, 540/b_height),
                    ]
                    button_start_candidates = [
                        (300/b_width, 605/b_height),
                    ]

                elif GAME_ID == 20226:
                    button_spec = [
                        (110/b_width, 280/b_height),
                        (105/b_width, 355/b_height),
                    ]
                    button_bet = [
                        (140/b_width, 560/b_height),
                        (140/b_width, 610/b_height),
                        (140/b_width, 660/b_height),
                    ]
                    button_start_candidates = [
                        (300/b_width, 710/b_height),
                    ]

                # 初期設定を行う間はロック
                with processing_lock:
                    bring_window_to_front(c, game_type=GAME_TYPE)
                    focus_main_window(c, game_type=GAME_TYPE)

                    # クレジットを追加で2倍交換 (初回のみ)
                    if not seated:
                        buy_medal(c, game_type=GAME_TYPE, credit=CREDIT)
                        buy_medal(c, game_type=GAME_TYPE, credit=CREDIT)

                    focus_main_window(c, game_type=GAME_TYPE)

                    if button_reel_auto is not None:
                        logger.info(f'[{GAME_NAME}] リール停止オート有効化')
                        click_auto_progress_button(
                            c,
                            game_type=GAME_TYPE,
                            fallback_pos=button_reel_auto,
                        )
                        time.sleep(0.5)

                    logger.info(
                        f'[{GAME_NAME}] バラエティ手動開始ループ '
                        f'(start候補={len(button_start_candidates)})'
                    )

                # スタートボタンを押すループ (約5sec毎)
                with processing_lock:
                    last_credit = read_game_medal(2, GAME_ID, GAME_NAME)
                stall_count = 0
                start_candidate_index = 0
                confirmed_start_button = None
                while True:
                    if confirmed_start_button is None:
                        pending_start_button = button_start_candidates[
                            start_candidate_index % len(button_start_candidates)
                        ]
                        pending_start_label = start_candidate_index % len(button_start_candidates) + 1
                        start_candidate_index += 1
                    else:
                        pending_start_button = confirmed_start_button
                        pending_start_label = 0

                    with processing_lock:
                        c.driver.switch_to.default_content()
                        result_area = c.get_element(
                            f'//div[contains(@class, "{GAME_TYPE}")]//div[contains(@class, "resultArea")]'
                        )
                        if result_area is not None and result_area.is_displayed():
                            logger.warning(f"[{GAME_NAME}] 結果画面を検知 精算開始.")
                            finish_game(c, is_variety=True, game_type=GAME_TYPE)
                            break

                        focus_main_window(c, game_type=GAME_TYPE)
                        click_canvas_game_pos(c, button_spec[VARIETY_SPEC - 1])
                        time.sleep(0.25)
                        click_canvas_game_pos(c, button_bet[VARIETY_BET - 1])
                        time.sleep(0.25)
                        click_canvas_game_pos(c, pending_start_button)
                        time.sleep(0.5)

                    # クレジット切れダイアログ検知
                    with processing_lock:
                        c.driver.switch_to.default_content()
                        credit_dialog_found = c.get_element(
                            f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"クレジット")]/../..//button[text()="閉じる"]'
                        ) is not None
                    if credit_dialog_found:
                        logger.warning(f"[{GAME_NAME}] Credit 切れ 精算開始.")
                        # 精算処理を行う間はロック
                        with processing_lock:
                            c.click_it(
                                f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"クレジット")]/../..//button[text()="閉じる"]'
                            )

                            focus_main_window(c, game_type=GAME_TYPE)

                            save_play_data_screenshot(GAME_NAME, GAME_TYPE)

                            finish_game(c, is_variety=True, game_type=GAME_TYPE)
                        break

                    # 完走ダイアログの検知
                    with processing_lock:
                        c.driver.switch_to.default_content()
                        completed_dialog_found = c.get_element(
                            f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"プレイ回数が上限")]/../..//button[text()="精算"]'
                        ) is not None
                    if completed_dialog_found:
                        # 完走!
                        logger.warning(f"[{GAME_NAME}] 完走 精算開始.")
                        # 精算処理を行う間はロック
                        with processing_lock:
                            c.click_it(
                                f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"プレイ回数が上限")]/../..//button[text()="精算"]'
                            )
                            c.wait_random()

                            c.click_it(
                                '//span[text()[contains(., "精算します")]]/../..//button[text()="精算"]'
                            )
                            c.wait_random()
                            save_play_data_screenshot(GAME_NAME, GAME_TYPE)
                            finish_game(c, from_dialog=True, is_variety=True, game_type=GAME_TYPE)
                        break

                    with processing_lock:
                        try:
                            game_store = take_game_store(
                                c,
                                no_influx=NO_INFLUX,
                                game_category=2,
                                game_id=GAME_ID,
                                game_name=GAME_NAME,
                            )
                            current_credit = game_store["medal"] if game_store else None
                        except CommunicationErrorRecovered:
                            raise
                        except Exception:
                            current_credit = None

                    if current_credit is not None:
                        if last_credit is None:
                            last_credit = current_credit
                        elif current_credit != last_credit:
                            if confirmed_start_button is None:
                                confirmed_start_button = pending_start_button
                                logger.info(
                                    f"[{GAME_NAME}] バラエティ開始ボタン候補{pending_start_label}を確定"
                                )
                            last_credit = current_credit
                            stall_count = 0
                        else:
                            stall_count += 1
                            logger.info(
                                f"[{GAME_NAME}] バラエティ手動ループ credit変化なし ({stall_count})"
                            )
                    else:
                        stall_count += 1
                        logger.info(
                            f"[{GAME_NAME}] バラエティ手動ループ credit取得失敗 ({stall_count})"
                        )

                    if stall_count >= 8:
                        logger.warning(f"[{GAME_NAME}] バラエティ手動ループ停止 精算開始.")
                        with processing_lock:
                            finish_game(c, is_variety=True, game_type=GAME_TYPE)
                        break
                    
                    time.sleep(4.5)


            # オート開始 (ビンゴ)
            elif IS_BINGO:
                b_width = 560
                b_height = 960

                button_leftpanel = (8/b_width, 830/b_height)
                button_speed3 = (170/b_width, 830/b_height)

                button_extraball_end = (100/b_width, 825/b_height)
                button_extraball_end_confirm = (160/b_width, 650/b_height)

                button_begin_bonus = (300/b_width, 750/b_height)
                button_swap_spec_right = (500/b_width, 385/b_height)
                button_draw_capsule_all = (420/b_width, 675/b_height)
                button_open_capsule_all = (300/b_width, 790/b_height)
                button_begin_rush = (300/b_width, 790/b_height)

                if GAME_ID == 20218:
                    button_rightpanel = (550/b_width, 830/b_height)
                    button_automax = (530/b_width, 815/b_height)
                    button_begin_auto = (465/b_width, 825/b_height)

                elif GAME_ID == 20256:
                    button_rightpanel = (515/b_width, 920/b_height)
                    button_automax = (390/b_width, 480/b_height)
                    button_begin_auto = (285/b_width, 630/b_height)

                # 初期設定を行う間はロック
                with processing_lock:
                    bring_window_to_front(c, game_type=GAME_TYPE)
                    focus_main_window(c, game_type=GAME_TYPE)

                    # スピード3に設定
                    c.click_relative_pos(button_leftpanel, "//canvas")
                    time.sleep(0.5)
                    c.click_relative_pos(button_speed3, "//canvas")
                    time.sleep(0.5)
                    logger.info(f'[{GAME_NAME}] スピード3に設定')

                # ガチャのスペック変更したか管理用フラグ
                is_first_bonus = True
                # 外側のループから抜けるためのフラグ
                bingo_finish_game = False

                while not bingo_finish_game:
                    # 初回、またはボーナスから抜けるたびにオートの再設定
                    with processing_lock:
                        bring_window_to_front(c, GAME_TYPE)
                        focus_main_window(c, game_type=GAME_TYPE)
                        c.click_relative_pos(button_rightpanel, "//canvas")
                        time.sleep(0.5)
                        c.click_relative_pos(button_automax, "//canvas")
                        time.sleep(0.5)
                        c.click_relative_pos(button_begin_auto, "//canvas")
                        logger.warning(f'[{GAME_NAME}] オート開始 (ビンゴ)')
                    
                        # ボーナス当選検知用
                        last_credit = take_game_store(
                            c,
                            no_influx=NO_INFLUX,
                            game_category=5,
                            game_id=GAME_ID,
                            game_name=GAME_NAME,
                        )['medal']
                        stall_count = 0

                    while True:
                        # クレジット切れダイアログの検知と精算
                        if c.get_element(
                            f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"クレジット")]/../..//button[text()="閉じる"]'
                        ):
                            logger.warning(f"[{GAME_NAME}] Credit 切れ 精算開始.")
                            # 精算処理を行う間はロック
                            with processing_lock:
                                c.click_it(
                                    f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"クレジット")]/../..//button[text()="閉じる"]'
                                )

                                focus_main_window(c, game_type=GAME_TYPE)

                                # 現在のゲームを終了 (エクストラボール終了)
                                c.click_relative_pos(button_extraball_end, "//canvas")
                                time.sleep(0.8)
                                c.click_relative_pos(button_extraball_end_confirm, "//canvas")
                                time.sleep(10)

                                save_play_data_screenshot(GAME_NAME, GAME_TYPE)

                                finish_game(c, is_bingo=True, game_type=GAME_TYPE)
                                bingo_finish_game = True
                            break

                        # プレイ回数上限ダイアログの検知と精算
                        if c.get_element(
                            f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"プレイ回数が上限")]/../..//button[text()="精算"]'
                        ):
                            # 完走!
                            logger.warning(f"[{GAME_NAME}] 完走 精算開始.")
                            # 精算処理を行う間はロック
                            with processing_lock:
                                c.click_it(
                                    f'//div[contains(@class, "{GAME_TYPE}")]//span[contains(text(),"プレイ回数が上限")]/../..//button[text()="精算"]'
                                )
                                c.wait_random()

                                c.click_it(
                                    '//span[text()[contains(., "精算します")]]/../..//button[text()="精算"]'
                                )
                                c.wait_random()
                                save_play_data_screenshot(GAME_NAME, GAME_TYPE)
                                
                                finish_game(c, from_dialog=True, is_bingo=True, game_type=GAME_TYPE)
                                bingo_finish_game = True
                            break


                        # クレジット変動の検査
                        with processing_lock:
                            game_store_1 = take_game_store(
                                c,
                                no_influx=NO_INFLUX,
                                game_category=5,
                                game_id=GAME_ID,
                                game_name=GAME_NAME,
                            )

                        if not game_store_1:
                            logger.warning(f'failed to fetch credit data')
                            continue
                        current_credit = game_store_1['medal']
                        logger.debug(f'credit: {current_credit} (stall_count: {stall_count})')

                        if current_credit != last_credit:
                            last_credit = current_credit
                            stall_count = 0
                            continue

                        else:
                            stall_count += 1
                            # 約25秒間クレジットに変動がない場合は、ボーナス突入と判定
                            if stall_count >= 25:
                                # ボーナス用の処理
                                logger.warning(f'[{GAME_NAME}] ボーナス検知')

                                # 一連の処理中はロック (検討の余地あり)
                                with processing_lock:
                                    bring_window_to_front(c, GAME_TYPE)
                                    focus_main_window(c, game_type=GAME_TYPE)

                                    # ボーナス画面に入る (10球未満で突入した場合)
                                    c.click_relative_pos(button_extraball_end, "//canvas")
                                    time.sleep(0.8)
                                    c.click_relative_pos(button_extraball_end_confirm, "//canvas")
                                    time.sleep(13)

                                    # ボーナス開始
                                    logger.info(f'[{GAME_NAME}] ボーナススタート選択')
                                    c.click_relative_pos(button_begin_bonus, "//canvas")
                                    time.sleep(3)

                                    # ガチャの選択
                                    # 初回のみ、安定スペックに変更する処理
                                    focus_main_window(c, game_type=GAME_TYPE)
                                    if is_first_bonus:
                                        logger.info(f'[{GAME_NAME}] ガチャスペック変更')
                                        c.click_relative_pos(button_swap_spec_right, "//canvas")
                                        time.sleep(1)
                                        is_first_bonus = False
                                    logger.info(f'[{GAME_NAME}] ガチャ回転')
                                    c.click_relative_pos(button_draw_capsule_all, "//canvas")
                                    time.sleep(5)

                                    # カプセルの開封
                                    logger.info(f'[{GAME_NAME}] カプセル開封')
                                    c.click_relative_pos(button_open_capsule_all, "//canvas")
                                    time.sleep(5)

                                # クレジットが変動する (=ビンゴラッシュが終わる) までボタンを定期的に押す
                                logger.info(f'[{GAME_NAME}] ガチャボーナス&ビンゴラッシュ終了待機中...')
                                rush_wait_count = 0
                                while True:
                                    with processing_lock:
                                        current_credit = take_game_store(
                                            c,
                                            no_influx=NO_INFLUX,
                                            game_category=5,
                                            game_id=GAME_ID,
                                            game_name=GAME_NAME,
                                        )['medal']
                                        if current_credit != last_credit:
                                            break

                                        rush_wait_count += 1
                                        bring_window_to_front(c, GAME_TYPE)
                                        focus_main_window(c, game_type=GAME_TYPE)
                                        c.click_relative_pos(button_begin_rush, "//canvas")

                                        # 複数ボーナスをもらった時対策で、ボーナス開始、ガチャ回転、カプセル開封 ボタン位置を定期的に押す
                                        if rush_wait_count % 3 == 0:  
                                            c.click_relative_pos(button_begin_bonus, "//canvas")
                                        if rush_wait_count % 3 == 1:
                                            c.click_relative_pos(button_draw_capsule_all, "//canvas")
                                        elif rush_wait_count % 3 == 2:
                                            c.click_relative_pos(button_open_capsule_all, "//canvas")

                                    time.sleep(5)

                                    # 20分待っても何も起こらない場合は強制break
                                    if rush_wait_count >= 240:
                                        logger.warning(f'[{GAME_NAME}] ガチャボーナス&ビンゴラッシュ終了判定失敗。強制breakします')
                                        break
                                        
                                # ガチャボーナス+ビンゴラッシュ終わり
                                logger.warning(f'[{GAME_NAME}] ボーナス終了 (数秒後にオート再設定します)')
                                time.sleep(8)
                                #focus_main_window(c, game_type=GAME_TYPE)
                                break

                            else:
                                time.sleep(1)
                        


with ErrorReporter(c):
    logger.info(GAME_ID_LIST)
    # 共通処理 (ログインまで)
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

    if not NO_INFLUX:
        init_influx()

    c.login(f"https://gapoli.net/search/")

    resumed_games = initial_action(c)
    # 復帰した順に左から並ぶ
    for q in resumed_games:
        id_list = [k for k, v in MACHINE_LIST.items() if v == q]
        if len(id_list):
            id = id_list[0]
            POSITION_STACK[id] = len(POSITION_STACK)
        else:  # 該当ジャンル以外
            POSITION_STACK[-1] = len(POSITION_STACK)

    c.wait_loaded()

    processing_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=4) as e:
        for id in GAME_ID_LIST:
            e.submit(game_loop, id, processing_lock)

