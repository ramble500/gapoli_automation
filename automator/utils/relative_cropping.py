from dataclasses import dataclass

import PIL.Image

from automator.utils.template import TemplateImage


@dataclass
class RelativeCrop:
    xl: float
    xr: float
    yl: float
    yr: float

    def crop_pil(self, img: PIL.Image.Image) -> PIL.Image.Image:
        sw, sh = img.size
        xl = int(self.xl * sw)
        xr = int(self.xr * sw)
        yl = int(self.yl * sh)
        yr = int(self.yr * sh)
        return img.crop((xl, yl, xr, yr))


def crop_relative(crop: RelativeCrop, img: TemplateImage):
    sh, sw, _ = img.img.shape
    xl = int(crop.xl * sw)
    xr = int(crop.xr * sw)
    yl = int(crop.yl * sh)
    yr = int(crop.yr * sh)
    return img.img[yl:yr, xl:xr, :3]


def pos_relative(crop: RelativeCrop, img: TemplateImage):
    sh, sw, _ = img.img.shape
    xl = int(crop.xl * sw)
    xr = int(crop.xr * sw)
    yl = int(crop.yl * sh)
    yr = int(crop.yr * sh)
    return xl, xr, yl, yr


def center_relative(crop: RelativeCrop, img: TemplateImage):
    sh, sw, _ = img.img.shape
    xl = int(crop.xl * sw)
    xr = int(crop.xr * sw)
    yl = int(crop.yl * sh)
    yr = int(crop.yr * sh)
    return (xl + xr) // 2, (yl + yr) // 2
