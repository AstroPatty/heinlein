from pathlib import Path
from heinlein.region import BaseRegion
from heinlein.dtypes.catalog import Catalog
from astropy.io import ascii
import sys


def get_handler(survey_mod, dtype):
    """
    Returns a function to get data from a particular region.
    This allows for lazy evaluation, which is useful with large datasets.
    """
    try:
        h_name = f"get_{dtype}"
        handler = getattr(survey_mod, h_name)
        return handler
    except AttributeError:
        return get_defualt_handler(dtype)

def get_defualt_handler(dtype):
    try:
        this = sys.modules[__name__]
        handler = getattr(this, f"get_{dtype}")
        return handler
    except AttributeError:
        raise NotImplementedError(f"Data type {dtype} does not have a default handler")

def get_catalog(path: Path, region: BaseRegion):
    """
    Default handler for a catalog.
    Loads a signle catalog, assuming the region name can be found in the file name.
    """
    if not path.is_file():
        files = [f for f in path.glob(f"*{region.name}*") if not f.name.startswith('.')]
        if len(files) > 1:
            raise NotImplementedError
        file_path = files[0]
    else:
        file_path = path

    if file_path.suffix == ".csv":
        data = ascii.read(file_path)
        return Catalog(data)
    else:
        raise NotImplementedError(f"File loader not implemented for file type {file_path.suffix}")