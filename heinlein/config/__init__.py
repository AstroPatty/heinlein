from typing import Any

from heinlein.errors import HeinleinConfigError

from .config import HeinleinConfig

_HEINLEIN_CONFIG = HeinleinConfig()


def get_option(option: str) -> Any:
    canonical_name = option.upper()
    try:
        return getattr(_HEINLEIN_CONFIG, canonical_name)
    except AttributeError:
        raise HeinleinConfigError.doesnt_exist(option)


def set_option(option: str, value: Any) -> bool:
    canonical_name = option.upper()
    if not hasattr(_HEINLEIN_CONFIG, canonical_name):
        raise HeinleinConfigError.doesnt_exist(option)
    setattr(_HEINLEIN_CONFIG, canonical_name, value)
    return True
