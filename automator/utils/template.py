import datetime
import logging
import os
from os import PathLike
from typing import Optional, Tuple, TypeAlias

import cv2
import imgsim
import numpy as np
from PIL import Image

from .detect import add_margin_pil, calc_homography, crop_with_mask, cv2pil

logger = logging.getLogger(__name__)

akaze = cv2.AKAZE_create()
sift = cv2.SIFT_create()

FLANN_INDEX_KDTREE = 0
FLANN_INDEX_LSH = 6

flann_matcher_sift = cv2.FlannBasedMatcher(
    {"algorithm": FLANN_INDEX_KDTREE, "trees": 5}, {"checks": 50}
)
flann_matcher_akaze = cv2.FlannBasedMatcher(
    {
        "algorithm": FLANN_INDEX_LSH,
        "table_number": 6,
        "key_size": 12,
        "multi_probe_level": 1,
    },
    {"checks": 50},
)
bf_matcher = cv2.BFMatcher(cv2.NORM_L2)
vectorizer = imgsim.Vectorizer()

IMAGE_TYPE: TypeAlias = "TemplateImage | Image.Image"


class TemplateImage:
    img: np.ndarray

    def __init__(self, img: Image.Image, no_detect: bool = False):
        img = cv2.cvtColor(np.array(img.convert("RGBA")), cv2.COLOR_RGBA2BGRA)
        if not no_detect:
            akaze_kp, akaze_des = akaze.detectAndCompute(img, None)
            sift_kp, sift_des = sift.detectAndCompute(img, None)

            self.akaze_kp = akaze_kp
            self.akaze_des = akaze_des
            self.sift_kp = sift_kp
            self.sift_des = sift_des
            self.vector = vectorizer.vectorize(img[:, :, :3])
        self.img = img

    @classmethod
    def from_path(cls, path: PathLike) -> "TemplateImage":
        return cls(Image.open(path))

    def get_size(self):
        h, w, *_ = self.img.shape
        return h, w


class SerializableKeyPoint:
    def __init__(self, keypoint):
        self.pt = keypoint.pt
        self.size = keypoint.size
        self.angle = keypoint.angle
        self.response = keypoint.response
        self.octave = keypoint.octave
        self.class_id = keypoint.class_id

    def to_cv2_keypoint(self):
        return cv2.KeyPoint(
            x=self.pt[0],
            y=self.pt[1],
            size=self.size,
            angle=self.angle,
            response=self.response,
            octave=self.octave,
            class_id=self.class_id,
        )


class TemplateParams:
    # 画像なし、パラメータのみ

    def __init__(self, akaze_kp, akaze_des, sift_kp, sift_des, vector, size):
        self.akaze_kp = akaze_kp
        self.akaze_des = akaze_des
        self.sift_kp = sift_kp
        self.sift_des = sift_des
        self.vector = vector
        self.size = size

    def get_size(self):
        return self.size

    @property
    def img(self):
        raise NotImplementedError("parameter only, no img")

    def __getstate__(self):
        return {
            "akaze_kp": [SerializableKeyPoint(item) for item in self.akaze_kp],
            "akaze_des": self.akaze_des,
            "sift_kp": [SerializableKeyPoint(item) for item in self.sift_kp],
            "sift_des": self.sift_des,
            "vector": self.vector,
            "size": self.size,
        }

    def __setstate__(self, state):
        self.akaze_kp = [item.to_cv2_keypoint() for item in state["akaze_kp"]]
        self.akaze_des = state["akaze_des"]
        self.sift_kp = [item.to_cv2_keypoint() for item in state["sift_kp"]]
        self.sift_des = state["sift_des"]
        self.vector = state["vector"]
        self.size = state["size"]

    @classmethod
    def from_template_img(cls, img: TemplateImage) -> "TemplateParams":
        return cls(
            akaze_kp=img.akaze_kp,
            akaze_des=img.akaze_des,
            sift_kp=img.sift_kp,
            sift_des=img.sift_des,
            vector=img.vector,
            size=img.get_size(),
        )


class ImageMatcher:
    def __init__(self):
        self.akaze_distance_threshold = 0.5
        self.sift_distance_threshold = 0.5

    def _img_cast(self, img: IMAGE_TYPE) -> TemplateImage:
        if isinstance(img, TemplateImage):
            return img
        else:
            return TemplateImage(img)

    def _sift_match(self, template: TemplateImage, img: IMAGE_TYPE):
        img = self._img_cast(img)
        logger.debug("kp_sift: %d", len(img.sift_kp))

        matches = flann_matcher_sift.knnMatch(template.sift_des, img.sift_des, k=2)

        good = []
        for m, n in matches:
            if m.distance < self.sift_distance_threshold * n.distance:
                good.append([m])
        logger.debug("matched: %d, good: %d", len(matches), len(good))
        if len(good) < 5:
            return None
        try:
            return calc_homography(
                template.get_size(), template.sift_kp, img.sift_kp, good
            )
        except:
            return None

    def _akaze_match(self, template: TemplateImage, img: IMAGE_TYPE):
        img = self._img_cast(img)
        logger.debug("kp_akaze: %d", len(img.akaze_kp))

        matches = flann_matcher_akaze.knnMatch(template.akaze_des, img.akaze_des, k=2)

        good = []
        for m, n in matches:
            if m.distance < self.akaze_distance_threshold * n.distance:
                good.append([m])
        logger.debug("matched: %d, good: %d", len(matches), len(good))
        if len(good) < 5:
            return None
        try:
            return calc_homography(
                template.get_size(), template.akaze_kp, img.akaze_kp, good
            )
        except:
            return None

    def match_object(
        self, template: TemplateImage, img: IMAGE_TYPE, debug: bool = False
    ):
        sift_matched = self._sift_match(template, img)
        if debug:
            logger.info(f"sift_matched: {sift_matched}")
        if sift_matched is None:
            akaze_matched = self._akaze_match(template, img)
            if debug:
                logger.info(f"akaze_matched: {akaze_matched}")
        else:
            return sift_matched

    def crop_template_matched(
        self, template: TemplateImage, img: Image
    ) -> Optional[Image.Image]:
        img = self._img_cast(img)

        mat = self.match_object(template, img)
        if mat is None:
            return None
        h, w, c = template.img.shape
        return cv2.warpPerspective(img.img, np.linalg.inv(mat), (w, h)), mat

    def crop_if_detected(self, template: TemplateImage, img: IMAGE_TYPE):
        crop_template_matched = self.crop_template_matched(template, img)
        if crop_template_matched is None:
            return None
        similar_area, mat = crop_template_matched
        cropped, (xl, xr), (yl, yr) = crop_with_mask(template.img, similar_area)

        pts = np.float32([[xl, yl], [xl, yr], [xr, yr], [xr, yl]]).reshape(-1, 4, 2)
        dst = cv2.perspectiveTransform(pts, mat).reshape(4, 2)
        xl, xr, yl, yr = (
            int(np.min(dst[:, 0])),
            int(np.max(dst[:, 0])),
            int(np.min(dst[:, 1])),
            int(np.max(dst[:, 1])),
        )
        return cropped, (xl, xr), (yl, yr)

    def crop_text(
        self,
        template: TemplateImage,
        img: IMAGE_TYPE,
        lang="jpn",
        config="outputbase digits",
        **kwargs,
    ) -> Optional[Tuple[str, Tuple[int, int], Tuple[int, int]]]:
        import pytesseract

        def threshold(img):
            img = np.array(img.convert("L"), "f")
            img = (img > 128).astype(np.uint8) * 255
            return cv2pil(img)

        cropped = self.crop_if_detected(template, img)
        if cropped is None:
            return None
        cropped, (xl, xr), (yl, yr) = cropped
        return self.ocr_text(cropped), (xl, xr), (yl, yr)

    def ocr_text(
        self,
        img: IMAGE_TYPE,
        lang="jpn",
        config="outputbase digits",
        log_image=False,
        **kwargs,
    ) -> str:
        import pytesseract

        def threshold(img):
            img = np.array(img.convert("L"), "f")
            img = (img > 128).astype(np.uint8) * 255
            return cv2pil(img)

        if isinstance(img, np.ndarray):
            img = cv2pil(img)

        img = add_margin_pil(img, 10, 10, 10, 10, (0, 0, 0))

        result_text = ""
        result_text = pytesseract.image_to_string(
            img, lang=lang, config=config, **kwargs
        ).strip()
        if result_text == "":
            img_bin = threshold(img)
            result_text = pytesseract.image_to_string(
                img_bin, lang=lang, config=config, **kwargs
            ).strip()

        if result_text == "" and log_image:
            log_path = f"./log/failed_text/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.png"
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            img.save(log_path)
            logger.warning("Failed to recognize image: %s", log_path)

        return result_text

    def click_point(self, template: TemplateImage, img: IMAGE_TYPE):
        img = self._img_cast(img)

        mat = self.match_object(template, img)
        if mat is None:
            return None
        h, w = template.get_size()
        try:
            dst = cv2.perspectiveTransform(
                np.array([[w / 2, h / 2]]).reshape(-1, 1, 2), mat
            ).reshape(2)
        except:
            logger.exception("%d %d %s", h, w, mat)
        return dst[0], dst[1]

    def get_bbox(self, template: TemplateImage, img: IMAGE_TYPE):
        img = self._img_cast(img)

        mat = self.match_object(template, img)
        if mat is None:
            return None
        h, w = template.get_size()
        pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(
            -1, 4, 2
        )
        dst = cv2.perspectiveTransform(pts, mat).reshape(4, 2)
        ih, iw = img.get_size()
        return (
            max(0, min(iw, int(np.min(dst[:, 0])))),
            max(0, min(ih, int(np.min(dst[:, 1])))),
            max(0, min(iw, int(np.max(dst[:, 0])))),
            max(0, min(ih, int(np.max(dst[:, 1])))),
        )
