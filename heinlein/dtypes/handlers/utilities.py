from pathlib import Path

from heinlein.manager.dconfig import DatasetConfig

from . import catalog, mask


def get_file_handlers(data: DatasetConfig, external: dict, *args, **kwargs):
    if external is not None:
        external_handlers = get_external_handlers(data, external)
    else:
        external_handlers = {dtype: None for dtype in data.keys()}
    handlers_ = {}
    dtypes = data.get_data_types()
    config = data.get_data("config")
    all_dconfig = config.get("dconfig", {})
    for dtype in dtypes:
        path = data.get_data(dtype)
        dconfig = all_dconfig.get(dtype, {})

        if external_handlers[dtype] is not None:
            cl = external_handlers[dtype](Path(path), dconfig)
            handlers_.update({dtype: cl})
        elif dtype == "catalog":
            cl = catalog.get_catalog_handler(Path(path), dconfig)
            handlers_.update({dtype: cl})
        elif dtype == "mask":
            cl = mask.get_mask_handler(Path(path), dconfig)
            handlers_.update({dtype: cl})

    return handlers_


def get_external_handlers(data: DatasetConfig, external):
    output = {}
    for dtype in data.get_data_types:
        function_key = f"{dtype.capitalize()}Handler"
        output.update({dtype: external.get(function_key, None)})
    return output
