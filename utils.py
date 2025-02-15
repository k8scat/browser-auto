import logging
from pathlib import Path
import platform
import random
import os
import socket
import time
from typing import Optional



def is_windows() -> bool:
    return _get_system_platform() == "windows"


def get_system_platform() -> str:
    p = _get_system_platform()
    if p == "windows":
        return "windows"

    return "mac-arm" if platform.processor() == "arm" else "mac-x64"


def _get_system_platform() -> str:
    """Get the current operating system platform with enhanced accuracy

    Returns:
        str: 'windows' for Windows, 'mac' for macOS
    """
    try:
        # Primary check using platform.system()
        system = platform.system().lower()

        # Secondary check using os.name
        os_name = os.name.lower()

        # Additional info from platform
        platform_info = platform.platform().lower()

        # Windows detection
        if system == "windows" or os_name == "nt" or "windows" in platform_info:
            # Additional Windows-specific check
            if os.path.exists("C:\\Windows"):
                return "windows"

        # macOS detection
        if system == "darwin" or "macos" in platform_info:
            # Additional macOS-specific check
            if os.path.exists("/Applications") and os.path.exists("/System"):
                return "mac"

        # Fallback to basic system check if specific detection fails
        if system == "darwin":
            return "mac"
        elif system == "windows":
            return "windows"

        # If all checks fail, return the basic system name
        return "windows" if os_name == "nt" else "mac"

    except Exception as e:
        logging.error(f"Error detecting system platform: {e}")
        # Last resort fallback based on os.name
        return "windows" if os.name == "nt" else "mac"


def sleep_random_time(
    min_seconds: int = 5, max_seconds: int = 10, reason: Optional[str] = None
):
    sleep_time = random.uniform(min_seconds, max_seconds)
    logging.info(f"Waiting for {sleep_time} seconds: {reason}")
    time.sleep(sleep_time)


def setup_logging(log_file="app.log", log_level=logging.INFO, formatter=None):
    # Create a formatter
    if formatter is None:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    log_path = Path("logs") / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Setup file handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def get_free_port(start_port: int = 1024, end_port: int = 65535) -> int:
    """Get a random free port in the given range

    Args:
        start_port: Start of port range (default: 1024)
        end_port: End of port range (default: 65535)

    Returns:
        int: A free port number

    Raises:
        RuntimeError: If no free port is found in the range
    """
    s = set()
    while True:
        port = random.randint(start_port, end_port)
        if port not in s:
            if not check_port_in_use(port):
                return port
            s.add(port)

def check_port_in_use(port: int) -> bool:
    """Check if a port is in use on both Windows and Mac/Linux systems

    Args:
        port: Port number to check

    Returns:
        bool: True if port is in use, False otherwise
    """
    # First try socket connection test which works on all platforms
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
            return False
    except socket.error:
        return True
