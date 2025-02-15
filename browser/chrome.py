import logging
import os
import re
import subprocess

from utils import is_windows
from .base import Browser

from selenium import webdriver
from selenium.webdriver.chrome.service import Service


class Chrome(Browser):
    pid = None
    _browser_path = None
    _user_data_dir = None

    def __init__(self, browser_path: str = None, user_data_dir: str = None):
        super().__init__("edge")

        self._browser_path = browser_path
        self._user_data_dir = user_data_dir

    @property
    def user_data_dir(self):
        if self._user_data_dir:
            return self._user_data_dir

        if is_windows():  # Windows
            return os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        else:  # MacOS
            return os.path.expanduser("~/Library/Application Support/Google/Chrome")

    @property
    def browser_path(self):
        if self._browser_path:
            return self._browser_path

        chrome_path_env = os.environ.get("CHROME_PATH")
        if chrome_path_env and os.path.exists(chrome_path_env):
            return chrome_path_env

        chrome_path = None
        if is_windows():  # Windows
            chrome_paths = (
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            )
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_path = path
                    break
            if not chrome_path:
                raise FileNotFoundError(
                    "Chrome executable not found. Please install Chrome or check the installation path."
                )

        else:  # MacOS
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if not os.path.exists(chrome_path):
                raise FileNotFoundError(
                    "Chrome executable not found. Please install Chrome or check the installation path."
                )

        if not chrome_path:
            raise FileNotFoundError(
                "Chrome executable not found. Please install Chrome or check the installation path."
            )

        return chrome_path

    def start(self, profile: str, port: int = 9777, headless: bool = False):
        cmd = [
            self.browser_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={self.user_data_dir}",
            f"--profile-directory={profile}",
            "--disable-extensions",  # 禁用所有扩展
            "--disable-plugins",  # 禁用插件
            "--disable-popup-blocking",  # 禁用弹窗拦截
            "--no-default-browser-check",  # 不检查默认浏览器
            "--lang=en",
            "--start-maximized",
        ]
        if headless:
            cmd.append("--headless")
        logging.warning(cmd)

        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, f"chrome-{profile}-startup.log")

        with open(log_file, "a") as log_file:
            process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)

        logging.info(
            f"Started chrome with PID {process.pid}. Logs are being written to {log_file}"
        )
        self.pid = process.pid

    def is_running(self):
        try:
            if is_windows():
                # Windows 使用 tasklist 命令
                cmd = 'tasklist /FI "IMAGENAME eq chrome.exe" /NH'
                output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                return "chrome.exe" in output.stdout
            else:
                # MacOS 使用 ps 命令
                cmd = ["ps", "-A"]
                output = subprocess.run(cmd, capture_output=True, text=True)
                # 在 Mac 上查找 Google Chrome 进程
                return any("Google Chrome" in line for line in output.stdout.splitlines())
        except Exception as e:
            logging.error(f"Error checking if Chrome is running: {e}")
            return False

    def close(self):
        super().close()

        try:
            if is_windows():
                # Windows 使用 taskkill 命令强制结束所有 Chrome 进程
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chrome.exe"],
                    capture_output=True,
                    check=False,
                )
            else:
                # MacOS 使用 pkill 命令结束所有 Chrome 进程
                subprocess.run(
                    ["pkill", "-9", "Google Chrome"], capture_output=True, check=False
                )
            logging.info("Chrome browser has been closed successfully")

        except Exception as e:
            logging.error(f"Failed to close Chrome browser: {e}")

    @property
    def version(self):
        # Google Chrome 131.0.6778.265
        cmd = [self.browser_path, "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        version = re.search(r"Google Chrome (\d+)", result.stdout)
        if version:
            return version.group(1)
        return None

    def get_driver(self, port: int):
        download_url = "https://googlechromelabs.github.io/chrome-for-testing/#stable"

        driver_path = "/usr/local/bin/chromedriver"
        if not os.path.exists(driver_path):
            raise FileNotFoundError(
                f"chromedriver not found at {driver_path}, please download from {download_url}"
            )

        logging.info("starting chrome webdriver")
        options = webdriver.ChromeOptions()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(options=options, service=service)
        return driver
