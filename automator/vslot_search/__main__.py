import logging
import time

from dotenv import load_dotenv

from automator.utils.error_reporter import ErrorReporter
from automator.utils.influx import init_influx
from automator.vslot_search.utils import (
    finish_game,
    focus_main_window,
    seat_and_check_payout,
    take_game_store,
    take_store,
    take_store_all,
)

load_dotenv(verbose=True)

import argparse
import datetime
import os
import time
from pathlib import Path
import csv
import random

from automator.login import Controller
from automator.utils.influx import init_influx
from automator.utils.initial import initial_action

parser = argparse.ArgumentParser()

parser.add_argument("--loglevel", default="INFO")
parser.add_argument(
    "--accept-payout",
    type=int,
    choices=[4, 5, 6],
    default=6,
    help='許容する最低ペイアウト設定',
)
parser.add_argument(
    '--no-mute',
    action='store_true',
    help='ミュートをオフにします。BGMを聴きたいときに',
)
parser.add_argument(
    '--exclude-machines',
    type=str,
    default='',
    help='探索から除外する機種ID (カンマ区切り)'
)
parser.add_argument(
    '--target-machines',
    type=str,
    default='',
    help='探索する機種ID (カンマ区切り) ※exclude-machinesと同時に指定した場合は、こちらだけ認識されます'
)

args = parser.parse_args()

logging.basicConfig(level=args.loglevel.upper())
logging.getLogger().setLevel(args.loglevel.upper())
logger = logging.getLogger(__name__)

ACCEPT_PAYOUT = args.accept_payout
NO_MUTE = args.no_mute

LOGIN_ID = os.environ.get("LOGIN_ID")
PASSWORD = os.environ.get("PASSWORD")
logger.info(LOGIN_ID)

machine_list_mode = 'exclude'
if args.exclude_machines != '':
    EXCLUDE_MACHINE_LIST = [int(q) for q in args.exclude_machines.split(',')]
else:
    EXCLUDE_MACHINE_LIST = []

if args.target_machines != '':
    TARGET_MACHINE_LIST = [int(q) for q in args.target_machines.split(',')]
    machine_list_mode = 'target'
else:
    TARGET_MACHINE_LIST = []


# 機種リストの作成
MACHINE_LIST = {}
try:
    with open('./automator/utils/machine_list.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == '1':
                key = int(row[1])
                value = row[2]
                if machine_list_mode == 'exclude' and key in EXCLUDE_MACHINE_LIST:
                    continue
                elif machine_list_mode == 'target' and not key in TARGET_MACHINE_LIST:
                    continue
                MACHINE_LIST[key] = value
except Exception as e:
    print(e)
    logger.error('failed to load machine list. is machine_list.csv present?')
    exit(1)
    
logger.warning(f'target list: {MACHINE_LIST}')

c = Controller(headless=False, network_logging=True, no_mute=NO_MUTE)

with ErrorReporter(c):
    # 初回ログイン
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

    init_influx()

    # 事故防止のため、ほかのゲームが起動中は中止
    c.login(f"https://gapoli.net/game/")
    resumed_games = initial_action(c)
    c.wait_loaded()

    if len(resumed_games) >= 1:
        logger.error('ほかのゲームをすべて精算してから起動してください')
        exit(1)


    remain_count = 999999
    nice_machine = None

    for i in range(10):
        logger.warning(f'---- loop {i+1} start ----')
        # 機種リストをシャッフル
        machine_search_order = list(MACHINE_LIST.keys())
        random.shuffle(machine_search_order)
        logger.info(machine_search_order)

        # 順に、着席→数回プレイ→離席 を繰り返す
        for game_id in machine_search_order:
            is_bingo = game_id in [20256, 20218]
            is_variety = game_id in [20205, 20204, 20226]

            c.login(f"https://gapoli.net/game/{game_id}")
            c.wait_loaded()

            c.driver.switch_to.default_content()

            result_payout = seat_and_check_payout(
                c,
                game_id=game_id,
                is_bingo=is_bingo,
                is_variety=is_variety,
            )

            # 好ペイアウト台を発見
            if result_payout >= ACCEPT_PAYOUT:
                nice_machine = game_id
                logger.warning('  O nice payout (%d) for %s (%d)!' % (result_payout, MACHINE_LIST[game_id], game_id))
                # 対象機種が見つかった場合でも、カモフラージュのため追加で何回かまわす
                if remain_count > 100:
                    remain_count = int(random.random() * 3) + 3
            else:
                logger.warning('  X  bad payout (%d) for %s' % (result_payout, MACHINE_LIST[game_id]) )
            
            remain_count -= 1
            if remain_count < 0:
                break

        if nice_machine:
            break
    
    # 見つからなかった場合
    if nice_machine is None:
        logger.warning('no nice machine found. exiting')
    else:
        logger.warning('nice machine found: %s (%d)' % (MACHINE_LIST[nice_machine], nice_machine))

