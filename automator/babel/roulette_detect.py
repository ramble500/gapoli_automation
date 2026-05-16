import datetime
import os

import cv2
import numpy as np

from automator.utils.detect import cv2pil
from automator.utils.template import ImageMatcher, TemplateImage

from .consts import *

LOG_ROULETTE_IMAGE = False


def create_distance_mask(shape, center, r, R):
    """
    指定されたサイズの2次元配列で、中心点からの距離がr以上R以下の部分だけが1になるマスクを生成します。

    Parameters:
    - shape: 配列の形 (height, width)
    - center: 中心点の座標 (cx, cy)
    - r: 最小距離
    - R: 最大距離

    Returns:
    - mask: 条件を満たす部分が1、それ以外は0の配列
    """
    height, width = shape
    cx, cy = center
    y, x = np.indices((height, width))
    distances = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    mask = (distances >= r) & (distances <= R)
    return mask.astype(np.uint8) * 255


def angle_check(img, center, n_rays=180, th=1):
    height, width = img.shape
    cx, cy = center
    y, x = np.indices((height, width))
    angles = np.round((n_rays / (2 * np.pi)) * np.atan2(x - cx, y - cy)) + 180
    v, fq = np.unique(angles[img == 0], return_counts=True)
    return sum(fq >= th) / n_rays


def detect_roulette_body(ss, debug=False):
    process_img = cv2.cvtColor(ss, cv2.COLOR_BGRA2GRAY)
    kernel_size = 5
    sigma = 0.1
    process_img = cv2.GaussianBlur(process_img, (kernel_size, kernel_size), sigma)

    circles = cv2.HoughCircles(
        process_img,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=20,
        param1=100,
        param2=40,
        minRadius=int(ss.shape[0] * 0.36),
        maxRadius=0,
    )

    if circles is None or len(circles) == 0:
        return None
    circles = np.uint16(np.around(circles))[0]
    circles = circles[np.argsort(-circles[:, 2])]  # 一番大きい円を取る

    mask = create_distance_mask(
        process_img.shape,
        (circles[0][0], circles[0][1]),
        int(circles[0][2] * 0.73),
        int(circles[0][2] * 0.95),
    )

    color_ring = cv2.bitwise_or(ss, cv2.cvtColor(~mask, cv2.COLOR_GRAY2BGR))
    is_magic = (
        np.sum(
            (color_ring[:, :, 0] > 192)
            & (color_ring[:, :, 1] < 192)
            & (color_ring[:, :, 2] > 192)
        )
        > 200
    )

    masked = cv2.bitwise_or(process_img, ~mask)
    _, masked = cv2.threshold(masked, 90, 255, cv2.THRESH_BINARY)
    atari = int(angle_check(masked, (circles[0][0], circles[0][1]), th=2) * 12)

    if LOG_ROULETTE_IMAGE:
        if bool(is_magic):
            log_path = f"./log/roulette/normal_{atari}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        else:
            log_path = f"./log/roulette/magic_{atari}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"

        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        cv2pil(ss).save(log_path)

    return atari, bool(is_magic)
