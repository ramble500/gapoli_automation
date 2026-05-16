import logging
from datetime import datetime
from typing import Any, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageFile

logger = logging.getLogger(__name__)

THRESHOLD = 5
MIN_MATCHES = 5


def polygon_area(x, y):
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def calc_homography(size, kp1, kp2, matches) -> np.ndarray:
    src_pts = np.float32([kp1[m[0].queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m[0].trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

    matchesMask = mask.ravel().astype(np.bool)

    h, w = size
    pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
    if M is None:
        raise ValueError("M is none")
    dst = cv2.perspectiveTransform(pts, M)

    d = dst.reshape(4, 2)
    area = polygon_area(d[:, 0], d[:, 1]) / (h * w)
    sk0 = np.linalg.norm(d[1] - d[0]) / np.linalg.norm(d[3] - d[0]) / (h / w)
    sk1 = np.dot(d[1] - d[0], d[3] - d[0])
    sk2 = np.linalg.norm(d[1] + d[3] - d[0] - d[2])

    #   if sk0 < 0.9 or 1.1 < sk0:
    #       logger.info(sk0)
    #       raise ValueError("Skew")
    #
    #   if np.abs(sk2) > 0.05 * (h + w):
    #       raise ValueError("Skew")
    #
    #   if np.abs(area) < 1 / 400:
    #       raise ValueError("Small")

    inverted_points = cv2.perspectiveTransform(
        dst_pts[matchesMask], np.linalg.inv(M)
    ).reshape(-1, 2)
    validity = (
        (0 <= inverted_points[:, 0])
        & (inverted_points[:, 0] <= w)
        & (0 <= inverted_points[:, 1])
        & (inverted_points[:, 1] <= h)
    )
    valid_points = inverted_points[validity]

    if len(valid_points) < THRESHOLD:
        raise ValueError("THRESHOLD")

    return M

    with_frame = cv2.polylines(img2.copy(), [np.int32(dst)], True, 255, 3, cv2.LINE_AA)

    draw_params = dict(
        matchColor=(0, 255, 0),  # draw matches in green color
        singlePointColor=None,
        matchesMask=matchesMask,  # draw only inliers
        flags=2,
    )
    img3 = cv2.drawMatchesKnn(
        img1,
        kp1,
        with_frame,
        kp2,
        [matches[i] for i, v in enumerate(validity) if v],
        None,
        flags=2,
    )
    cv2.imwrite(f"log/{datetime.now().strftime('%Y%m%d%H%M%S')}.png", img3)
    return M


def match_akaze(
    img1: Image.Image, img2: ImageFile, distance_threshold=0.5
) -> np.ndarray:
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    detector = cv2.AKAZE_create()
    kp1, des1 = detector.detectAndCompute(gray1, None)
    kp2, des2 = detector.detectAndCompute(gray2, None)

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(des1, des2, k=2)

    good = []
    for m, n in matches:
        if m.distance < distance_threshold * n.distance:
            good.append([m])
    logger.debug("matched: %d, good: %d", len(matches), len(good))
    w, h = img1.size
    return calc_homography((h, w), kp1, kp2, good)


def match_sift(img1: ImageFile, img2: ImageFile, distance_threshold=0.5) -> np.ndarray:
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    detector = cv2.SIFT_create()
    kp1, des1 = detector.detectAndCompute(gray1, None)
    logger.debug("kp1: %d", len(kp1))
    kp2, des2 = detector.detectAndCompute(gray2, None)
    logger.debug("kp2: %d", len(kp2))

    bf = cv2.BFMatcher(cv2.NORM_L2)
    matches = bf.knnMatch(des1, des2, k=2)

    good = []
    for m, n in matches:
        if m.distance < distance_threshold * n.distance:
            good.append([m])
    logger.debug("matched: %d, good: %d", len(matches), len(good))
    w, h = img1.size
    return calc_homography((h, w), kp1, kp2, good)


def get_click_point(
    template: ImageFile, ss: ImageFile, with_log=True
) -> Tuple[float, float]:
    template = cv2.cvtColor(np.array(template.convert("RGB")), cv2.COLOR_RGB2BGR)
    ss = cv2.cvtColor(np.array(ss.convert("RGB")), cv2.COLOR_RGB2BGR)

    mat = match_akaze(template, ss)
    h, w, c = template.shape
    dst = cv2.perspectiveTransform(
        np.array([[w / 2, h / 2]]).reshape(-1, 1, 2), mat
    ).reshape(2)
    return dst[0], dst[1]


def get_similar_image(template, ss, with_log=True) -> Image:
    template = cv2.cvtColor(np.array(template.convert("RGB")), cv2.COLOR_RGB2BGR)
    ss = cv2.cvtColor(np.array(ss.convert("RGB")), cv2.COLOR_RGB2BGR)

    mat = match_sift(template, ss, distance_threshold=1)
    h, w, c = template.shape
    return cv2.warpPerspective(ss, np.linalg.inv(mat), (w, h))


def cv2pil(image):
    new_image = image.copy()
    if new_image.ndim == 2:  # モノクロ
        pass
    elif new_image.shape[2] == 3:  # カラー
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGR2RGB)
    elif new_image.shape[2] == 4:  # 透過
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGRA2RGBA)
    new_image = Image.fromarray(new_image)
    return new_image


def bbox(img):
    rows = np.any(img, axis=1)
    cols = np.any(img, axis=0)
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    return xmin, ymin, xmax + 1, ymax + 1


def crop_with_mask(mask, img):
    mask = 255 - cv2.threshold(mask[:, :, -1], 128, 255, cv2.THRESH_BINARY)[1]

    h, w, *_ = img.shape
    hm, wm, *_ = mask.shape
    mask = cv2.copyMakeBorder(
        mask, 0, max(h - hm, 0), 0, max(w - wm, 0), cv2.BORDER_CONSTANT, 0
    )[0:h, 0:w]

    xl, yl, xr, yr = bbox(mask)
    masked = (img & np.repeat(mask, img.shape[2], axis=None).reshape(img.shape))[
        yl:yr, xl:xr, :
    ]
    return cv2pil(masked), (xl, xr), (yl, yr)


def add_margin_pil(pil_img, top, right, bottom, left, color):
    width, height = pil_img.size
    new_width = width + right + left
    new_height = height + top + bottom
    result = Image.new(pil_img.mode, (new_width, new_height), color)
    result.paste(pil_img, (left, top))
    return result
