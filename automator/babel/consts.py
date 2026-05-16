import datetime
import io
import logging

import numpy as np
from IPython.display import Image, clear_output, display

from automator.utils.detect import cv2pil
from automator.utils.template import ImageMatcher, TemplateImage, vectorizer

logger = logging.getLogger(__name__)

continue_select = TemplateImage.from_path("./targets/continue_select.png")
cancel_button = TemplateImage.from_path("./targets/cancel_button.png")

roulette = TemplateImage.from_path("./targets/roulette.png")
press_button = TemplateImage.from_path("./targets/press_button.png")
main_screen = TemplateImage.from_path("./targets/main_screen.png")

logger.info("target image reloaded")
