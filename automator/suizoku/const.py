__all__ = ["big_timespan", "MEDAL_WAIT", "NO_LOW_EXIT"]

from automator.utils.template import TemplateImage

big_timespan = {
    "arowana": [25.315, 37.701, 50.718],
    "kujira": [24.523, 37.146, 49.763],
    "jimbeizame": [24.573, 37.280, 49.997],
    "same": [21.768, 32.952, 44.084],
    "takitarou": [21.681, 33.021, 44.088],
    "nisikigoi": [21.760, 33.012, 44.007],
}

MEDAL_WAIT = {
    "arowana": 0.4,
    "kujira": 0.4,
    "jimbeizame": 0.9,
    "same": 0.6,
    "takitarou": 0.4,
    "nisikigoi": 1.0,
}

RATE = None
NO_CONDITION = False
REROLL_COUNT = 999
NO_LOW_EXIT = False
