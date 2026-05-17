# coding: utf_8

break_flag = False

import datetime
import json
import logging
import os
from hashlib import sha256

from ultralytics import YOLO

from automator.hyena.utils import (
    block_everyone,
    finish_pachi_game,
    focus_main_window,
    get_seats_info,
)
from automator.login import Controller
from automator.utils.relative_cropping import RelativeCrop

logger = logging.getLogger(__name__)


def main(c: Controller, hall: str):
    game_name = "スマスロ真・北斗無双"

    for i in range(10):

        while True:
            c.driver.switch_to.default_content()
            c.wait_it(f'//span[contains(text(), "{game_name}")]')
            el = c.get_element(f'//span[contains(text(), "{game_name}")]')
            c.click_element(el)

            c.wait_random()

            block_cnt = block_everyone(c)

            if block_cnt > 0:
                c.click_it("//div[contains(@class, '_closeIconOuter_')]")
            else:
                break

        logger.info("ブロック処理完了")

        if (
            c.get_element("//span[contains(text(),'台情報を取得できませんでした。')]")
            is not None
        ):
            c.click_it("//button[contains(text(), '閉じる')]")
            break
        c.wait_it("//button[contains(text(), 'この台を選択')]")

        seats_info = get_seats_info(c)

        seats_enter = c.get_elements("//button[contains(text(), 'この台を選択')]")

        for i, seat in enumerate(seats_info):
            status = seat["status"]
            user = seat.get("seated_user_profile", {})
            user_id = None
            if user is not None:
                user_id = user.get("identify_id")

            bb = seat["seat_data"]["count1"]
            rb = seat["seat_data"]["count2"]
            at = seat["seat_data"]["count3"]
            dif = seat["seat_data"]["difference_count"]
            #     print(f"{i} user: {user_id} bb: {bb} rb: {rb} at: {at}")

            graph = seat["seat_data"]["graph"]
            graph_txt = json.dumps(graph, indent=2)
            graph_hash = sha256(graph_txt.encode()).hexdigest()
            if os.path.exists(
                f"log/hyena/seat_data_ss_hokuto_musou/True/{graph_hash}.json"
            ):
                logger.info(
                    f"---------------------------------Exists True {graph_hash}---------------------------------"
                )
            if os.path.exists(
                f"log/hyena/seat_data_ss_hokuto_musou/False/{graph_hash}.json"
            ):
                logger.info(
                    f"---------------------------------Exists False {graph_hash}---------------------------------"
                )
                continue

            high = 0
            for seg in graph:
                if seg["mode"] == "BB":
                    big_diff = seg["list"][-1]["diff"] - seg["list"][0]["diff"]
                    if big_diff >= 280:
                        high += 1
                    else:
                        pass

            if high >= 4:
                logger.info("台を発見")

                seats_enter[i].click()
                c.wait_random()
                c.click_it("//button[contains(text(), 'プレイ')]")
                c.wait_it(
                    "//div[contains(@class, '_titleContainer_')]/span[contains(text(), 'メダル交換')]",
                    timeout=30,
                )

                c.click_it(
                    "//div[contains(@class, '_titleContainer_')]/span[contains(text(), 'メダル交換')]/../following-sibling::div[1]/div[contains(@class, '_closeContainer_')]"
                )

                focus_main_window(c, -1)

                c.wait_random()

                ss = c.take_image_from_video("//video")

                path = f"log/hyena/ss_hokuto_musou/{graph_hash}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                os.makedirs(os.path.dirname(path), exist_ok=True)
                c.save_ss(path, ss)

                path = f"log/hyena/seat_data_ss_hokuto_musou/{graph_hash}.json"
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf8") as f:
                    f.write(json.dumps(seat["seat_data"], indent=2, ensure_ascii=False))

                if True:
                    finish_pachi_game(c, -1, hall)
                    c.wait_random()
                    break
                else:
                    raise ValueError("good seat reserved")
        else:
            logger.warning("no suitable seat!!")
            c.click_it("//div[contains(@class, '_closeIconOuter_')]")
            break
