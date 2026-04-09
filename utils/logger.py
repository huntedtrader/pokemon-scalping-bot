"""Colored console + file logging for the scalping bot."""

import logging
import sys
from datetime import datetime
from pathlib import Path

COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[41m",  # Red background
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
}

RETAILER_COLORS = {
    "pokemon_center": "\033[93m",  # Bright yellow
    "target": "\033[91m",          # Red
    "walmart": "\033[94m",         # Blue
    "amazon": "\033[33m",          # Orange-ish
    "bestbuy": "\033[96m",         # Cyan
    "tcgplayer": "\033[95m",       # Magenta
    "ebay": "\033[92m",            # Green
    "monitor": "\033[97m",         # White
    "checkout": "\033[93m",        # Yellow
    "system": "\033[90m",          # Gray
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        level = record.levelname
        color = COLORS.get(level, "")
        reset = COLORS["RESET"]
        dim = COLORS["DIM"]

        retailer = getattr(record, "retailer", None)
        retailer_tag = ""
        if retailer:
            rc = RETAILER_COLORS.get(retailer, "")
            retailer_tag = f" {rc}[{retailer.upper()}]{reset}"

        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        msg = record.getMessage()

        formatted = (
            f"{dim}{timestamp}{reset} "
            f"{color}{level:<8}{reset}"
            f"{retailer_tag} "
            f"{msg}"
        )

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted += f"\n{COLORS['ERROR']}{record.exc_text}{reset}"

        return formatted


class FileFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Configure root logger with colored console and file output."""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    root = logging.getLogger("pokescalp")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColorFormatter())
    root.addHandler(console)

    # File handler (daily rotation)
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(log_path / f"bot_{today}.log", encoding="utf-8")
    file_handler.setFormatter(FileFormatter())
    root.addHandler(file_handler)

    return root


def get_logger(name: str, retailer: str = None) -> logging.LoggerAdapter:
    """Get a logger with optional retailer context."""
    logger = logging.getLogger(f"pokescalp.{name}")
    extra = {"retailer": retailer} if retailer else {"retailer": None}
    return logging.LoggerAdapter(logger, extra)
