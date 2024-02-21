from types import ModuleType

from godata.project import GodataProject

from . import catalog, mask


def get_file_handlers(
    dtypes: list, pconfig: GodataProject, external: dict, *args, **kwargs
):
    if external is not None:
        external_handlers = get_external_handlers(pconfig, external)
    else:
        external_handlers = {dtype: None for dtype in dtypes}
    handlers_ = {}
    config = pconfig.get("meta/config")
    all_dconfig = config.get("dconfig", {})
    for dtype in dtypes:
        dconfig = all_dconfig.get(dtype, {})
        if external_handlers[dtype] is not None:
            cl = external_handlers[dtype](pconfig, dconfig)
            handlers_.update({dtype: cl})
        elif dtype == "catalog":
            cl = catalog.get_catalog_handler(pconfig, dconfig)
            handlers_.update({dtype: cl})
        elif dtype == "mask":
            cl = mask.get_mask_handler(pconfig, dconfig)
            handlers_.update({dtype: cl})
    return handlers_


def get_external_handlers(data: GodataProject, external: ModuleType):
    output = {}
    known_dtypes_ = data.list("data")
    known_dtypes = []
    for dtype in known_dtypes_:
        known_dtypes.extend(known_dtypes_[dtype])

    for dtype in known_dtypes:
        function_key = f"{dtype.capitalize()}Handler"
        output.update({dtype: external.get(function_key, None)})
    return output
