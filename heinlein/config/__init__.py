from typing import Any

from .config import HeinleinConfig

_HEINLEIN_CONFIG = HeinleinConfig()


def get_option(option: str) -> Any:
    return getattr(_HEINLEIN_CONFIG, option)


def set_option(option: str, value: Any) -> bool:
    setattr(_HEINLEIN_CONFIG, option, value)
    return True
