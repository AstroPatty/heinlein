from pathlib import Path
from typing import Any
from heinlein.region import BaseRegion
from heinlein.dtypes.catalog import Catalog
from astropy.io import ascii
import sys
from abc import ABC, abstractmethod
import logging


def get_file_handlers():
    handlers = {'catalog': file_catalog_handler, 'mask': file_mask_handler }
    return handlers

def file_catalog_handler(path: Path, region: BaseRegion, *args, **kwargs):
        """
        Default handler for a catalog.
        Loads a single catalog, assuming the region name can be found in the file name.
        """
        parent_region = kwargs.get("parent_region", False)
        if not path.exists():
            print(f"Path {path} does not exist! Perhaps it is in an external storage device that isn't attached.")
            return None

        if not path.is_file():
            files = [f for f in path.glob(f"*{region.name}*") if not f.name.startswith('.')]
            if len(files) > 1:
                raise NotImplementedError
            if len(files) == 0:
                new_path = path / str(parent_region.name)
                files = [f for f in new_path.glob(f"*{region.name}*") if not f.name.startswith('.')]
            try:
                file_path = files[0]
            except IndexError:
                logging.error(f"No file found for dtype catalog in region {region.name}!")
        else:
            file_path = path

        if file_path.suffix == ".csv":
            data = ascii.read(file_path)
            return Catalog(data)
        else:
            raise NotImplementedError(f"File loader not implemented for file type {file_path.suffix}")



def file_mask_handler():
    pass
class FileHandler(ABC):

    def __init__(self, dtype: str, *args, **kwargs):
        self.type = dtype
        self.region_id = None

    def __call__(self, path: Path, query_region: BaseRegion, *args, **kwargs):
        if self.region_id is not None:
            return self.get_file(path / str(self.region_id), query_region.name)
        return self.get_file(path, query_region.name)

    def set_subregion(self, region_id: str) -> None:
        self.region_id = region_id
    
    @abstractmethod
    def get_file(self, path: Path, region: str) -> any:
        pass

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
        return handler()
    except AttributeError:
        raise NotImplementedError(f"Data type {dtype} does not have a default handler")

class get_catalog(FileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__("catalog")


    def get_file(self, path: Path, region: str, *args, **kwargs) -> Any:
        """
        Default handler for a catalog.
        Loads a single catalog, assuming the region name can be found in the file name.
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