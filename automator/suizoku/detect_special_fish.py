import os
from dataclasses import dataclass
from typing import Optional, Tuple

import ultralytics
from ultralytics.engine.results import Results as YOLOResult

yolo_model = ultralytics.YOLO("oyaji_keyfish.pt")


@dataclass
class DetectSpecialFishResult:
    oyaji: Optional[Tuple[float, float, float, float]]
    key_fish: Optional[Tuple[float, float, float, float]]


def detect_special_fish(ss) -> DetectSpecialFishResult:
    oyaji = None
    key_fish = None

    result: YOLOResult = yolo_model(ss)
    for r in result:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            if box.cls == 0:
                oyaji = (x1, y1, x2, y2)
            elif box.cls == 1:
                key_fish = (x1, y1, x2, y2)

    return DetectSpecialFishResult(oyaji=oyaji, key_fish=key_fish)
