from typing import Tuple

import cv2
import numpy as np


def detect_color(img: np.array, color: Tuple[int, int, int], d: int = 50):
    c = np.array([[[*reversed(color)]]], dtype=np.uint8)
    color = cv2.cvtColor(c, cv2.COLOR_BGR2HSV_FULL)[0, 0].astype(np.int16)
    diff = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2HSV_FULL).astype(np.int16) - color
    diff = np.abs(diff)
    diff[:, :, 0] *= 3
    diff = np.minimum(255, np.sum(diff, axis=2))
    res = (diff).astype(np.uint8)
    return 255 - res


def detect_color_rgb(img: np.array, color: Tuple[int, int, int]):
    c = np.array([[[*reversed(color)]]], dtype=np.uint8)
    diff = img[:, :, :3] - color
    diff = np.abs(diff)
    diff = np.minimum(255, np.sum(diff, axis=2))
    res = (diff).astype(np.uint8)
    return 255 - res
