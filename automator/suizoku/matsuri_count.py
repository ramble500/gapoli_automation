import numpy as np

from automator.babel.main import RelativeCrop, pos_relative
from automator.suizoku.crop import crop_relative
from automator.utils.detect_color import detect_color, detect_color_rgb
from automator.utils.template import TemplateImage


def detect_matsuri_counter(ss: TemplateImage):
    matsuri_block = [0.53472222, 0.6712963, 0.80787037, 0.94444444]

    matsuri_display_areas = [
        RelativeCrop(
            xl=matsuri_block[i], xr=matsuri_block[i + 1], yl=0.06640625, yr=0.1396484375
        )
        for i in range(3)
    ]

    im1 = crop_relative(matsuri_display_areas[0], ss)
    im2 = crop_relative(matsuri_display_areas[1], ss)
    im3 = crop_relative(matsuri_display_areas[2], ss)

    return int(
        sum(
            [
                (detect_color_rgb(im1, (0x25, 0x07, 0xC3)) > 100).mean() > 0.1,
                (detect_color_rgb(im2, (0x25, 0x07, 0xC3)) > 100).mean() > 0.1,
                (detect_color_rgb(im3, (0x25, 0x07, 0xC3)) > 100).mean() > 0.1,
            ]
        )
    )
