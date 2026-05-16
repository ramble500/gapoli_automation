from .detect import get_click_point
from .detect_color import detect_color


def clamp(x, l, r):
    if x < l:
        return l
    elif x > r:
        return r
    else:
        return x
