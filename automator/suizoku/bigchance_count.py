import numpy as np

from automator.suizoku.crop import RelativeCrop, crop_relative
from automator.utils.detect_color import detect_color_rgb
from automator.utils.template import TemplateImage

gauge_area = RelativeCrop(xl=0.14, xr=0.42, yl=0.9275, yr=0.93)


def detect_bigchance_counter(ss: TemplateImage):
    cropped = crop_relative(gauge_area, ss)
    m = detect_color_rgb(cropped, (0x20, 0x20, 0x20))

    return int(5 - np.round((m > 128).sum() / m.size / 0.9 * 5))
