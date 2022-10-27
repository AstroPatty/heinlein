from pathlib import Path
from . import catalog
from . import mask
from .handler import Handler

def get_file_handlers(data: dict, external: dict, *args, **kwargs):
    if external is not None:
        external_handlers = get_external_handlers(data, external)
    else:
        external_handlers = {dtype: None for dtype in data.keys()}
    handlers_ = {}
    for dtype, dconfig in data.items():
        path = dconfig['path']
        try:
            dc_ = dconfig['config']
        except KeyError:
            dc_ = {}
        if external_handlers[dtype] is not None:
            cl = external_handlers[dtype](Path(path), dc_)
            handlers_.update({dtype: cl})
        elif dtype == "catalog":
            cl = catalog.get_catalog_handler(Path(path), dc_)
            handlers_.update({dtype: cl})
        elif dtype == "mask":
            cl = mask.get_mask_handler(Path(path), dc_)
            handlers_.update({dtype: cl})
    return handlers_

def get_external_handlers(data, external):
    output = {}
    for dtype in data.keys():
        function_key = f"{dtype.capitalize()}Handler"
        output.update({dtype: external.get(function_key, None)})
    return output
