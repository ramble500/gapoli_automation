import cv2
import numpy as np


def is_dark_screen(ss):
    mean_pix = np.array(ss).mean()
    if mean_pix < 100:
        return True
    else:
        return False


def put_text_in_image(
    img,
    text,
    place="bottom-right",
    size=1,
    color=(255, 255, 255),
    thickness=2,
    margin=5,
    border=None,
):
    """
    画像に文字を入れる

    Parameters
    ----------
    img : np.array
        文字を入れたい画像イメージ（cv2形式）

    text : str
        入れたい文字列（英数字のみ）

    place : str
        'top' : 上部中央
        'top-left' : 上部左寄せ
        'top-right' : 上部右寄せ
        'center' : 中央
        'bottom' : 下部中央
        'bottom-left' : 下部左寄せ
        'bottom-right' : 下部右寄せ

    size : float
        フォントサイズ

    color : str
        文字色。['black', 'red', 'blue', 'green', 'orange', 'yellow', 'white']のいずれか

    thickness : int > 0
        フォントの太さ

    margin : int
        余白の大きさ

    bordering : dic
        縁取りしたい時に指定する
        'color' : 縁取りの色
        'thickness' : 縁取りの太さ

    return : np.array
        ウィンドウの画像イメージ（cv2形式）
        ウィンドウが見つからなかった場合はNoneを返す
    """
    text = str(text)

    height = int(50 * size)
    width = int(len(text) * 20 * size + 10 + thickness - 1)
    blank = np.zeros((height, width, 3))

    current_y = 0
    max_width = 0
    ys = []
    for i, line in enumerate(text.split("\n")):
        (line_width, line_height), baseline = cv2.getTextSize(
            line, cv2.FONT_HERSHEY_SIMPLEX, size, thickness
        )
        current_y += line_height + baseline
        max_width = max(max_width, line_width)
        ys.append(current_y - baseline)

    text_img = img.copy()
    img_height, img_width = img.shape[:2]

    for i, line in enumerate(text.split("\n")):
        if border:
            cv2.putText(
                text_img,
                line,
                (img_width - max_width, ys[i]),
                fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                fontScale=size,
                color=border,
                thickness=thickness + 1,
            )
        cv2.putText(
            text_img,
            line,
            (img_width - max_width, ys[i]),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=size,
            color=color,
            thickness=thickness,
        )

    return text_img


def put_bbox(img, bbox, name):
    x1, y1, x2, y2 = bbox
    img = cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
    return cv2.putText(
        img,
        name,
        (int(x1), int(y1) - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 0),
        2,
    )
