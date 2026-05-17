import io
import logging
import os
import random
import sys
import time
from base64 import b64decode
from pathlib import Path
from tempfile import TemporaryFile
from typing import Optional, Tuple

import cv2
import numpy as np
import selenium
from PIL import Image, ImageFile
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .utils.detect import get_click_point, get_similar_image

logger = logging.getLogger(__name__)

class Controller:

    def __init__(
        self,
        fallback_chromium: bool = False,
        headless: bool = False,
        backend="chrome",
        network_logging: bool = False,
        no_mute: bool = False,
    ):
        custom_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        #        options.add_argument('--headless')
        os.environ["DISPLAY"] = ":1"
        if backend == "firefox":
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.firefox.webdriver import (
                WebDriver as FirefoxWebDriver,
            )

            options = FirefoxOptions()
            options.add_argument(f"--user-agent={custom_user_agent}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            if not no_mute:
                options.add_argument("--mute-audio")
            driver = FirefoxWebDriver(options=options)
        else:
            try:
                import chromedriver_binary_sync
                from selenium.webdriver.chrome.service import Service as ChromeService

                chromedriver_path = (
                    os.path.dirname(os.path.dirname(__file__)) + "/chromedriver/"
                )
                chromedriver_binary_sync.download(download_dir=chromedriver_path)
                sys.path.insert(0, chromedriver_path)

                options = ChromeOptions()
                options.add_argument(f"--user-agent={custom_user_agent}")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--start-maximized")
                if not no_mute:
                    options.add_argument("--mute-audio")
                options.add_argument("--incognito")
                options.add_argument("--no-sandbox")
                options.add_argument(
                    "--host-resolver-rules=MAP www.google-analytics.com 127.0.0.1"
                )
                options.add_argument("--disable-background-networking")
                options.add_argument("--disable-background-timer-throttling")

                if network_logging:
                    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

                # userdata_dir = Path("./log/userdata/")
                # profile_dir = Path("./log/profile/")
                # userdata_dir.mkdir(parents=True, exist_ok=True)
                # profile_dir.mkdir(parents=True, exist_ok=True)
                # options.add_argument(f'--user-data-dir={userdata_dir.absolute()}')
                # options.add_argument(f'--profile-directory={profile_dir.absolute()}')

                options.add_experimental_option(
                    "prefs", {"profile.default_content_setting_values.notifications": 2}
                )
                options.add_experimental_option(
                    "excludeSwitches", ["enable-automation", "enable-logging"]
                )
                if headless:
                    options.add_argument("--headless")
                service = ChromeService(
                    executable_path=chromedriver_path + "chromedriver.exe"
                )
                driver = Chrome(service=service, options=options)
            except Exception:
                if fallback_chromium:
                    from selenium.webdriver.chromium.options import ChromiumOptions
                    from selenium.webdriver.chromium.webdriver import ChromiumDriver

                    options = ChromiumOptions()
                    options.add_argument(f"--user-agent={custom_user_agent}")
                    options.add_argument(
                        "--disable-blink-features=AutomationControlled"
                    )
                    if not no_mute:
                        options.add_argument("--mute-audio")
                    options.add_experimental_option(
                        "excludeSwitches", ["enable-automation", "enable-logging"]
                    )
                    driver = ChromiumDriver(options=options)
                else:
                    raise

        self.driver = driver
        try:
            self.driver.maximize_window()
        except Exception:
            logger.warning("failed to maximize browser window", exc_info=True)
        self.last_ss = None
        self.ratio = float(self.driver.execute_script("return window.devicePixelRatio"))

    def login(self, url):
        driver = self.driver
        driver.get(url)
        logger.info(driver.current_url)

    def close(self):
        self.driver.close()

    def click_it(self, xpath, timeout=10):
        driver = self.driver
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        for i in range(10):
            try:
                el = driver.find_element(By.XPATH, xpath)
                self.click_element(el)
            except selenium.common.exceptions.StaleElementReferenceException:
                continue
            break

    def click_element(self, el):
        width, height = self._get_element_size(el)
        self._click_element_point_with_mouse(el, (width / 2, height / 2))

    def scroll_into(self, xpath, timeout=10):
        driver = self.driver
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

        ac = ActionChains(self.driver, duration=40)
        el = self.driver.find_element(By.XPATH, xpath)
        ac.scroll_to_element(el)
        ac.perform()

    def wait_it(self, xpath, timeout=10):
        driver = self.driver
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return self.driver.find_element(By.XPATH, xpath)

    def get_element(self, xpath):
        try:
            return self.driver.find_element(By.XPATH, xpath)
        except:
            return None

    def get_elements(self, xpath):
        try:
            return self.driver.find_elements(By.XPATH, xpath)
        except:
            return None

    def input_text(self, xpath, text):
        driver = self.driver
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        el = driver.find_element(By.XPATH, xpath)
        el.send_keys(text)

    def wait(self, sec):
        time.sleep(sec)

    def wait_random(self, sec=1.0):
        self.wait(sec * (random.random() * 0.6 + 0.7))

    def wait_loaded(self):
        driver = self.driver
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located)

    def wait_forever(self):
        logger.info("WAIT FOREVER...")
        driver = self.driver
        WebDriverWait(driver, 10**9).until(EC.url_to_be("_"))

    def take_photo(self) -> ImageFile:
        driver = self.driver
        img = driver.get_screenshot_as_png()
        return Image.open(io.BytesIO(img))

    def take_photo_of(self, xpath: str) -> ImageFile:
        driver = self.driver
        img = driver.get_screenshot_as_png()
        img = Image.open(io.BytesIO(img))
        el = driver.find_element(By.XPATH, xpath)
        ratio = float(self.driver.execute_script("return window.devicePixelRatio"))
        # ref: https://qiita.com/ozoneboy/items/b57bf4e67110b3756390
        rect_s = self.driver.execute_script(
            """
        return (function(el) {
            const pos = { top: 0, left: 0, bottom: 0, right: 0};
            pos.top = el.getBoundingClientRect().top;
            pos.left = el.getBoundingClientRect().left;
            pos.bottom = el.getBoundingClientRect().bottom;
            pos.right = el.getBoundingClientRect().right;

            let doc = el.ownerDocument;
            let childWindow = doc.defaultView;

            while (window.top !== childWindow) {
                pos.top += childWindow.frameElement.getBoundingClientRect().top;
                pos.left += childWindow.frameElement.getBoundingClientRect().left;
                pos.bottom += childWindow.frameElement.getBoundingClientRect().top;
                pos.right += childWindow.frameElement.getBoundingClientRect().left;
                childWindow = childWindow.parent;
            }
            return pos
        })(arguments[0])
        """,
            el,
        )
        left = rect_s["left"] * ratio
        top = rect_s["top"] * ratio
        right = rect_s["right"] * ratio
        bottom = rect_s["bottom"] * ratio
        self.last_ss = img.crop((left, top, right, bottom))
        return self.last_ss

    def take_image_from_video(self, xpath):
        # https://qiita.com/udonchan/items/77ca19f9aa8420e769c8
        capture_frame = """
        return (function(video){
            var canvas = document.createElement('canvas');
            var ctx = canvas.getContext('2d')
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0);
            var dataURL = canvas.toDataURL('image/jpeg');
            return dataURL;
        })(arguments[0])
        """
        driver = self.driver
        el = driver.find_element(By.XPATH, xpath)
        data_url = self.driver.execute_script(capture_frame, el)
        img = b64decode(data_url.split("base64,", 1)[1])
        self.last_ss = Image.open(io.BytesIO(img))
        return self.last_ss

    def take_image_from_canvas(self, xpath):
        capture_frame = """
        return (function(canvas){
            var ctx = canvas.getContext('2d')
            var dataURL = canvas.toDataURL('image/png');
            return dataURL;
        })(arguments[0])
        """
        driver = self.driver
        el = driver.find_element(By.XPATH, xpath)
        data_url = self.driver.execute_script(capture_frame, el)
        img = b64decode(data_url.split("base64,", 1)[1])
        self.last_ss = Image.open(io.BytesIO(img))
        return self.last_ss

    def save_ss(self, path: os.PathLike, image: ImageFile, silent: bool = False):
        if not silent:
            logger.info("Image Save to " + path)
        try:
            image.save(path)
        except:
            logger.exception("ss save error")

    def get_dom(self):
        return self.driver.execute_script("return document.documentElement.outerHTML")

    def _get_element_size(self, el) -> Tuple[float, float]:
        size = self.driver.execute_script(
            """
            const el = arguments[0];
            if (el === document.body || el === document.documentElement) {
                return {
                    width: document.documentElement.clientWidth || window.innerWidth,
                    height: document.documentElement.clientHeight || window.innerHeight,
                };
            }
            const rect = el.getBoundingClientRect();
            const width = rect.width || el.clientWidth || el.offsetWidth;
            const height = rect.height || el.clientHeight || el.offsetHeight;
            return {width, height};
            """,
            el,
        )
        return float(size["width"]), float(size["height"])

    def get_size(self, xpath: Optional[str] = None) -> Tuple[int, int]:
        if xpath is None:
            el = self.driver.find_element(By.TAG_NAME, "body")
        else:
            el = self.driver.find_element(By.XPATH, xpath)

        width, height = self._get_element_size(el)
        return int(round(width)), int(round(height))

    def click_pos(
        self,
        pos: Tuple[float, float],
        relative_from_xpath: str = None,
        no_mult: bool = True,
        ratio: float = 1,
        context: bool = False,
    ):
        if relative_from_xpath is not None:
            el = self.driver.find_element(By.XPATH, relative_from_xpath)
        else:
            el = self.driver.find_element(By.TAG_NAME, "body")
        width, height = self._get_element_size(el)
        if no_mult:
            ratio *= 1
        else:
            ratio *= float(self.driver.execute_script("return window.devicePixelRatio"))

        pos = (pos[0] / ratio, pos[1] / ratio)
        logger.debug(f"width: {width}, height: {height} ratio: {ratio}")
        self._click_element_point_with_mouse(el, pos, context=context)

    def click_pos2(
        self,
        pos: Tuple[float, float],
        relative_from_xpath: str = None,
        no_mult: bool = True,
        ratio: float = 1,
        context: bool = False,
    ):
        if relative_from_xpath is not None:
            el = self.driver.find_element(By.XPATH, relative_from_xpath)
        else:
            el = self.driver.find_element(By.TAG_NAME, "body")
        width, height = self._get_element_size(el)
        if no_mult:
            ratio *= 1
        else:
            ratio *= float(self.driver.execute_script("return window.devicePixelRatio"))

        pos = (pos[0] / ratio, pos[1] / ratio)
        rect_s = self.driver.execute_script(
            "return arguments[0].getBoundingClientRect()", el
        )
        logger.info(f"width: {width}, height: {height} ratio: {ratio} rect: {rect_s}")
        self._click_element_point_with_mouse(
            el, pos, context=context, use_offset_action=True
        )

    def click_relative_pos(
        self,
        relative_pos: Tuple[float, float],
        relative_from_xpath: str = None,
        context: bool = False,
        pause=0.04,
    ):
        if relative_from_xpath is not None:
            el = self.driver.find_element(By.XPATH, relative_from_xpath)
        else:
            el = self.driver.find_element(By.TAG_NAME, "body")
        width, height = self._get_element_size(el)

        pos = (
            relative_pos[0] * width,
            relative_pos[1] * height,
        )
        logger.debug(f"width: {width}, height: {height} x: {pos[0]}, y: {pos[1]}")
        self._click_element_point_with_mouse(
            el, pos, context=context, pause=pause
        )

    def _click_element_point_with_mouse(
        self,
        el,
        pos: Tuple[float, float],
        context: bool = False,
        pause: float = 0.04,
        use_offset_action: bool = False,
    ):
        width, height = self._get_element_size(el)
        self._scroll_element_point_into_view(el, pos)
        info = self._get_element_point_visibility(el, pos)
        if not info["clickable"]:
            raise selenium.common.exceptions.MoveTargetOutOfBoundsException(
                f"target point is not visibly clickable: {info}"
            )

        ac = ActionChains(self.driver, duration=int(pause * 1000))
        if use_offset_action:
            ac.move_to_element_with_offset(
                el, int(pos[0] - width / 2), int(pos[1] - height / 2)
            )
        else:
            ac.move_to_element(el)
            ac.move_by_offset(int(pos[0] - width / 2), int(pos[1] - height / 2))
        if context:
            ac.context_click()
        else:
            ac.click_and_hold()
            ac.pause(pause)
            ac.release()
        ac.perform()

    def _get_element_point_visibility(self, el, pos):
        return self.driver.execute_script(
            """
            const el = arguments[0];
            const x = arguments[1];
            const y = arguments[2];
            const rect = el.getBoundingClientRect();
            const targetX = rect.left + x;
            const targetY = rect.top + y;
            const style = window.getComputedStyle(el);
            const inViewport =
                targetX >= 0 &&
                targetY >= 0 &&
                targetX < window.innerWidth &&
                targetY < window.innerHeight;
            const hit = inViewport
                ? document.elementFromPoint(targetX, targetY)
                : null;
            const targetReceivesClick = hit === el || el.contains(hit);
            const hitClassName =
                hit && hit.className && hit.className.baseVal !== undefined
                    ? hit.className.baseVal
                    : String(hit ? hit.className : "");
            return {
                clickable:
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    style.pointerEvents !== "none" &&
                    inViewport &&
                    targetReceivesClick,
                inViewport,
                targetReceivesClick,
                hitTagName: hit ? hit.tagName : null,
                hitClassName,
                targetX,
                targetY,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                elementWidth: rect.width,
                elementHeight: rect.height,
            };
            """,
            el,
            pos[0],
            pos[1],
        )

    def _scroll_element_point_into_view(self, el, pos):
        return self.driver.execute_script(
            """
            const el = arguments[0];
            const x = arguments[1];
            const y = arguments[2];
            const margin = 20;

            const scrollTargetIntoView = () => {
                const rect = el.getBoundingClientRect();
                const targetX = rect.left + x;
                const targetY = rect.top + y;
                let dx = 0;
                let dy = 0;

                if (targetX < margin) {
                    dx = targetX - margin;
                } else if (targetX > window.innerWidth - margin) {
                    dx = targetX - (window.innerWidth - margin);
                }

                if (targetY < margin) {
                    dy = targetY - margin;
                } else if (targetY > window.innerHeight - margin) {
                    dy = targetY - (window.innerHeight - margin);
                }

                if (dx !== 0 || dy !== 0) {
                    window.scrollBy(dx, dy);
                }
            };

            scrollTargetIntoView();
            const rect = el.getBoundingClientRect();
            return {
                targetX: rect.left + x,
                targetY: rect.top + y,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                elementWidth: rect.width,
                elementHeight: rect.height,
            };
            """,
            el,
            pos[0],
            pos[1],
        )

    def mouseshake(self, relative_from_xpath: str = None):
        ac = ActionChains(self.driver, duration=40)
        if relative_from_xpath is not None:
            el = self.driver.find_element(By.XPATH, relative_from_xpath)
        else:
            el = self.driver.find_element(By.TAG_NAME, "body")
        width = int(el.get_attribute("clientWidth"))
        height = int(el.get_attribute("clientHeight"))

        ac.move_to_element(el)
        ac.move_by_offset(random.randint(-100, 100), random.randint(-100, 100))
        ac.perform()

    def click_target_by_image(self, template_image_path: os.PathLike):
        ss_image = self.take_photo()
        template_image = Image.open(template_image_path)
        cp = get_click_point(template_image, ss_image)
        logger.info(cp)
        self.click_pos(cp)

    def clip_similar_image(self, template_image_path: os.PathLike):
        ss_image = self.take_photo()
        template_image = Image.open(template_image_path)
        cp = get_click_point(template_image, ss_image)
        return get_similar_image(template_image, ss_image)

    def key_down(self, key: Keys | str, el_xpath: Optional[str] = None, times=1):
        ac = ActionChains(self.driver, duration=40)
        if el_xpath is not None:
            el_xpath = self.get_element(el_xpath)

        for _ in range(times):
            ac.key_down(key, el_xpath)
            ac.pause(0.04)
            ac.key_up(key, el_xpath)
        ac.perform()

    def dragdrop(self, pos_start, pos_end_relative_on_window, relative_from_xpath: str = None):
        ac = ActionChains(self.driver, duration=400)
        if relative_from_xpath is not None:
            el = self.driver.find_element(By.XPATH, relative_from_xpath)
        else:
            el = self.driver.find_element(By.TAG_NAME, "body")

        el_body = self.driver.find_element(By.TAG_NAME, "body")
        width = int(el_body.get_attribute("clientWidth"))
        height = int(el_body.get_attribute("clientHeight"))
        pos_end = (width * (pos_end_relative_on_window[0] - 0.5), height * (pos_end_relative_on_window[1] - 0.5))

        ac.move_to_element(el)
        ac.move_by_offset(pos_start[0], pos_start[1])
        ac.click_and_hold()
        ac.move_to_element_with_offset(self.driver.find_element(By.TAG_NAME, "body"), pos_end[0], pos_end[1])
        ac.release()
        ac.perform()

    def set_css_attribute_all(self, xpath, attrib, value):
        try:
            els = self.driver.find_elements(By.XPATH, xpath)
            for el in els:
                self.driver.execute_script(
                    f'arguments[0].style.{attrib} = "{value}";',
                    el
                )
        except Exception as e:
            logger.warning('set_css_attribute: no such object (%s)' % xpath)
