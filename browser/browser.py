import logging
from pathlib import Path
import time
import traceback
from typing import Any, Callable, List, Optional

from utils import (
    get_free_port,
    sleep_random_time,
)
from .base import Browser

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement


def run_in_browser(
    browser: Browser,
    profile: str,
    fn: Callable,
    headless: bool = False,
    port: Optional[int] = None,
    kill_browser_before_running: bool = False,
    kill_browser_after_running: bool = False,
):
    if browser.is_running():
        if kill_browser_before_running:
            logging.info("Browser is already running, killing it")
            browser.close()

    port = port or get_free_port()
    logging.info(f"browser port: {port}")

    driver = None
    try:
        browser.start(
            profile,
            port=port,
            headless=headless,
        )
        sleep_random_time(reason="start browser")

        driver = browser.get_driver(port)
        logging.info("chrome webdriver started")

        fn(driver)

    except Exception as e:
        raise e

    finally:
        if kill_browser_after_running:
            browser.close()


def with_scroll(
    driver: webdriver.Chrome,
    url: str,
    target_count: int,
    find_items: Callable[[webdriver.Chrome], List[WebElement]],
    process_item: Callable[[WebElement], Any],
    process_item_interval: Optional[float] = None,
) -> List[Any]:

    results = []

    try:
        driver.get(url)
        sleep_random_time(reason=f"Open {url}")

        max_scroll_attempts = 3  # 最大滚动尝试次数
        scroll_count = 0  # 滚动次数
        previous_height = 0  # 前一次页面高度

        result_keys = []

        while len(results) < target_count and scroll_count < max_scroll_attempts:
            # 获取当前页面高度
            current_height = driver.execute_script("return document.body.scrollHeight")

            items: List[WebElement] = find_items(driver)

            for item in items:
                try:
                    result = process_item(item)
                    if isinstance(result, tuple):
                        result_key, result = result
                        if result_key in result_keys:
                            logging.info(
                                f"Result key {result_key} already exists, skip"
                            )
                            continue
                        result_keys.append(result_key)

                    results.append(result)

                    if len(results) >= target_count:
                        logging.info(f"Found {len(results)} items, break")
                        break

                    if process_item_interval is not None:
                        if process_item_interval > 0:
                            logging.info(
                                f"Sleep {process_item_interval} seconds before next item"
                            )
                            time.sleep(process_item_interval)
                    else:
                        sleep_random_time()

                except Exception as e:
                    logging.warning(f"Process item failed: {str(e)}")
                    logging.warning(traceback.format_exc())
                    continue

            if len(results) >= target_count:
                break

            logging.info(f"Current results: {len(results)}")

            # 滚动到页面底部
            logging.info("Scroll to load more posts")
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight, {behavior: 'smooth'});"
            )

            # 等待新内容加载
            sleep_random_time()

            # 检查是否有新内容加载
            if current_height == previous_height:
                scroll_count += 1
                logging.info(f"Scroll {scroll_count} times but no new content loaded")
            else:
                scroll_count = 0  # 重置计数器，因为发现了新内容
                logging.info("New content loaded, reset scroll count")

            previous_height = current_height

        logging.info(f"Total results: {len(results)}")
        return results

    except Exception as e:
        logging.error(f"with_scroll failed: {str(e)}")
        logging.error(traceback.format_exc())
        return results
