import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import ultralytics
from ultralytics.engine.results import Results as YOLOResult

yolo_model = ultralytics.YOLO("tamate.pt")


def detect_tamatebako(ss) -> List[Tuple[int, int]]:
    res = []

    result: YOLOResult = yolo_model(ss)
    for r in result:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            if box.cls == 0:
                res.append(((x1 + x2) // 2, (y1 + y2) // 2))

    return res
