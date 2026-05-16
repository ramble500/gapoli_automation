# simple bot
import datetime
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

import cv2
import numpy as np
from selenium.common.exceptions import NoSuchWindowException

from automator.login import Controller
from automator.suizoku.bigchance_count import detect_bigchance_counter
from automator.suizoku.detect_fish_type import get_stage, is_valid_transision
from automator.suizoku.detect_special_fish import (
    DetectSpecialFishResult,
    detect_special_fish,
)
from automator.suizoku.detect_tamate import detect_tamatebako
from automator.suizoku.matsuri_count import detect_matsuri_counter
from automator.suizoku.outside_action import (
    detect_window,
    finish_game,
    focus_main_window,
    reset_suizoku,
)
from automator.suizoku.utils import put_bbox, put_text_in_image
from automator.utils import clamp
from automator.utils.detect import cv2pil
from automator.utils.detect_color import detect_color
from automator.utils.influx import write_influx
from automator.utils.template import ImageMatcher, TemplateImage

from . import const
from .const import MEDAL_WAIT, NO_LOW_EXIT, big_timespan
from .crop import crop_relative, medal_area, poop_area

LOGIN_ID = os.environ.get("LOGIN_ID")

logger = logging.getLogger(__name__)
logger.info("Logger initialized!")

ultralytics_logger = logging.getLogger("ultralytics")
ultralytics_logger.setLevel(logging.WARNING)

LOG_IMAGE_TAMATE = False
LOG_IMAGE_BIG = False
LOG_IMAGE_NORMAL = True


def select_tamate(tamates, size) -> Tuple[bool, bool, bool]:
    width, height = size
    targets = [False for i in range(3)]
    for item in tamates:
        x, y = item
        if y < height * 0.4:
            targets[int(x * 3 // width)] = True

    return targets


class Ticker:

    def __init__(self, auto=True, newgame=False):
        self.auto = auto
        self.last_medal = 0
        self.last_medal_time = 0
        self.medal = None
        self.poop = None
        self.matsuri_gauge = None
        self.bigchance_gauge = None
        self.special_fish = None
        self.ticks = 0
        self.last_medal_detect = time.time()
        self.last_ocr_elapsed = 0.0
        self.last_ocr_since = time.time()

        # 続行不可判定
        self.jugdement_timer = None

        self.ss = None
        self.lock_ss = threading.Lock()

        self.oyaji_hunger = 92
        self.keyfish_hunger = 92

        if not NO_LOW_EXIT:
            self.first_chance = True

        if newgame:
            self.oyaji_hunger = 0
            self.keyfish_hunger = 0

        self.big_left = 42

        self.last_matsuri_gauge = 0
        self.last_bigchance_gauge = 0
        self.last_process_time = 0.0

        self.stage_name = None
        self.state = "normal"
        self.state_start = time.time()
        self.tamate = []

        self.last_medal_insert_time = time.time()
        self.last_mean_pix = 0

        self.endgame = False
        self.continued = False
        self.next_detect_window = time.time() + 120
        
        self._last_ss_saved = time.time() 

    def ocr_loop(self, c: Controller, shutdown):
        m = ImageMatcher()
        last_ss_id = 0
        logger.info("START OCR LOOP")
        while not shutdown.is_set():
            stt = time.time()
            try:
                if self.ss is None:
                    time.sleep(0.1)
                    continue
                ssid = id(self.ss)
                if last_ss_id == ssid:
                    time.sleep(1)
                    continue
                last_ss_id = ssid

                stime = time.time()
                with self.lock_ss:
                    img_game_screen = TemplateImage(self.ss, no_detect=True)
                kernel = np.ones((3, 3), np.uint8)

                crop_poop_ss = crop_relative(poop_area, img_game_screen)
                poop_ss = cv2.cvtColor(
                    cv2.morphologyEx(
                        detect_color(crop_poop_ss, (238, 68, 150)),
                        cv2.MORPH_OPEN,
                        kernel=kernel,
                    ),
                    cv2.COLOR_GRAY2BGR,
                )
                poop_num = m.ocr_text(poop_ss)

                crop_medal_ss = crop_relative(medal_area, img_game_screen)
                medal_ss = cv2.cvtColor(
                    cv2.morphologyEx(
                        detect_color(crop_medal_ss, (238, 68, 150)),
                        cv2.MORPH_OPEN,
                        kernel=kernel,
                    ),
                    cv2.COLOR_GRAY2BGR,
                )
                medal_num = m.ocr_text(medal_ss)

                stage_name = get_stage(img_game_screen)
                if stage_name is not None:
                    if LOG_IMAGE_NORMAL and self._last_ss_saved + 15 < time.time():
                        self._last_ss_saved = time.time()
                        ts = datetime.datetime.fromtimestamp(
                            stt, datetime.timezone(datetime.timedelta(hours=9))
                        )
                        os.makedirs(
                            f"./log/normal/{stage_name}/{ts.strftime('%Y%m%d%H%M%S')}/", exist_ok=True
                        )

                        log_path = (
                            f"./log/normal/{stage_name}/{ts.strftime('%Y%m%d%H%M%S')}/{ts:.3f}.png"
                        )
                        self.ss.save(log_path)

                    if is_valid_transision(self.stage_name, stage_name):
                        self.stage_name = stage_name

                try:
                    self.medal = int(medal_num)
                except:
                    pass
                    # logger.info(f"medal_num {medal_num}")

                try:
                    self.poop = int(poop_num)
                except:
                    pass
                    # logger.info(f"poop_num {poop_num}")

                try:
                    fields = {}
                    if self.medal is not None:
                        fields["medals"] = self.medal
                    if self.poop is not None:
                        fields["poop"] = self.poop

                    if self.state is not None:
                        fields["state"] = self.state
                    if self.stage_name is not None:
                        fields["stage_name"] = self.stage_name
                    if self.last_matsuri_gauge is not None:
                        fields["last_matsuri_gauge"] = self.last_matsuri_gauge
                    if self.last_bigchance_gauge is not None:
                        fields["last_bigchance_gauge"] = self.last_bigchance_gauge
                    if self.oyaji_hunger is not None:
                        fields["oyaji_hunger"] = self.oyaji_hunger
                    if self.keyfish_hunger is not None:
                        fields["keyfish_hunger"] = self.keyfish_hunger

                    write_influx(
                        f"suizoku_{LOGIN_ID.split('@')[0]}_medal_state", fields
                    )
                    self.last_medal_detect = stime
                except:
                    logger.exception("Influx send failed")
            except:
                logger.exception("failed")
            time.sleep(0.5)
            end = time.time()
            self.last_ocr_elapsed = end - stt
            self.last_ocr_since = stt
        logger.info("OCR SHUTDOWN OK")

    def ss_loop(self, c: Controller, shutdown):
        logger.info("START SS LOOP")

        last_mean_pix = 0

        while not shutdown.is_set():
            stt = time.time()
            try:
                with self.lock_ss:
                    try:
                        ss = c.take_image_from_video("//video")
                    except:
                        logger.exception("take video failed")
                        shutdown.set()
                        raise
                    self.ss = ss
                    img_game_screen = TemplateImage(ss, no_detect=True)

                mean_pix = np.array(ss).mean()
                self.last_mean_pix = mean_pix

                if self.state == "normal":
                    self.special_fish = detect_special_fish(ss)
                    self.tamate = []
                elif self.state == "matsuri":
                    self.special_fish = DetectSpecialFishResult(
                        oyaji=None, key_fish=None
                    )
                    self.tamate = detect_tamatebako(ss)

                if mean_pix >= 120:
                    # 暗いときには判定しない
                    matsuri_gauge = detect_matsuri_counter(img_game_screen)
                    if matsuri_gauge != self.last_matsuri_gauge:
                        if matsuri_gauge > self.last_matsuri_gauge:
                            self.oyaji_hunger = 90
                            logger.info(
                                "oyaji counter refreshed (%d -> %d)"
                                % (self.last_matsuri_gauge, matsuri_gauge)
                            )
                        self.last_matsuri_gauge = matsuri_gauge

                    bigchance_gauge = detect_bigchance_counter(img_game_screen)
                    if bigchance_gauge != self.last_bigchance_gauge:
                        if bigchance_gauge > self.last_bigchance_gauge:
                            self.keyfish_hunger = 92
                        self.last_bigchance_gauge = bigchance_gauge

                if mean_pix < 90 and last_mean_pix >= 90:
                    # dark screen detected
                    logger.info(
                        f"DARK SCREEN DETECTED {self.last_matsuri_gauge} {self.last_bigchance_gauge}"
                    )
                    if self.state == "matsuri" and self.first_chance:
                        self.first_chance = False
                        self.jugdement_timer = time.time() + 2

                    if self.last_matsuri_gauge == 3:
                        self.state = "matsuri"
                        self.state_start = time.time()
                    elif self.last_bigchance_gauge == 5:
                        self.state = "big"
                        self.big_left = 44
                        self.state_start = time.time()
                    else:
                        self.state = "normal"
                        logger.warning("INVALID STATE")

                last_mean_pix = mean_pix

            except KeyboardInterrupt:
                logger.info("SHUTDOWN")
                shutdown.set()
                raise
            except:
                logger.exception("failed")
            end = time.time()
            self.last_process_time = end - stt
            time.sleep(0.001)

        logger.info("SS SHUTDOWN OK")

    def tick(self, c: Controller, shutdown):
        oyaji_shown = False
        keyfish_shown = False
        oyaji_pos = None
        keyfish_pos = None

        if self.jugdement_timer is not None:
            if self.jugdement_timer < self.last_ocr_since:
                if self.medal < 95:
                    logger.info("低設定")
                    shutdown.set()
                    self.endgame = True
                    return
                else:
                    self.jugdement_timer = None

        if self.ss is not None:
            with self.lock_ss:
                disp_img = cv2.cvtColor(
                    np.array(self.ss.convert("RGBA")), cv2.COLOR_RGBA2BGRA
                )
            state_time = time.time() - self.state_start
            debug_text = f"""
                state = {self.state}
                stage_name = {self.stage_name}
                matsuri_gauge = {self.last_matsuri_gauge}
                bigchance_gauge = {self.last_bigchance_gauge}
                oyaji_hunger = {self.oyaji_hunger}
                keyfish_hunger = {self.keyfish_hunger}
                medal_num = {self.medal}
                poop_num = {self.poop}
                last_process_time = {self.last_process_time:.3f}
                last_ocr_elapsed = {self.last_ocr_elapsed:.3f}
                state_time = {state_time:.3f}
                mean_pix = {self.last_mean_pix:.3f}
                """
            if self.state == "big":
                debug_text += f"big_left = {self.big_left}"

            disp_img = put_text_in_image(
                disp_img,
                debug_text,
                "top-right",
                size=0.5,
                border=(255, 255, 255),
                color=(0, 0, 0),
            )

            if self.special_fish is not None:
                special_fish = self.special_fish
                if special_fish.oyaji:
                    oyaji_shown = True
                    x1, y1, x2, y2 = special_fish.oyaji
                    oyaji_pos = (
                        clamp((x1 + x2) / 2 / self.ss.width, 0.15, 0.85),
                        (y1 + y2) / 2 / self.ss.height,
                    )
                    disp_img = put_bbox(disp_img, special_fish.oyaji, "oyaji")
                if special_fish.key_fish:
                    keyfish_shown = True
                    x1, y1, x2, y2 = special_fish.key_fish

                    keyfish_pos = (
                        clamp((x1 + x2) / 2 / self.ss.width, 0.15, 0.85),
                        (y1 + y2) / 2 / self.ss.height,
                    )
                    disp_img = put_bbox(disp_img, special_fish.key_fish, "key")

            for item in self.tamate:
                x, y = item
                disp_img = put_bbox(
                    disp_img, (x - 50, y - 50, x + 50, y + 50), "tamate"
                )

            cv2.imshow("img", disp_img)
            cv2.waitKey(1)

        # keys = ["a", "s", "d"]
        # print(f"keydown {keys[self.ticks % 3]}")
        # c.key_down(keys[self.ticks % 3])
        positions = [
            (
                (self.ticks % 3) / 3 + 1 / 6 + 1 / 32 - 1 / 16 * random.random(),
                0.3 + 0.1 * random.random(),
            )
        ]
        # print(pos)
        launch = False
        gap = time.time() - self.last_medal_insert_time
        tamate_result = None

        medal_wait = 0.4
        if self.stage_name is not None:
            medal_wait = MEDAL_WAIT[self.stage_name]

        if self.state == "normal":
            if (
                self.oyaji_hunger <= 0
                and self.keyfish_hunger <= 0
                and (not self.first_chance)
            ):
                if oyaji_shown:
                    medal_wait /= 1.5
                    positions = [oyaji_pos]
                    launch = True
                elif keyfish_shown:
                    medal_wait /= 1.5
                    positions = [keyfish_pos]
                    launch = True
                else:
                    launch = False
            elif self.oyaji_hunger <= 0:
                if oyaji_shown:
                    medal_wait /= 1.5
                    positions = [oyaji_pos]
                    launch = True
                else:
                    launch = False
            elif self.keyfish_hunger <= 0 and (not self.first_chance):
                if keyfish_shown:
                    medal_wait /= 1.5
                    positions = [keyfish_pos]
                    launch = True
                else:
                    launch = False
            else:
                launch = True
            launch = launch and gap > medal_wait

        elif self.state == "matsuri":
            launch = gap > medal_wait
            if LOG_IMAGE_TAMATE:
                ts = datetime.datetime.fromtimestamp(
                    self.state_start, datetime.timezone(datetime.timedelta(hours=9))
                )
                os.makedirs(
                    f"./log/tamate/{ts.strftime('%Y%m%d%H%M%S')}/", exist_ok=True
                )

                log_path = (
                    f"./log/tamate/{ts.strftime('%Y%m%d%H%M%S')}/{state_time:.3f}.png"
                )
                self.ss.save(log_path)
            tamate_result = select_tamate(self.tamate, self.ss.size)
            if any(tamate_result):
                launch = gap > 0.1
                positions = []
                for i, b in enumerate(tamate_result):
                    if b:
                        positions.append(
                            (
                                (i % 3) / 3 + 1 / 6 + 1 / 32 - 1 / 16 * random.random(),
                                0.3 + 0.1 * random.random(),
                            )
                        )
            matsuri_state_time = time.time() - self.state_start
            if matsuri_state_time > 40:
                self.state = "normal"

        #            log_path = f"./log/matsuri/{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
        #            self.ss.save(log_path)
        elif self.state == "big":
            launch = False
            if LOG_IMAGE_BIG:
                ts = datetime.datetime.fromtimestamp(
                    self.state_start, datetime.timezone(datetime.timedelta(hours=9))
                )
                os.makedirs(
                    f"./log/bigchance/{ts.strftime('%Y%m%d%H%M%S')}/", exist_ok=True
                )

                log_path = f"./log/bigchance/{ts.strftime('%Y%m%d%H%M%S')}/{state_time:.3f}.png"
                self.ss.save(log_path)
            if self.auto and self.stage_name is not None and self.big_left > 0:
                self.ticks += 1
                with self.lock_ss:
                    big_state_time = time.time() - self.state_start
                    for t in big_timespan[self.stage_name]:
                        end_burst = self.state_start + t + 0.7
                        if t - 1.0 <= big_state_time <= t + 0.7:
                            while time.time() < end_burst and self.big_left > 0:
                                c.click_relative_pos(
                                    (
                                        1 / 2 + 1 / 32 - 1 / 16 * random.random(),
                                        0.3 + 0.1 * random.random(),
                                    ),
                                    "//video",
                                    pause=0,
                                )
                                self.last_medal_insert_time = time.time()
                                self.oyaji_hunger -= 1
                                self.keyfish_hunger -= 1
                                self.big_left -= 1
                                time.sleep(0.002)

        if launch and self.auto:
            self.ticks += 1
            with self.lock_ss:
                for pos in positions:
                    c.click_relative_pos(pos, "//video", pause=0.005)
                    self.last_medal_insert_time = time.time()
                    self.oyaji_hunger -= 1
                    self.keyfish_hunger -= 1

        if self.next_detect_window < time.time() and self.state == "normal":
            with self.lock_ss:
                if detect_window(c, not bonus_time()):
                    logger.info("球切れ")
                    shutdown.set()
                    self.endgame = True
                    self.continued = True
                else:
                    logger.info("終了確認を行いました")
            self.next_detect_window = time.time() + 60

    def tick_loop(self, c: Controller, shutdown):
        while not shutdown.is_set():
            try:
                self.tick(c, shutdown)
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt")
                shutdown.set()
                # c.close()
                raise
            except NoSuchWindowException:
                logger.info("NoSuchWindowException")
                shutdown.set()
                # c.close()
                raise
            except Exception:
                logger.exception("Unknown Exception")


COUNTER = 0

FIRST_START_DAY = datetime.datetime.now() - datetime.timedelta(hours=12)


def bonus_time():
    # 日が変わったら落とす
    global COUNTER

    if COUNTER >= const.REROLL_COUNT:
        return False
    COUNTER += 1

    if const.NO_CONDITION:
        return True

    dt = datetime.datetime.now() - datetime.timedelta(hours=12)
    return FIRST_START_DAY.day == dt.day


def start_ticker(c: Controller, newgame=False, **kwargs):
    first = True
    while bonus_time() or (first and not newgame):
        first = False
        ticker = Ticker(newgame=newgame, **kwargs)
        shutdown = threading.Event()

        with ThreadPoolExecutor(max_workers=4) as e:
            e.submit(ticker.ocr_loop, c, shutdown)
            e.submit(ticker.ss_loop, c, shutdown)
            ticker.tick_loop(c, shutdown)
            # ticker.ss_loop(c, shutdown)

        logger.info("閉じます")
        cv2.destroyAllWindows()
        logger.info("閉じました")

        if ticker.endgame:
            time.sleep(5)
            if not ticker.continued:
                finish_game(c, not bonus_time())

            for i in range(5):
                try:
                    focus_main_window(c)
                except:
                    time.sleep(2)
                else:
                    break
        else:
            break
