import logging
import os
import re
import subprocess

from utils import is_windows
from .base import Browser

from selenium import webdriver
from selenium.webdriver.chrome.service import Service


class Edge(Browser):
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
            return os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
        else:
            return os.path.expanduser("~/Library/Application Support/Microsoft Edge")

    @property
    def browser_path(self):
        if self._browser_path:
            return self._browser_path

        return os.path.expandvars(
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        )

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
        logging.warning(" ".join(cmd))

        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, f"edge-{profile}-startup.log")

        with open(log_file, "a") as log_file:
            process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)

        logging.info(
            f"Started Browser with PID {process.pid}. Logs are being written to {log_file}"
        )
        self.pid = process.pid

    def is_running(self):
        try:
            if is_windows():
                cmd = 'tasklist /FI "IMAGENAME eq edge.exe" /NH'
                output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                return "edge.exe" in output.stdout
            else:
                # MacOS 使用 ps 命令
                cmd = ["ps", "-A"]
                output = subprocess.run(cmd, capture_output=True, text=True)
                # 在 Mac 上查找 Google Chrome 进程
                return any(
                    "Microsoft Edge" in line for line in output.stdout.splitlines()
                )

        except Exception as e:
            logging.error(f"Error checking if Chrome is running: {e}")
            return False

    def close(self):
        super().close()

        try:
            if is_windows():
                subprocess.run(
                    ["taskkill", "/F", "/IM", "edge.exe"],
                    capture_output=True,
                    check=False,
                )
            else:
                subprocess.run(
                    ["pkill", "-9", "Microsoft Edge"], capture_output=True, check=False
                )
        except Exception as e:
            logging.error(f"kill edge failed: {e}")

    @property
    def version(self):
        # Microsoft Edge 132.0.2957.127
        cmd = [self.browser_path, "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        version = re.search(r"Microsoft Edge (\d+)", result.stdout)
        if version:
            return version.group(1)
        return None

    def get_driver(self, port: int):
        download_url = "https://developer.microsoft.com/zh-cn/microsoft-edge/tools/webdriver/?form=MA13LH"

        driver_path = "/usr/local/bin/msedgedriver"
        if not os.path.exists(driver_path):
            raise FileNotFoundError(
                f"msedgedriver not found at {driver_path}, please download from {download_url}"
            )

        logging.info("starting msedge webdriver")
        options = webdriver.EdgeOptions()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        service = Service(executable_path=driver_path)
        driver = webdriver.Edge(options=options, service=service)
        return driver
