from dataclasses import dataclass

from automator.utils.template import TemplateImage


@dataclass
class RelativeCrop:
    xl: float
    xr: float
    yl: float
    yr: float

    def get_center(self):
        return (self.xl + self.xr) / 2, (self.yl + self.yr) / 2


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


medal_area = RelativeCrop(
    xl=0.7239583333333334, xr=0.9583333333333334, yl=0.8857421875, yr=0.947265625
)
poop_area = RelativeCrop(
    xl=0.5607638888888888, xr=0.65625, yl=0.8935546875, yr=0.94921875
)
