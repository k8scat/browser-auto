import logging
import os
import signal
import subprocess

from utils import is_windows


class Browser:
    pid = None
    
    def __init__(self, browser_type: str):
        self.browser_type = browser_type
        self.driver = None
    
    @property
    def user_data_dir(self):
        raise NotImplementedError
    
    @property
    def browser_path(self):
        raise NotImplementedError

    def start(
        self,
        profile: str,
        port: int = 9222,
        headless: bool = False,
    ):
        raise NotImplementedError

    def get_user_data_dir(self):
        raise NotImplementedError

    def get_browser_path(self):
        raise NotImplementedError

    def is_running(self):
        raise NotImplementedError

    def close(self):
        if self.pid:
            try:
                logging.warning(f"killing chrome with pid: {self.pid}")
                if is_windows():
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(self.pid)], check=True
                    )
                else:
                    os.kill(self.pid, signal.SIGKILL)

            except Exception as e:
                logging.error(f"kill chrome with pid: {self.pid} failed: {e}")

    def get_version(self):
        raise NotImplementedError

    def get_driver(self):
        raise NotImplementedError
