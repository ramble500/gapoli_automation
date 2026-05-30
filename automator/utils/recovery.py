import logging
import threading
import time

from selenium.webdriver.common.by import By


logger = logging.getLogger(__name__)


class CommunicationErrorRecovered(Exception):
    """Raised after a visible communication-error dialog has been retried."""


_RETRY_XPATHS = (
    '//button[contains(normalize-space(.), "リトライ")]',
    '//*[@role="button" and contains(normalize-space(.), "リトライ")]',
    '//button[contains(normalize-space(.), "再試行")]',
    '//*[@role="button" and contains(normalize-space(.), "再試行")]',
    '//div[contains(@class, "applyButton") and contains(normalize-space(.), "リトライ")]',
)


def _is_visible(element):
    try:
        return element.is_displayed() and element.is_enabled()
    except Exception:
        return False


def _has_visible_retry_in_top(controller):
    try:
        return bool(
            controller.driver.execute_script(
                """
                try {
                  const doc = window.top.document;
                  return Array.from(
                    doc.querySelectorAll(
                      'button,[role="button"],div[class*="applyButton"]'
                    )
                  )
                    .some((element) => {
                      const text = (element.textContent || '').trim();
                      const style = window.top.getComputedStyle(element);
                      const rect = element.getBoundingClientRect();
                      return (
                        (text.includes('リトライ') || text.includes('再試行')) &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        rect.width > 0 &&
                        rect.height > 0
                      );
                    });
                } catch (error) {
                  return false;
                }
                """
            )
        )
    except Exception:
        return False


def _get_lock(controller):
    lock = getattr(controller, "_communication_retry_lock", None)
    if lock is None:
        lock = threading.Lock()
        controller._communication_retry_lock = lock
    return lock


def _get_thread_state(controller):
    state = getattr(controller, "_communication_retry_thread_state", None)
    if state is None:
        state = threading.local()
        controller._communication_retry_thread_state = state
    return state


def _find_visible_retry(controller):
    controller.driver.switch_to.default_content()
    for xpath in _RETRY_XPATHS:
        for element in controller.driver.find_elements(By.XPATH, xpath):
            if _is_visible(element):
                return element
    return None


def recover_communication_error(controller, timeout=20):
    """Click a visible retry dialog with the regular mouse path."""
    if not _has_visible_retry_in_top(controller):
        return False

    with _get_lock(controller):
        if not _has_visible_retry_in_top(controller):
            return False

        retry_button = _find_visible_retry(controller)
        if retry_button is None:
            return False

        logger.warning("通信エラーダイアログを検知。『リトライ』をクリック")
        controller._recovering_communication_error = True
        try:
            controller.click_element(retry_button)
        finally:
            controller._recovering_communication_error = False

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _has_visible_retry_in_top(controller):
                controller.communication_retry_count += 1
                logger.warning("通信エラーダイアログ消失を確認")
                controller.wait_random(0.5)
                return True
            time.sleep(0.2)

    raise TimeoutError("通信エラーダイアログがリトライ後も消えません")


def raise_if_communication_error(controller):
    """Recover once, then force the caller to restart its screen flow."""
    state = _get_thread_state(controller)
    current_count = controller.communication_retry_count
    if not hasattr(state, "seen_retry_count"):
        state.seen_retry_count = current_count
    seen_count = state.seen_retry_count

    if seen_count != current_count:
        state.seen_retry_count = current_count
        raise CommunicationErrorRecovered("別ワーカーが通信エラーから復帰しました")

    if recover_communication_error(controller):
        state.seen_retry_count = controller.communication_retry_count
        raise CommunicationErrorRecovered("通信エラーから復帰しました")
