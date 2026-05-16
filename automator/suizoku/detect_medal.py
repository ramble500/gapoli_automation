from typing import Tuple

import cv2
import numpy as np
import pytesseract

from automator.utils.detect import add_margin_pil, cv2pil


def detect_color(img: np.array, color: Tuple[int, int, int], d: int = 50):
    c = np.array([[[*reversed(color)]]], dtype=np.uint8)
    color = cv2.cvtColor(c, cv2.COLOR_BGR2HSV_FULL)[0, 0].astype(np.int16)
    diff = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2HSV_FULL).astype(np.int16) - color
    diff = np.abs(diff)
    diff[:, :, 0] *= 3
    diff = np.minimum(255, np.sum(diff, axis=2))
    res = (diff).astype(np.uint8)
    return 255 - res


def get_medal_number(img):
    processed = (
        detect_color(
            np.array(img),
            (0xED, 0x40, 0x9E),  # ed419e
        )
        > 0
    )
    processed = processed.astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    #    processed = cv2.erode(processed, kernel)
    processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)
    processed = cv2.copyMakeBorder(
        processed, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )
    processed = cv2.resize(
        processed, (int(processed.shape[1] * 2), int(processed.shape[0] * 3))
    )

    try:
        ocr_str = pytesseract.image_to_string(
            processed,
            lang="eng",  # "outputbase digits"
        ).strip()

        return int(ocr_str)
    except:
        return None
