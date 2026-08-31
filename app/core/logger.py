import logging
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings


def configure_logging() -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger("regression_analyzer")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(settings.path("storage.log_dir") / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    return logger
