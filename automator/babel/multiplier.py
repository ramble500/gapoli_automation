import cv2
import imgsim
import numpy as np

vct = imgsim.Vectorizer()

vs = np.array(
    [vct.vectorize(cv2.imread((f"targets/continue_x{i}.png"))) for i in range(1, 6)]
)


def get_multiplier(ss):
    return int(np.argmin(np.linalg.norm(vct.vectorize(ss) - vs, axis=1)) + 1)
