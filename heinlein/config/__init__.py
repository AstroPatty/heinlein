import os
import warnings
from typing import Any

from pydantic import ValidationError

from heinlein.errors import HeinleinConfigError

from .config import HeinleinConfig

try:
    _HEINLEIN_CONFIG = HeinleinConfig()
except ValidationError as e:
    bad_values = {e["loc"][0]: e["msg"] for e in e.errors()}
    msg = (
        "heinlein recieved invalid configuration values from the "
        "environment and will use defaults instead. Invalid values:\n"
    )
    msg += "\n".join(f"{k}: {v}" for k, v in bad_values.items())
    warnings.warn(msg)
    for k in bad_values.keys():
        os.environ.pop(f"HEINLEIN_{k}", None)
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
