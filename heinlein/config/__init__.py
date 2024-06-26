from typing import Any

from .config import HeinleinConfig

HEINLEIN_CONFIG = HeinleinConfig()


def get_config(option: str) -> Any:
    return getattr(HEINLEIN_CONFIG, option)


def set_config(option: str, value: Any) -> bool:
    setattr(HEINLEIN_CONFIG, option, value)
    return True
