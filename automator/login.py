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
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
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
        deadline = time.monotonic() + timeout
        last_info = None
        last_exception = None
        next_log_at = 0

        while time.monotonic() < deadline:
            found = False
            for el in self.driver.find_elements(By.XPATH, xpath):
                found = True
                try:
                    width, height = self._get_element_size(el)
                    info = self._get_element_point_visibility(
                        el, (width / 2, height / 2)
                    )
                    last_info = info
                    if not info["clickable"]:
                        continue

                    remaining = max(0.2, deadline - time.monotonic())
                    self._click_element_point_with_mouse(
                        el, (width / 2, height / 2), timeout=remaining
                    )
                    return
                except selenium.common.exceptions.StaleElementReferenceException as e:
                    last_exception = e
                    continue
                except selenium.common.exceptions.MoveTargetOutOfBoundsException as e:
                    last_exception = e
                    continue

            now = time.monotonic()
            if now >= next_log_at:
                logger.info(
                    "waiting for visibly clickable target: xpath=%s found=%s last=%s",
                    xpath,
                    found,
                    last_info,
                )
                next_log_at = now + 1.0
            time.sleep(0.2)

        if last_info is not None:
            raise selenium.common.exceptions.MoveTargetOutOfBoundsException(
                f"target did not become visibly clickable: xpath={xpath} last={last_info}"
            )
        if last_exception is not None:
            raise last_exception
        raise selenium.common.exceptions.TimeoutException(
            f"target was not found before timeout: xpath={xpath}"
        )

    def click_element(self, el):
        width, height = self._get_element_size(el)
        self._click_element_point_with_mouse(el, (width / 2, height / 2))

    def click_visible_item(
        self,
        xpath,
        scroll_origin_xpath=None,
        timeout=10,
        max_scrolls=10,
        scroll_amount=240,
    ):
        driver = self.driver
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

        last_info = None
        for attempt in range(max_scrolls + 1):
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    width, height = self._get_element_size(el)
                    info = self._get_element_point_visibility(
                        el, (width / 2, height / 2)
                    )
                    last_info = info
                    if info["clickable"]:
                        logger.info(
                            "visible item selected: xpath=%s attempt=%d info=%s",
                            xpath,
                            attempt,
                            info,
                        )
                        self._click_element_point_with_mouse(
                            el, (width / 2, height / 2)
                        )
                        return
                except selenium.common.exceptions.StaleElementReferenceException:
                    continue

            if attempt >= max_scrolls:
                break

            scroll_el = self._get_scroll_origin_for_item(
                xpath,
                fallback_xpath=scroll_origin_xpath,
            )
            scroll_info = self._describe_element(scroll_el)
            amount = self._get_scroll_amount_toward(last_info, scroll_amount)
            logger.info(
                "visible item not found; scroll dropdown: xpath=%s attempt=%d amount=%s origin=%s last=%s",
                xpath,
                attempt + 1,
                amount,
                scroll_info,
                last_info,
            )
            self.scroll_wheel(scroll_el, amount)
            time.sleep(0.25)

        raise selenium.common.exceptions.MoveTargetOutOfBoundsException(
            f"no visibly clickable item found: xpath={xpath} last={last_info}"
        )

    def scroll_wheel(self, origin=None, amount=240):
        if origin is None:
            origin_el = self.driver.find_element(By.TAG_NAME, "body")
        elif isinstance(origin, str):
            origin_el = self.driver.find_element(By.XPATH, origin)
        else:
            origin_el = origin

        offsets = self._get_visible_scroll_origin_offsets(origin_el)
        logger.info(
            "mouse wheel target: amount=%s offsets=%s origin=%s",
            amount,
            offsets,
            self._describe_element(origin_el),
        )
        ac = ActionChains(self.driver, duration=80)
        ac.scroll_from_origin(
            ScrollOrigin.from_element(
                origin_el,
                int(offsets["x"]),
                int(offsets["y"]),
            ),
            0,
            amount,
        )
        ac.perform()

    def _get_scroll_origin_for_item(self, xpath, fallback_xpath=None):
        candidates = self.driver.find_elements(By.XPATH, xpath)
        if candidates:
            origin = self.driver.execute_script(
                """
                const el = arguments[0];
                let candidate = null;
                let node = el.parentElement;
                while (node && node !== document.documentElement) {
                    const scrollable = node.scrollHeight > node.clientHeight + 2;
                    const style = window.getComputedStyle(node);
                    const overflowY = style.overflowY || "";
                    if (scrollable && overflowY !== "visible" && overflowY !== "hidden") {
                        return node;
                    }
                    if (scrollable && candidate === null) {
                        candidate = node;
                    }
                    node = node.parentElement;
                }
                return candidate;
                """,
                candidates[0],
            )
            if origin is not None:
                return origin

        if fallback_xpath is not None:
            elements = self.driver.find_elements(By.XPATH, fallback_xpath)
            for el in reversed(elements):
                try:
                    width, height = self._get_element_size(el)
                    info = self._get_element_point_visibility(
                        el, (width / 2, height / 2)
                    )
                    if info["clickable"]:
                        return el
                except selenium.common.exceptions.StaleElementReferenceException:
                    continue
            if elements:
                return elements[-1]

        return self.driver.find_element(By.TAG_NAME, "body")

    def _get_scroll_amount_toward(self, info, default_amount):
        if not info:
            return default_amount

        target_y = info.get("topTargetY", info.get("targetY", 0))
        viewport_height = info.get(
            "topViewportHeight",
            info.get("viewportHeight", self.driver.get_window_size()["height"]),
        )
        if target_y < 80:
            return -abs(default_amount)
        if target_y > viewport_height - 120:
            return abs(default_amount)
        return abs(default_amount)

    def _describe_element(self, el):
        return self.driver.execute_script(
            """
            const el = arguments[0];
            if (!el) {
                return null;
            }
            const rect = el.getBoundingClientRect();
            const className =
                el.className && el.className.baseVal !== undefined
                    ? el.className.baseVal
                    : String(el.className || "");
            return {
                tagName: el.tagName,
                className,
                rect: {
                    left: rect.left,
                    top: rect.top,
                    right: rect.right,
                    bottom: rect.bottom,
                },
                scrollTop: el.scrollTop,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
            };
            """,
            el,
        )

    def _get_visible_scroll_origin_offsets(self, el):
        return self.driver.execute_script(
            """
            const el = arguments[0];
            const rect = el.getBoundingClientRect();
            const visibleLeft = Math.max(rect.left, 0);
            const visibleTop = Math.max(rect.top, 0);
            const visibleRight = Math.min(rect.right, window.innerWidth);
            const visibleBottom = Math.min(rect.bottom, window.innerHeight);
            const centerX = (rect.left + rect.right) / 2;
            const centerY = (rect.top + rect.bottom) / 2;

            const points = [];
            const x = (visibleLeft + visibleRight) / 2;
            for (const ratio of [0.2, 0.35, 0.5, 0.65, 0.8]) {
                points.push({
                    x,
                    y: visibleTop + (visibleBottom - visibleTop) * ratio,
                });
            }

            for (const point of points) {
                const hit = document.elementFromPoint(point.x, point.y);
                if (hit === el || el.contains(hit)) {
                    return {
                        x: point.x - centerX,
                        y: point.y - centerY,
                        hitTagName: hit ? hit.tagName : null,
                    };
                }
            }

            return {x: 0, y: 0, hitTagName: null};
            """,
            el,
        )

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

    def wait_loaded(self, timeout=30):
        driver = self.driver
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )

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
        self._click_element_point_with_mouse(el, pos, context=context)

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
        timeout: float = 10.0,
    ):
        frame_path = self._get_frame_path_to_top()
        info = None
        deadline = time.monotonic() + timeout
        next_log_at = 0

        while time.monotonic() < deadline:
            max_attempts = 3
            for attempt in range(max_attempts):
                self._scroll_element_point_into_view(el, pos)
                info = self._get_element_point_visibility(el, pos)
                if info["clickable"]:
                    break

                if (
                    not info["topInViewport"]
                    and info["targetReceivesClick"]
                    and attempt < max_attempts - 1
                    and self._drag_window_to_show_top_target(info, frame_path)
                ):
                    logger.info(
                        "target was outside top viewport; retried after window drag: %s",
                        info,
                    )
                    continue

                break

            if info is not None and info["clickable"]:
                break

            now = time.monotonic()
            if now >= next_log_at:
                logger.info("waiting for visibly clickable point: %s", info)
                next_log_at = now + 1.0
            time.sleep(0.2)

        if info is None or not info["clickable"]:
            self._restore_frame_path(frame_path)
            raise selenium.common.exceptions.MoveTargetOutOfBoundsException(
                f"target point did not become visibly clickable: {info}"
            )

        try:
            self.driver.switch_to.default_content()
            target = self._get_top_viewport_click_origin(info)
            logger.info(f"mouse click target: {target['log']}")
            ac = ActionChains(self.driver, duration=int(pause * 1000))
            ac.move_to_element_with_offset(
                target["element"],
                int(info["topTargetX"] - target["centerX"]),
                int(info["topTargetY"] - target["centerY"]),
            )
            if context:
                ac.context_click()
            else:
                ac.click_and_hold()
                ac.pause(pause)
                ac.release()
            ac.perform()
        finally:
            self._restore_frame_path(frame_path)

    def _drag_window_to_show_top_target(self, info, frame_path):
        margin = 24
        dx = 0
        dy = 0
        if info["topTargetX"] < margin:
            dx = margin - info["topTargetX"]
        elif info["topTargetX"] > info["topViewportWidth"] - margin:
            dx = (info["topViewportWidth"] - margin) - info["topTargetX"]

        if info["topTargetY"] < margin:
            dy = margin - info["topTargetY"]
        elif info["topTargetY"] > info["topViewportHeight"] - margin:
            dy = (info["topViewportHeight"] - margin) - info["topTargetY"]

        if dx == 0 and dy == 0:
            return False

        self.driver.switch_to.default_content()
        drag_handle = self._get_drag_handle_for_frame_path(frame_path)
        if drag_handle is None:
            self._restore_frame_path(frame_path)
            return False

        drag_x = int(max(min(dx, 160), -160))
        drag_y = int(max(min(dy, 160), -160))
        start_offset = self._get_drag_start_offset(drag_handle, drag_x, drag_y)
        logger.info(
            "drag window to show target: dx=%s dy=%s start_offset=%s info=%s",
            drag_x,
            drag_y,
            start_offset,
            info,
        )
        ac = ActionChains(self.driver, duration=180)
        ac.move_to_element_with_offset(
            drag_handle,
            int(start_offset["x"]),
            int(start_offset["y"]),
        )
        ac.click_and_hold()
        ac.move_by_offset(drag_x, drag_y)
        ac.release()
        try:
            ac.perform()
        except selenium.common.exceptions.MoveTargetOutOfBoundsException:
            logger.warning(
                "window drag target was out of bounds: dx=%s dy=%s start_offset=%s info=%s",
                drag_x,
                drag_y,
                start_offset,
                info,
                exc_info=True,
            )
            self._restore_frame_path(frame_path)
            return False
        time.sleep(0.25)
        self._restore_frame_path(frame_path)
        return True

    def _get_drag_start_offset(self, el, drag_x, drag_y):
        return self.driver.execute_script(
            """
            const el = arguments[0];
            const dragX = arguments[1];
            const dragY = arguments[2];
            const margin = 8;
            const rect = el.getBoundingClientRect();
            const centerX = (rect.left + rect.right) / 2;
            const centerY = (rect.top + rect.bottom) / 2;

            const startX = Math.min(
                Math.max(centerX, margin - dragX),
                window.innerWidth - margin - dragX
            );
            const startY = Math.min(
                Math.max(centerY, margin - dragY),
                window.innerHeight - margin - dragY
            );

            const visibleLeft = Math.max(rect.left + 2, margin);
            const visibleRight = Math.min(rect.right - 2, window.innerWidth - margin);
            const visibleTop = Math.max(rect.top + 2, margin);
            const visibleBottom = Math.min(rect.bottom - 2, window.innerHeight - margin);

            return {
                x: Math.min(Math.max(startX, visibleLeft), visibleRight) - centerX,
                y: Math.min(Math.max(startY, visibleTop), visibleBottom) - centerY,
                rect: {
                    left: rect.left,
                    top: rect.top,
                    right: rect.right,
                    bottom: rect.bottom,
                },
            };
            """,
            el,
            drag_x,
            drag_y,
        )

    def _get_drag_handle_for_frame_path(self, frame_path):
        if not frame_path:
            return None

        return self.driver.execute_script(
            """
            const path = arguments[0];
            let doc = document;
            let frame = null;
            for (const frameIndex of path) {
                const frames = Array.from(doc.querySelectorAll("iframe,frame"));
                frame = frames[frameIndex];
                if (!frame) {
                    return null;
                }
                doc = frame.contentDocument || frame.contentWindow.document;
            }

            const container =
                frame.closest('div[class*="green"], div[class*="pink"]') ||
                frame.parentElement;
            if (!container) {
                return frame;
            }

            const handles = Array.from(
                container.querySelectorAll(
                    '[class*="header-info"], [class*="_header-info"], [class*="header"]'
                )
            );
            for (const handle of handles) {
                const rect = handle.getBoundingClientRect();
                const style = window.getComputedStyle(handle);
                if (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.display !== "none" &&
                    style.visibility !== "hidden"
                ) {
                    return handle;
                }
            }
            return container;
            """,
            frame_path,
        )

    def _get_top_viewport_click_origin(self, info):
        target = self.driver.execute_script(
            """
            const x = arguments[0];
            const y = arguments[1];
            const el = document.elementFromPoint(x, y);
            if (!el) {
                return null;
            }
            const rect = el.getBoundingClientRect();
            const visibleLeft = Math.max(rect.left, 0);
            const visibleTop = Math.max(rect.top, 0);
            const visibleRight = Math.min(rect.right, window.innerWidth);
            const visibleBottom = Math.min(rect.bottom, window.innerHeight);
            const centerX = (visibleLeft + visibleRight) / 2;
            const centerY = (visibleTop + visibleBottom) / 2;
            const className =
                el.className && el.className.baseVal !== undefined
                    ? el.className.baseVal
                    : String(el.className || "");
            return {
                element: el,
                centerX,
                centerY,
                tagName: el.tagName,
                className,
                left: rect.left,
                top: rect.top,
                right: rect.right,
                bottom: rect.bottom,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
            };
            """,
            info["topTargetX"],
            info["topTargetY"],
        )
        if target is None:
            raise selenium.common.exceptions.MoveTargetOutOfBoundsException(
                f"no visible top-level click origin: {info}"
            )
        target["log"] = {
            "x": info["topTargetX"],
            "y": info["topTargetY"],
            "originTag": target["tagName"],
            "originClass": target["className"],
            "offsetX": info["topTargetX"] - target["centerX"],
            "offsetY": info["topTargetY"] - target["centerY"],
            "originRect": {
                "left": target["left"],
                "top": target["top"],
                "right": target["right"],
                "bottom": target["bottom"],
            },
            "viewport": {
                "width": target["viewportWidth"],
                "height": target["viewportHeight"],
            },
        }
        return target

    def _get_frame_path_to_top(self):
        return self.driver.execute_script(
            """
            const path = [];
            let frameWindow = window;
            while (frameWindow !== frameWindow.top) {
                const frameElement = frameWindow.frameElement;
                if (!frameElement) {
                    break;
                }
                const frames = Array.from(
                    frameWindow.parent.document.querySelectorAll("iframe,frame")
                );
                path.unshift(frames.indexOf(frameElement));
                frameWindow = frameWindow.parent;
            }
            return path;
            """
        )

    def _restore_frame_path(self, frame_path):
        self.driver.switch_to.default_content()
        for frame_index in frame_path:
            self.driver.switch_to.frame(frame_index)

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
            const visibleLeft = Math.max(rect.left, 0);
            const visibleTop = Math.max(rect.top, 0);
            const visibleRight = Math.min(rect.right, window.innerWidth);
            const visibleBottom = Math.min(rect.bottom, window.innerHeight);
            const inViewCenterX = (visibleLeft + visibleRight) / 2;
            const inViewCenterY = (visibleTop + visibleBottom) / 2;
            let topTargetX = targetX;
            let topTargetY = targetY;
            let frameWindow = window;
            let topFrameElement = null;
            while (frameWindow !== frameWindow.top) {
                const frameElement = frameWindow.frameElement;
                if (!frameElement) {
                    break;
                }
                const frameRect = frameElement.getBoundingClientRect();
                const scaleX = frameWindow.innerWidth
                    ? frameRect.width / frameWindow.innerWidth
                    : 1;
                const scaleY = frameWindow.innerHeight
                    ? frameRect.height / frameWindow.innerHeight
                    : 1;
                topTargetX = frameRect.left + topTargetX * scaleX;
                topTargetY = frameRect.top + topTargetY * scaleY;
                topFrameElement = frameElement;
                frameWindow = frameWindow.parent;
            }
            const topInViewport =
                topTargetX >= 0 &&
                topTargetY >= 0 &&
                topTargetX < window.top.innerWidth &&
                topTargetY < window.top.innerHeight;
            const topHit = topInViewport
                ? window.top.document.elementFromPoint(topTargetX, topTargetY)
                : null;
            const topTargetReceivesClick = topFrameElement
                ? topHit === topFrameElement || topFrameElement.contains(topHit)
                : targetReceivesClick;
            const topHitClassName =
                topHit && topHit.className && topHit.className.baseVal !== undefined
                    ? topHit.className.baseVal
                    : String(topHit ? topHit.className : "");
            return {
                clickable:
                    rect.width > 0 &&
                    rect.height > 0 &&
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    style.pointerEvents !== "none" &&
                    inViewport &&
                    targetReceivesClick &&
                    topInViewport &&
                    topTargetReceivesClick,
                inViewport,
                targetReceivesClick,
                topInViewport,
                topTargetReceivesClick,
                hitTagName: hit ? hit.tagName : null,
                hitClassName,
                topHitTagName: topHit ? topHit.tagName : null,
                topHitClassName,
                targetX,
                targetY,
                topTargetX,
                topTargetY,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                topViewportWidth: window.top.innerWidth,
                topViewportHeight: window.top.innerHeight,
                elementWidth: rect.width,
                elementHeight: rect.height,
                inViewCenterElementX: inViewCenterX - rect.left,
                inViewCenterElementY: inViewCenterY - rect.top,
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
