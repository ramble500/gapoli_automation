import time

from automator.login import Controller


def finish_game(c: Controller):
    # 精算する

    c.driver.switch_to.default_content()
    c.click_it('//div[contains(@class, "_checkButtonWrapper")]')
    time.sleep(0.4)
    try:
        c.click_it('//button[text()="精算"]')
    except:
        c.login("https://gapoli.net/game/20206")
        c.click_it('//button[text()="精算する"]')
        c.click_it('//button[text()="閉じる"]')
        return
    time.sleep(0.4)

    try:
        c.click_it('//button[text()="続けて遊ぶ"]')
    except:
        c.login("https://gapoli.net/game/20206")
        c.click_it('//button[text()="精算する"]')
        c.click_it('//button[text()="閉じる"]')


def win_loop(c: Controller):
    c.login("https://gapoli.net/game/20206")
    c.wait_loaded()

    c.click_it('//button[text()="プレイ"]')
    c.click_it('//div[contains(@class, "_pulldown")]')

    c.click_it(f'//div[contains(@class, "_pullDownItem")]//span[contains(text(), "1")]')
    c.click_it('//button[text()="レート決定"]')

    c.wait_it(xpath='//span[text()="チップ交換"]', timeout=30)

    c.click_it('//div[contains(@class, "_pulldown")]')
    c.click_it(
        '//div[contains(@class, "_pullDownItem")]//span[contains(text(), "1,000")]'
    )
    c.click_it('//button[text()="プレイ開始"]')

    time.sleep(3)

    ss = c.take_photo_of("//iframe")
    w, h = ss.size

    c.click_pos2((454 * w / 500, 813 * h / 849), "//iframe")
    time.sleep(0.4)
    c.click_pos2((65 * w / 500, 742 * h / 849), "//iframe")
    c.click_pos2((65 * w / 500, 742 * h / 849), "//iframe")
    time.sleep(0.4)
    c.click_pos2((39 * w / 500, 325 * h / 849), "//iframe")
    time.sleep(0.4)
    c.click_pos2((247 * w / 500, 733 * h / 849), "//iframe")
    time.sleep(0.4)

    time.sleep(10)

    finish_game(c)


def loop(c: Controller, loop_count: int = 70, mode: str = "win"):
    for i in range(loop_count):
        win_loop(c)
