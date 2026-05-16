import csv
import logging
import os
import random
import shutil
from collections import defaultdict
from glob import glob
from pathlib import Path
from typing import Dict, List

import PIL.Image

logger = logging.getLogger(__name__)


def make_dataset(in_dir: str, out_dir: str, process=None, test_ratio: float = 0.1):
    class_items: Dict[str, List[str]] = defaultdict(lambda: [])
    for item in glob("**/*.png", root_dir=in_dir, recursive=True):
        src = Path(in_dir) / item

        classname = src.parts[-2]
        class_items[classname].append(item)

    for k, v in class_items.items():
        class_size = len(v)
        random.shuffle(v)
        test_size = int(class_size * test_ratio)
        for item in v[:test_size]:
            src = Path(in_dir) / item
            dest = Path(out_dir) / "test" / item

            os.makedirs(dest.parent, exist_ok=True)
            if process is None:
                shutil.copy2(src, dest)
            else:
                img = PIL.Image.open(src)
                img = process(img)
                img.save(dest)

            print(f"{src} => {dest}")

        for item in v[test_size:]:
            src = Path(in_dir) / item
            dest = Path(out_dir) / "train" / item

            os.makedirs(dest.parent, exist_ok=True)
            if process is None:
                shutil.copy2(src, dest)
            else:
                img = PIL.Image.open(src)
                img = process(img)
                img.save(dest)

            print(f"{src} => {dest}")


def make_dataset_from_text_label(
    in_label: str, in_dir: str, out_dir: str, process=None, test_ratio: float = 0.1
):
    class_items: Dict[str, List[str]] = defaultdict(lambda: [])

    d = {}

    with open(Path(in_dir) / in_label, "r", encoding="utf8") as f:
        for row in csv.reader(f):
            if len(row) != 2:
                continue
            file, label = row
            d[file] = str(label)

    for item in glob("*.png", root_dir=in_dir, recursive=True):
        src = Path(in_dir) / item

        classname = src.parts[-2]
        class_items[classname].append(item)

    for k, v in class_items.items():
        class_size = len(v)
        random.shuffle(v)
        test_size = int(class_size * test_ratio)
        for item in v[:test_size]:
            if item not in d:
                logger.warning(f"invalid {item}")
                continue

            src = Path(in_dir) / item
            dest = Path(out_dir) / "test" / d[item] / item

            os.makedirs(dest.parent, exist_ok=True)
            if process is None:
                shutil.copy2(src, dest)
            else:
                img = PIL.Image.open(src)
                img = process(img)
                img.save(dest)

            print(f"{src} => {dest}")

        for item in v[test_size:]:
            if item not in d:
                logger.warning(f"invalid {item}")
                continue

            src = Path(in_dir) / item
            dest = Path(out_dir) / "train" / d[item] / item

            os.makedirs(dest.parent, exist_ok=True)
            if process is None:
                shutil.copy2(src, dest)
            else:
                img = PIL.Image.open(src)
                img = process(img)
                img.save(dest)

            print(f"{src} => {dest}")
