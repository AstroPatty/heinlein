from pathlib import Path
from types import ModuleType

from . import catalog, mask


def get_file_handlers(dtypes: list, config: dict, external: dict, *args, **kwargs):
    if external is not None:
        external_handlers = get_external_handlers(config, external)
    else:
        external_handlers = {dtype: None for dtype in dtypes}
    handlers_ = {}
    all_dconfig = config.get("dconfig", {})
    data = config.get("data", {})
    for dtype in dtypes:
        dconfig = all_dconfig.get(dtype, {})
        if external_handlers[dtype] is not None:
            cl = external_handlers[dtype](Path(data[dtype]), dconfig)
            handlers_.update({dtype: cl})
        elif dtype == "catalog":
            cl = catalog.get_catalog_handler(config, dconfig)
            handlers_.update({dtype: cl})
        elif dtype == "mask":
            cl = mask.get_mask_handler(config, dconfig)
            handlers_.update({dtype: cl})
    return handlers_


def get_external_handlers(config: dict, external: ModuleType):
    output = {}
    known_dtypes = list(config.get("data", {}).keys())

    for dtype in known_dtypes:
        function_key = f"{dtype.capitalize()}Handler"
        output.update({dtype: external.get(function_key, None)})
    return output
