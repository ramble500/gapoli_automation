import logging

import cv2
import imgsim
import numpy as np

from automator.babel.main import RelativeCrop
from automator.suizoku.crop import crop_relative
from automator.utils.template import TemplateImage

logger = logging.getLogger(__name__)

vct = imgsim.Vectorizer()

target_icons = [
    "targets/stage_icon/arowana.png",
    "targets/stage_icon/kujira.png",
    "targets/stage_icon/same.png",
    "targets/stage_icon/jimbeizame.png",
    "targets/stage_icon/takitarou.png",
    "targets/stage_icon/nisikigoi.png",
]

names = [
    "arowana",
    "kujira",
    "same",
    "jimbeizame",
    "takitarou",
    "nisikigoi",
]

vs = np.array([vct.vectorize(cv2.imread(target_icons[i])) for i in range(6)])

keyfish_crop = RelativeCrop(
    xl=0.057291666666666664, xr=0.14756944444444445, yl=0.9072265625, yr=0.9521484375
)


def get_stage_similarity(ss: TemplateImage):
    ss = crop_relative(keyfish_crop, ss)
    vector = vct.vectorize(ss.astype(np.uint8))
    sims = vs @ vector.T
    sims /= np.linalg.norm(vs, axis=1)
    sims /= np.linalg.norm(vector)
    return sims


def get_stage(ss: TemplateImage):
    vector = get_stage_similarity(ss)
    if np.max(vector) < 0.8:
        return None
    else:
        return names[np.argmax(vector)]


def is_valid_transision(prev, next) -> bool:
    if prev is None:
        return True

    if prev == next:
        return True

    ORDER = ["same", "jimbeizame", "takitarou", "arowana", "nisikigoi", "kujira"]
    pi = ORDER.index(prev)
    ni = ORDER.index(next)
    if (ni - pi + 6) % 6 == 1:
        return True

    if (ni - pi + 6) % 6 == 5:
        logger.warning(f"BACKWARD Transition {prev} -> {next}")
        return True

    logger.warning(f"INVALID Transition {prev} -> {next}")
    return True
