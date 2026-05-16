# coding: utf_8

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

model = YOLO("kizu.pt")
crop_stage_screen = RelativeCrop(
    xl=0.11607142857142858,
    xr=0.8839285714285714,
    yl=0.2193627450980392,
    yr=0.4166666666666667,
)


def main(c: Controller, hall: str):

    stage_name = "unknown"
    game_name = "パチスロ傷物語 -始マリノ刻-"

    for i in range(10):

        while True:
            c.driver.switch_to.default_content()
            c.wait_it(f'//span[contains(text(), "{game_name}")]')
            el = c.get_element(f'//span[contains(text(), "{game_name}")]')
            el.click()

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
            #     print(f"{i} user: {user_id} bb: {bb} rb: {rb} at: {at}")
            graph = seat["seat_data"]["graph"]
            graph_txt = json.dumps(graph, indent=2)
            graph_hash = sha256(graph_txt.encode()).hexdigest()
            if os.path.exists(f"log/hyena/graph_kizu/True/{graph_hash}.json"):
                logger.info(
                    f"---------------------------------Exists True {graph_hash}---------------------------------"
                )
            if os.path.exists(f"log/hyena/graph_kizu/False/{graph_hash}.json"):
                logger.info(
                    f"---------------------------------Exists False {graph_hash}---------------------------------"
                )
                continue

            if rb == 2:
                logger.info("RB=2の台を発見")

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

                crop_ss = crop_stage_screen.crop_pil(ss)

                result = model(crop_ss)[0]

                # print(result.probs)
                if result.probs.top1conf > 0.9:
                    stage_name = result.names[result.probs.top1]
                else:
                    logger.warning(
                        f"unknown stage with candidate {result.names[result.probs.top1]} ({result.probs.top1conf * 100}) %"
                    )
                    stage_name = "unknown"
                    raise ValueError(
                        f"unknown stage with candidate {result.names[result.probs.top1]} ({result.probs.top1conf * 100}) %"
                    )
                logger.info(f"stage_name={stage_name}")

                path = f"log/hyena/kizu/{stage_name}/{graph_hash}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                os.makedirs(os.path.dirname(path), exist_ok=True)
                c.save_ss(path, ss)

                path = (
                    f"log/hyena/graph_kizu/{stage_name == 'koudou'}/{graph_hash}.json"
                )
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf8") as f:
                    f.write(graph_txt)

                if stage_name != "unknown" and stage_name != "koudou":
                    finish_pachi_game(c, -1, hall)
                    c.wait_random()

                break
        else:
            logger.warning("no rb=2 seat!!")
            c.click_it("//div[contains(@class, '_closeIconOuter_')]")
            break

        if stage_name == "unknown":
            break
