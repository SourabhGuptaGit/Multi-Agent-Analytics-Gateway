import os
import json
import time
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
from core.config import settings

# ------------------------------
# DIRECTORY UTILITIES
# ------------------------------

def ensure_dir(path: str):
    """
    Ensures a directory exists. If not, creates it.
    Used for:
    - data/raw
    - data/processed
    - data/metadata
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path


# ------------------------------
# JSON UTILITIES
# ------------------------------

def save_json(data, path: str):
    """
    Saves Python dict/list to JSON file.
    Used for:
    - schema metadata file
    - summary files
    - sample values
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_json(path: str):
    """
    Loads JSON safely.
    """
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------
# TIMER DECORATOR
# ------------------------------

def timed(detailed=False):
    """
    Decorator factory that returns the actual decorator.
    Accepts 'detailed' as an argument to configure the timer behavior.
    """
    def decorator(func):
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            
            elapsed_time = end - start
            if detailed:
                # Build the argument string
                all_args = list(args) + [f"{k}={v}" for k, v in kwargs.items()]
                func_args_str = ", ".join(map(str, all_args))
                logger.info(f"[TIMER] {func.__name__} with args: ({func_args_str}) took {elapsed_time:.2f}s")
            else:
                logger.info(f"[TIMER] {func.__name__} took {elapsed_time:.2f}s")
                
            return result
        return wrapper
    return decorator


# ------------------------------
# SIMPLE LOGGER (COLORED)
# ------------------------------

class Logger:
    """
    Small logger for clean and colored output.
    Only prints to console (not files).
    """

    @staticmethod
    def info(msg):
        print(f"\033[94m[INFO]\033[0m {msg}")

    @staticmethod
    def success(msg):
        print(f"\033[92m[SUCCESS]\033[0m {msg}")

    @staticmethod
    def warn(msg):
        print(f"\033[93m[WARNING]\033[0m {msg}")

    @staticmethod
    def error(msg):
        print(f"\033[91m[ERROR]\033[0m {msg}")


# ------------------------------
# ADVANCED LOGGER (Console + File)
# ------------------------------

def _setup_logger(): # Old logger (missing feature to add success level and center paddings)
    """
    Creates a logger that:
    - Logs to console with colors
    - Logs to file using Python stdlib
    - Adds a custom `.success()` method (maps to INFO level)
    """

    logger = logging.getLogger("retail_ai")
    logger.setLevel(settings.LOG_LEVEL.upper())

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # ----- Console Handler (Colored) -----
    console_handler = logging.StreamHandler()

    class ColorFormatter(logging.Formatter):
        COLORS = {
            "DEBUG": "\033[37m",
            "INFO": "\033[94m",
            "WARNING": "\033[93m",
            "ERROR": "\033[91m",
            "CRITICAL": "\033[95m"
        }
        RESET = "\033[0m"

        def format(self, record):
            color = self.COLORS.get(record.levelname, "")
            message = super().format(record)
            return f"{color}{message}{self.RESET}"

    console_handler.setFormatter(
        ColorFormatter("[%(levelname)s] %(message)s")
    )
    logger.addHandler(console_handler)

    # ----- File Handler (Rotating Log File) -----
    if settings.LOG_TO_FILE:
        file_handler = RotatingFileHandler(
            settings.LOG_FILE_PATH,
            maxBytes=1_000_000,
            backupCount=3
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(file_handler)

    # ----- Add custom SUCCESS logging -----
    def success(msg, *args, **kwargs):
        """
        Logs a success message as INFO but with a SUCCESS prefix.
        """
        logger.info(f"SUCCESS: {msg}", *args, **kwargs)

    logger.success = success

    return logger


def setup_logger():
    
    # --- Define Custom SUCCESS Level (Standard Practice) ---
    SUCCESS_LEVEL_NUM = 25
    logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

    class CustomLogger(logging.Logger):
        """
        Custom Logger class with a dedicated .success() method.
        """
        def success(self, msg, *args, **kwargs):
            if self.isEnabledFor(SUCCESS_LEVEL_NUM):
                self._log(SUCCESS_LEVEL_NUM, msg, args, **kwargs)

    logging.setLoggerClass(CustomLogger)
    
    # Use the CustomLogger class
    logger = logging.getLogger("retail_ai") 
    logger.setLevel(settings.LOG_LEVEL.upper())

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # ----- Console Handler (Colored) -----
    
    class ColorFormatter(logging.Formatter):
        FORMAT = "[%(levelname)s] %(message)s"
        LEVEL_WIDTH = 8
        
        LEVEL_COLORS = {
            "DEBUG":    "\033[36m",  # Cyan
            "INFO":     "\033[94m",  # Light Blue
            "SUCCESS":  "\033[32m",  # Green
            "WARNING":  "\033[93m",  # Yellow
            "ERROR":    "\033[91m",  # Red
            "CRITICAL": "\033[41;1m" # White text on Red background
        }
        RESET = "\033[0m"

        def format(self, record):
            levelname = record.levelname
            color = self.LEVEL_COLORS.get(levelname, "")
            
            centered_levelname = levelname.center(self.LEVEL_WIDTH)
            colored_levelname = f"{color}{centered_levelname}{self.RESET}"
            record.levelname = colored_levelname
            message = super().format(record)
            record.levelname = levelname
            
            return message

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter(ColorFormatter.FORMAT))
    logger.addHandler(console_handler)

    # ----- File Handler (Rotating Log File) -----
    if settings.LOG_TO_FILE:
        file_handler = RotatingFileHandler(
            settings.LOG_FILE_PATH,
            maxBytes=1_000_000,
            backupCount=3,
            encoding='utf-8' # Added encoding for robustness
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)-8s] %(message)s") # -8s for aligned log level
        )
        logger.addHandler(file_handler)

    return logger

# Global logger
logger = setup_logger()


# ------------------------------
# SAFE EXECUTION WRAPPER
# ------------------------------

def safe_execute(func):
    """
    Wraps a function to prevent total failure.
    Useful for agent pipelines where LLM might throw an error.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{func.__name__} failed: {str(e)}")
            return None
    return wrapper


# ------------------------------
# SINGLETON DECORATOR
# ------------------------------

def singleton(cls):
    """
    Turns a class into a singleton.
    Example use: DuckDB client should be initialized only once.
    """
    instances = {}

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
