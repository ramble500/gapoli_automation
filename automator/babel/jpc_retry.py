import cv2
import numpy as np

from automator.babel.roulette_detect import create_distance_mask


def get_retry_roulette(ss, debug=False):
    process_img = cv2.cvtColor(ss, cv2.COLOR_BGRA2GRAY)
    kernel_size = 5
    sigma = 0.1
    process_img = cv2.GaussianBlur(process_img, (kernel_size, kernel_size), sigma)

    circles = cv2.HoughCircles(
        process_img,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=100,
        param1=100,
        param2=40,
        minRadius=int(ss.shape[0] * 0.36),
        maxRadius=0,
    )

    circles = np.uint16(np.around(circles))[0]
    circles = circles[np.argsort(-circles[:, 2])]  # 一番大きい円を取る

    mask = create_distance_mask(
        process_img.shape,
        (circles[0][0], circles[0][1]),
        int(circles[0][2] * 0.9),
        int(circles[0][2] * 1.1),
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

    return bool(is_magic)
