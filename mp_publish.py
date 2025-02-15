from datetime import datetime
import logging
import os
from pathlib import Path
import random
import re
import traceback
from typing import Callable, List, Optional
import time
import uuid

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from pydantic import BaseModel
from dotenv import load_dotenv

from article_collector_common import Article as ArticleCollected
from utils import (
    setup_logging,
    sleep_random_time,
)
from browser.edge import Edge
from browser.browser import run_in_browser


class Article(BaseModel):
    """文章数据模型"""

    title: str
    content: str
    cover_image: Optional[str] = None
    description: Optional[str] = None  # 摘要
    author: Optional[str] = None
    original_article: Optional[bool] = True
    categories: Optional[List[str]] = None
    original_url: Optional[str] = None

    def model_post_init(self, __context) -> None:
        super().model_post_init(__context)
        if self.cover_image:
            if not Path(self.cover_image).is_file():
                raise ValueError(f"Cover image not found: {self.cover_image}")

    class Config:
        arbitrary_types_allowed = True


DEFAULT_ARTICLE_SUFFIX_TEMPLATE = """<center><strong style="color: black;">点击关注并扫码添加进交流群</strong></center>
<center><strong style="color: black;">免费领取「{title}」学习资料</strong></center>

<div style="text-align:center;">
  <img src="{cover_image}" style="width:70%;" />
</div>"""

DEFAULT_ARTICLE_SUFFIX_TEMPLATE_2 = """<center><strong style="color: black;">点击关注并扫码添加进交流群</strong></center>
<center><strong style="color: black;">免费领取学习资料</strong></center>

<div style="text-align:center;">
  <img src="{cover_image}" style="width:70%;" />
</div>"""


class PublishConfig(BaseModel):
    profile: str  # Chrome profile name
    mp_account: str
    articles: List[Article]
    articles_collected: List[ArticleCollected]
    cover_images: Optional[List[str]] = None
    article_suffix: Optional[str] = None
    article_prefix: Optional[str] = None
    main_category: str

    def model_post_init(self, __context) -> None:
        """Validate that all cover_images exist"""
        super().model_post_init(__context)
        if self.cover_images:
            for i in range(len(self.cover_images)):
                image_path = self.cover_images[i]
                if image_path.startswith("http://") or image_path.startswith("https://"):
                    # download image
                    with requests.get(image_path, allow_redirects=True) as r:
                        r.raise_for_status()
                        image_data = r.content
                    image_path = f"/tmp/mp_publish_{uuid.uuid4()}.jpg"
                    with open(image_path, "wb") as f:
                        f.write(image_data)
                    self.cover_images[i] = image_path
                    logging.info(f"Download cover image: {image_path}")
                elif not Path(image_path).is_file():
                    raise ValueError(f"Cover image not found: {image_path}")


class PublishResult(BaseModel):
    """发布结果"""

    success: bool
    message: str
    article_url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class MPPublisher:
    """微信公众号文章发布器"""

    def __init__(self, driver: webdriver.Chrome, profile: PublishConfig):
        self.profile = profile
        self._profile = self.profile.profile.replace(" ", "_")
        self.driver = driver

        self.data_dir = Path(f"data/mp_publish/{self.profile.mp_account}")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def format_content(self, content: str, window_handle: Optional[str] = None):
        if window_handle:
            logging.info(f"Switch to window: {window_handle}")
            self.driver.switch_to.window(window_handle)

        logging.info("format content using mdnice")
        url = "https://editor.mdnice.com/?outId=b64e0a073b6144e1b490df79738128e6"
        self.driver.get(url)
        sleep_random_time(reason=f"Open {url}")

        import_btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "nice-menu-file"))
        )
        import_btn.click()

        tmp_file = "/tmp/mp_publish_tmp.md"
        try:
            content = content.strip()
            if content.startswith("# "):
                # remove the first line
                content = "\n".join(content.split("\n")[1:]).strip()
            if content.startswith("## "):
                # remove the first line
                content = "\n".join(content.split("\n")[1:]).strip()

            if self.profile.article_suffix:
                content = f"{content}\n\n{self.profile.article_suffix}"
            if self.profile.article_prefix:
                content = f"{self.profile.article_prefix}\n\n{content}"

            # write content to tmp file
            with open(tmp_file, "w") as f:
                f.write(content)

            import_md_btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "importMarkdown"))
            )
            import_md_btn.send_keys(tmp_file)

            sleep_random_time(reason="Wait for content to be set")

            logging.info("Click copy button")
            copy_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "nice-sidebar-wechat"))
            )
            copy_btn.click()

        finally:
            try:
                os.remove(tmp_file)
            except Exception as e:
                logging.warning(f"Remove tmp file failed: {e}")

    def is_mp_login(self):
        try:
            account_name = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[class="acount_box-nickname"]')
                )
            )
            logging.info(f"Mp {account_name.text} already logged in")
            return True
        except Exception as _:
            return False

    def verify_mp_login(self, try_login: bool = False):
        self.verify_login(
            "mp",
            "https://mp.weixin.qq.com",
            self.is_mp_login,
            try_login,
        )

    def is_mdnice_login(self):
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        '[class="ant-avatar ant-avatar-sm ant-avatar-circle"]',
                    )
                )
            )
            
            # todo fix
            logging.info("Mdnice already logged in")
            return True
        except Exception as _:
            return False

    def verify_mdnice_login(self, try_login: bool = False):
        self.verify_login(
            "mdnice",
            "https://editor.mdnice.com/?outId=b64e0a073b6144e1b490df79738128e6",
            self.is_mdnice_login,
            try_login,
        )

    def verify_login(
        self,
        name: str,
        url: str,
        find_element_fn: Callable[[], bool],
        try_login: bool = False,
    ):
        self.driver.get(url)

        if find_element_fn():
            return

        feishu_alert(f"{name} not logged in")

        if try_login:
            screenshot_file = f"/tmp/{name}_not_login_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
            try:
                screenshot_as_file(self.driver, screenshot_file)
                feishu_send_image(screenshot_file)

            except Exception as e:
                logging.error(f"Send screenshot failed: {e}")

            finally:
                try:
                    os.remove(screenshot_file)
                except Exception as e:
                    logging.error(f"Remove screenshot file failed: {e}")

            start_time = time.time()
            while time.time() - start_time < 600:
                if find_element_fn():
                    return
                sleep_random_time(reason=f"Wait for {name} login")

        raise Exception(f"{name} not logged in")

    def add_new_post(self):
        new_post_area = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[class="preview_media_add_word"]')
            )
        )
        actions = ActionChains(self.driver)
        actions.move_to_element(new_post_area).perform()
        sleep_random_time(
            min_seconds=1,
            max_seconds=2,
            reason="Wait for new post area to be hovered",
        )

        btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[title="写新图文"]'))
        )
        btn.click()

    def publish_article(self, articles: List[Article]):
        """发布文章"""
        self.driver.get("https://mp.weixin.qq.com/")
        sleep_random_time(reason="Open mp.weixin.qq.com")

        # 点击写文章按钮
        new_post_btns = WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, '[class="new-creation__menu-content"]')
            )
        )
        new_post_btn = new_post_btns[0]
        original_window = self.driver.current_window_handle

        new_post_btn.click()
        sleep_random_time(reason="Click new post button")

        new_post_window = self.driver.window_handles[-1]
        self.driver.switch_to.window(new_post_window)

        for index, article in enumerate(articles):
            if index > 0:
                try:
                    self.add_new_post()
                    sleep_random_time(reason="Click add new post")
                except Exception as e:
                    logging.error(f"Click add new post failed: {e}")
                    raise e

            self.format_content(article.content, window_handle=original_window)

            self.driver.switch_to.window(new_post_window)

            self.set_title(article.title)
            self.set_author(article.author)

            try:
                self.set_content()
            except Exception as e:
                logging.error(f"Set content failed: {e}")
                try:
                    logging.info("Try to set content v2")
                    self.set_content_v2()
                except Exception as e:
                    logging.error(f"Set content v2 failed: {e}")
                    raise e

            # scroll to bottom
            logging.info("scroll to bottom")
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight, {behavior: 'smooth'});"
            )
            sleep_random_time(
                min_seconds=1,
                max_seconds=2,
                reason="Wait for content to be scrolled to bottom",
            )

            self.set_cover_image(article.cover_image)
            self.set_description(article.description)
            self.set_categories(article.categories)
            self.set_original(article.original_article)
            self.click_save_draft()

    def click_save_draft(self):
        save_draft_btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//span[text()="保存为草稿"]'))
        )
        save_draft_btn.click()
        sleep_random_time(reason="Wait for save draft")

    def set_original(self, original: bool):
        if not original:
            logging.info("Not original article, skip set original")
            return

        try:
            original_checkbox = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[text()="未声明"]'))
            )
            original_checkbox.click()
            sleep_random_time(
                min_seconds=1,
                max_seconds=2,
                reason="Wait for original checkbox to be clicked",
            )

            confirm_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[text()="确定"]'))
            )
            confirm_btn.click()
            sleep_random_time(reason="Wait for confirm original checkbox")

            # 如果没有同意协议，原创的界面不会消失，需要先点击同意，然后点击确定
            try:
                check_el = self.driver.find_element(
                    By.CSS_SELECTOR,
                    '[class="original_agreement"] label [class="weui-desktop-icon-checkbox"]',
                )
                check_el.click()
                sleep_random_time(
                    min_seconds=1,
                    max_seconds=2,
                    reason="Wait for check original checkbox",
                )

                confirm_btn.click()
                sleep_random_time(reason="Wait for confirm original checkbox again")

            except Exception as _:
                pass

        except Exception as e:
            logging.error(f"Click original checkbox failed: {e}")

    def set_content(self):
        logging.info("Set content")
        logging.info("find content body")
        content_body = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "ueditor_0"))
        )
        logging.info("click content body")
        content_body.click()
        logging.info("paste content")
        content_body.send_keys(Keys.COMMAND + "v")
        sleep_random_time(
            min_seconds=1, max_seconds=2, reason="Wait for content to be pasted"
        )

    def set_content_v2(self):
        logging.info("Set content v2")
        logging.info("find content body")
        content_body = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[class="ProseMirror"]'))
        )
        logging.info("click content body")
        content_body.click()
        sleep_random_time(
            min_seconds=1,
            max_seconds=2,
            reason="Wait for content body to be clicked",
        )
        logging.info("paste content")
        content_body.send_keys(Keys.COMMAND + "v")
        sleep_random_time(
            min_seconds=1, max_seconds=2, reason="Wait for content to be pasted"
        )

    def set_author(self, author: Optional[str] = None):
        if not author:
            author = self.profile.mp_account

        logging.info(f"Set author: {author}")
        author_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "author"))
        )
        author_input.send_keys(author)

    def set_title(self, title: str):
        # 移除表情符号和其他特殊字符
        title = re.sub(
            r"[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\u2B50\u2B55]", "", title
        )
        # 移除其他不可见字符和控制字符
        title = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", title)
        # 移除零宽字符
        title = re.sub(r"[\u200B-\u200D\uFEFF]", "", title)
        title = title.strip()

        logging.info(f"Set title: {title}")
        title_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'textarea[id="title"]'))
        )
        title_input.send_keys(title)

    def set_cover_image(self, cover_image: Optional[str] = None):
        try:
            cover_choose_area = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//span[text()='拖拽或选择封面']")
                )
            )
            actions = ActionChains(self.driver)
            actions.move_to_element(cover_choose_area).perform()
            sleep_random_time(
                min_seconds=1,
                max_seconds=2,
                reason="Wait for cover choose area to be hovered",
            )

            cover_choose_btns = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, '//div[@id="js_cover_area"]//a[text()="从图片库选择"]')
                )
            )
            if len(cover_choose_btns) == 0:
                raise Exception("Cover choose button not found")
            if len(cover_choose_btns) == 1:
                cover_choose_btns[0].click()
            else:
                for btn in cover_choose_btns:
                    try:
                        logging.info("Try to click cover choose button")
                        btn.click()
                        break
                    except Exception as _:
                        logging.error("Click cover choose button failed")
                        continue

            if (
                not cover_image
                and self.profile.cover_images
                and len(self.profile.cover_images) > 0
            ):
                cover_image_index = random.randint(0, len(self.profile.cover_images) - 1)
                cover_image = self.profile.cover_images[cover_image_index]
                self.profile.cover_images.pop(cover_image_index)

            if cover_image:
                logging.info(f"Set cover image: {cover_image}")
                cover_upload = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '[class~="js_upload_btn_container"] input')
                    )
                )
                cover_upload.send_keys(cover_image)
                sleep_random_time(reason="Wait for cover image to be uploaded")
            else:
                cover_images = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, '[class="weui-desktop-img-picker__item"]')
                    )
                )
                if len(cover_images) > 0:
                    cover_images[0].click()
                    sleep_random_time(
                        min_seconds=1,
                        max_seconds=2,
                        reason="Wait for cover image to be selected",
                    )

            next_step_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[text()="下一步"]'))
            )
            next_step_btn.click()
            sleep_random_time(reason="Wait for next step")

            confirm_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[text()="确认"]'))
            )
            confirm_btn.click()
            sleep_random_time(reason="Wait for confirm cover image")

        except Exception as e:
            logging.error(f"Set cover image failed: {e}")

    def set_categories(self, categories: Optional[List[str]] = None):
        if not categories or len(categories) == 0:
            logging.info("No categories to set")
            return

        try:
            categories = categories[:5]
            logging.info(f"Set categories: {categories}")
            add_category_btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '[class~="js_article_tags_label"]')
                )
            )
            add_category_btn.click()
            sleep_random_time(
                min_seconds=1,
                max_seconds=2,
                reason="Wait for add category button to be clicked",
            )

            input_area = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        'label[class="weui-desktop-form-tag__input__label"]',
                    )
                )
            )
            input_area.click()

            category_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//input[@placeholder="输入后按回车分割"]')
                )
            )

            for category in categories:
                category_input.send_keys(category)
                category_input.send_keys(Keys.ENTER)
                sleep_random_time(
                    min_seconds=1, max_seconds=2, reason="Wait for category to be set"
                )

            confirm_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[text()="确定"]'))
            )
            confirm_btn.click()
            sleep_random_time(reason="Wait for confirm categories")

        except Exception as e:
            logging.error(f"Set categories failed: {e}")

    def set_description(self, description: Optional[str] = None):
        if not description:
            logging.info("No description to set")
            return

        try:
            description = description[:120]
            logging.info(f"Set description: {description}")
            description_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "js_description"))
            )
            description_input.send_keys(description)
        except Exception as e:
            logging.error(f"Set description failed: {e}")


def process_publish(profile: PublishConfig):
    """处理发布任务"""
    formatter = logging.Formatter(
        f"%(asctime)s - {profile.profile} - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    setup_logging(
        log_file=f"mp_publisher_{profile.profile.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
        log_level=logging.INFO,
        formatter=formatter,
    )

    logging.info(f"Profile config: {profile}")

    def fn(driver):
        logging.info("Starting MP publisher")
        publisher = MPPublisher(driver, profile)
        publisher.verify_mp_login(try_login=True)
        publisher.verify_mdnice_login(try_login=True)

        publisher.publish_article(profile.articles)
        feishu_alert(f"{profile.mp_account} 新增文章")

    load_dotenv()
    headless = os.getenv("CHROME_HEADLESS", "false").lower() == "true"

    browser = Edge()
    run_in_browser(
        browser,
        profile.profile,
        fn,
        headless=headless,
        kill_browser_before_running=True,
        kill_browser_after_running=False,
    )


if __name__ == "__main__":
    try:
        config = PublishConfig(
            mp_account="Rust编程笔记",
            profile="Profile 3",
            articles=[
                Article(
                    title="test",
                    content="# test\n\n## hi\n\nhello world",
                    description="test",
                    original_article=True,
                    categories=["测试", "测试2", "测试3", "测试4", "测试5", "测试6"],
                ),
                Article(
                    title="test",
                    content="# test\n\n## hi\n\nhello world222",
                    description="test",
                    original_article=True,
                    categories=["测试", "测试2", "测试3", "测试4", "测试5", "测试6"],
                ),
                Article(
                    title="test",
                    content="# test\n\n## hi\n\nhello world333",
                    description="test",
                    original_article=True,
                    categories=["测试", "测试2", "测试3", "测试4", "测试5", "测试6"],
                ),
            ],
        )
        process_publish(config)

    except Exception as e:
        print(f"Main error: {e}")
        print(traceback.format_exc())
