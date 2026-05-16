import datetime
import io
import logging
import time
from dataclasses import dataclass

import numpy as np

from automator.babel.jpc_retry import get_retry_roulette
from automator.babel.multiplier import get_multiplier
from automator.babel.roulette_detect import detect_roulette_body
from automator.login import Controller
from automator.utils.detect import cv2pil
from automator.utils.influx import write_influx
from automator.utils.template import ImageMatcher, TemplateImage, vectorizer

from .consts import continue_select, main_screen, press_button, roulette

logger = logging.getLogger(__name__)

last_medal = 0
last_medal_time = datetime.datetime(2038, 1, 1, 0, 0, 0)


def detect_red_button(ss):
    cropped = crop_relative(red_button, ss)
    v_crop = vectorizer.vectorize(cropped)
    red_button_similarity = np.linalg.norm(v_crop - press_button.vector)
    logger.debug(f"red_button_similarity: {red_button_similarity}")
    if red_button_similarity < 20:
        return center_relative(red_button, ss)
    else:
        return None


def judge_continue_jp(cost, multiplier, atari, magic):
    logger.info(f"cost={cost}, multiplier={multiplier}, atari={atari}, magic={magic}")
    the_table = [
        [5, 2, 0, 0, 0],
        [11, 7, 5, 3, 2],
        [99, 99, 11, 8, 6],  # [99,11,8,6,5],
    ]
    if cost == 70:
        if not magic:
            return True
        return the_table[0][multiplier - 1] <= atari
    elif cost == 140:
        return the_table[1][multiplier - 1] <= atari
    elif cost == 210:
        return the_table[2][multiplier - 1] <= atari
    else:
        logger.warning(f"Invalid cost: {cost}")
        return np.random.randint(10) < 5
        raise ValueError(f"Invalid cost: {cost}")


@dataclass
class RelativeCrop:
    xl: float
    xr: float
    yl: float
    yr: float


def crop_relative(crop: RelativeCrop, img: TemplateImage):
    sh, sw, _ = img.img.shape
    xl = int(crop.xl * sw)
    xr = int(crop.xr * sw)
    yl = int(crop.yl * sh)
    yr = int(crop.yr * sh)
    return img.img[yl:yr, xl:xr, :3]


def pos_relative(crop: RelativeCrop, img: TemplateImage):
    sh, sw, _ = img.img.shape
    xl = int(crop.xl * sw)
    xr = int(crop.xr * sw)
    yl = int(crop.yl * sh)
    yr = int(crop.yr * sh)
    return xl, xr, yl, yr


def center_relative(crop: RelativeCrop, img: TemplateImage):
    sh, sw, _ = img.img.shape
    xl = int(crop.xl * sw)
    xr = int(crop.xr * sw)
    yl = int(crop.yl * sh)
    yr = int(crop.yr * sh)
    return (xl + xr) // 2, (yl + yr) // 2


medal_area = RelativeCrop(
    xl=0.5225694444444444, xr=0.71875, yl=0.939453125, yr=0.9775390625
)
limit_area = RelativeCrop(
    xl=0.22395833333333334, xr=0.3420138888888889, yl=0.0126953125, yr=0.0341796875
)
continue_button_area = RelativeCrop(
    xl=0.07291666666666667, xr=0.4618055555555556, yl=0.7578125, yr=0.818359375
)
cancel_button_area = RelativeCrop(
    xl=0.5416666666666666, xr=0.921875, yl=0.7607421875, yr=0.814453125
)
# JPC (ジャックポット突入抽選の再開抽選)
jpc_roulette_on_continue = RelativeCrop(
    xl=0.1736111111111111, xr=0.5625, yl=0.17578125, yr=0.404296875
)

# JP (ジャックポット中の再開抽選)
retry_roulette_area = RelativeCrop(
    xl=0.010416666666666666, xr=0.2482638888888889, yl=0.3076171875, yr=0.4462890625
)

red_button = RelativeCrop(
    xl=0.4496527777777778, xr=0.5625, yl=0.818359375, yr=0.8798828125
)
multiplier_area = RelativeCrop(
    xl=0.19270833333333334, xr=0.2465277777777778, yl=0.2470703125, yr=0.2783203125
)

last_roulette = datetime.datetime.now()


class BabelAutomator:
    def tick(self, c: Controller):
        pass


def tick(c: Controller, no_continue: bool = False):
    global last_medal, last_medal_time, last_roulette
    img_game_screen = c.take_image_from_video("//video")
    screen_ratio = img_game_screen.size[0] / c.get_size("//video")[0]
    img_game_screen = TemplateImage(img_game_screen)
    m = ImageMatcher()

    medal_bar_num = m.ocr_text(crop_relative(medal_area, img_game_screen))
    medal_limit_num = m.ocr_text(crop_relative(limit_area, img_game_screen))
    if medal_bar_num == "":
        medal_bar_num = None
    if medal_limit_num == "":
        medal_limit_num = None

    roulette_pos = m.click_point(roulette, img_game_screen)
    press_button_pos = None
    try:
        press_button_pos = detect_red_button(img_game_screen)
    except:
        pass

    if m.get_bbox(continue_select, img_game_screen) is not None:
        continue_select_res = m.ocr_text(
            crop_relative(continue_button_area, img_game_screen),
            config="outputbase digits",
        )
        if continue_select_res != "":
            logger.info(f"CONTINUE DETECTED")
            continue_select_num = int(continue_select_res)
        else:
            continue_select_num = None
    else:
        continue_select_num = None

    main_screen_res = m.get_bbox(main_screen, img_game_screen)
    logger.debug("medal amount : %s" % medal_bar_num)
    logger.debug("medal limit : %s" % medal_limit_num)
    logger.debug("roulette: %s" % str(roulette_pos))
    logger.debug("press_button: %s" % str(press_button_pos))
    logger.debug("continue_select: %s" % continue_select_num)
    logger.debug(f"main_screen_res: {main_screen_res}")

    medal_limit = None
    try:
        fields = {}
        try:
            fields["medals"] = int(medal_bar_num)
        except:
            pass
        try:
            medal_limit = int(medal_limit_num)
            fields["limit"] = int(medal_limit_num)
        except:
            pass
        write_influx("medal_state", fields)
    except:
        logger.exception("Influx send failed")

    is_in_jpc = main_screen_res is not None
    if roulette_pos is not None and (
        datetime.datetime.now() - last_roulette
    ) > datetime.timedelta(seconds=5):
        logger.info(f"PRESS ROULETTE {roulette_pos}")
        c.click_pos(roulette_pos, "//video", ratio=screen_ratio)
        last_roulette = datetime.datetime.now()
    if press_button_pos is not None:
        logger.info(f"PRESS RED BUTTON {press_button_pos}")
        c.click_pos(press_button_pos, "//video", ratio=screen_ratio)
    if continue_select_num is not None:
        try:
            logger.info(f"is_in_jpc: {is_in_jpc}")
            atari = None
            magic = None
            if is_in_jpc:
                mul = get_multiplier(crop_relative(multiplier_area, img_game_screen))
                atari, magic = detect_roulette_body(
                    crop_relative(retry_roulette_area, img_game_screen)
                )

                judge_result = judge_continue_jp(continue_select_num, mul, atari, magic)
            else:
                magic = get_retry_roulette(
                    crop_relative(jpc_roulette_on_continue, img_game_screen)
                )
                judge_result = not magic

            if medal_limit is None or medal_limit < 100 or no_continue:
                judge_result = False

            if judge_result:
                logger.info(f"PRESS CONTINUE")
                if is_in_jpc:
                    write_influx(
                        "event_continue_jp",
                        {
                            "cost": continue_select_num,
                            "atari": atari,
                            "is_magic": magic,
                            "current_multiplier": mul,
                        },
                    )
                else:
                    write_influx(
                        "event_continue_retry_jpc",
                        {"cost": continue_select_num, "is_magic": magic},
                    )
                c.click_pos(
                    center_relative(continue_button_area, img_game_screen),
                    "//video",
                    ratio=screen_ratio,
                )
                time.sleep(0.3)
            else:
                logger.info(f"PRESS CANCEL")
                if is_in_jpc:
                    write_influx(
                        "event_cancel_jp",
                        {
                            "cost": continue_select_num,
                            "atari": atari,
                            "is_magic": magic,
                            "current_multiplier": mul,
                        },
                    )
                else:
                    write_influx(
                        "event_cancel_retry_jpc",
                        {"cost": continue_select_num, "is_magic": magic},
                    )
                c.click_pos(
                    center_relative(cancel_button_area, img_game_screen),
                    "//video",
                    ratio=screen_ratio,
                )
                time.sleep(0.3)
        except:
            logger.exception("JPC REVIVE ROULETTE DETECT ERROR", stack_info=True)
            c.click_pos(
                center_relative(continue_button_area, img_game_screen),
                "//video",
                ratio=screen_ratio,
            )

    if medal_bar_num is None or len(medal_bar_num) != 5:
        logger.info(f"medal num detect error: {medal_bar_num}")
    else:
        current_medal = int(medal_bar_num)
        if current_medal != last_medal:
            last_medal = current_medal
            last_medal_time = datetime.datetime.now()

    if medal_limit_num is None or len(medal_limit_num) != 5:
        logger.info(f"medal limit detect error: {medal_limit_num}")

    logger.debug(f"from last medal: {datetime.datetime.now() - last_medal_time}")
    if not is_in_jpc and datetime.datetime.now() - last_medal_time > datetime.timedelta(
        seconds=5
    ):
        logger.info("MEDAL GO")
        c.key_down(" ", times=5)
        last_medal_time = datetime.datetime.now()

    # img_bytes = io.BytesIO()
    # cv2pil(img.img).save(img_bytes, format='PNG')

    # display(Image(img_bytes.getvalue()))
