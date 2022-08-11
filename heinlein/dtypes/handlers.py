from asyncio import Handle
from pathlib import Path
import sqlite3
from typing import Any
from heinlein.region import BaseRegion
from heinlein.dtypes.catalog import Catalog
from astropy.io import ascii
import sys
from abc import ABC, abstractmethod
import logging
import time

def get_file_handlers(data: dict):
    handlers = {}
    for dtype, dconfig in data.items():
        path = dconfig['path']
        dc_ = {k: v for k,v in dconfig.items() if k != "path"}

        if dtype == "catalog":
            f = get_catalog_handler(Path(path), dc_)
        else:
            f = FileMaskHandler
        handlers.update({dtype: f})
    handlers.update({"mask": FileMaskHandler})
    return handlers

def get_catalog_handler(path: Path, dconfig: dict):
    if not path.is_file():
        return CsvCatalogHandler(path, dconfig)
    elif path.suffix == ".db":
        return SQLiteCatalogHandler(path, dconfig)

        
class Handler(ABC):

    def __init__(self, path: Path, dconfig: dict, *args, **kwargs):
        self._path = path
        self._config = dconfig

    @abstractmethod
    def get_data(self, region: BaseRegion, *args, **kwargs):
        pass

class CsvCatalogHandler(Handler):

    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config)
    
    def get_data(self, region: BaseRegion, *args, **kwargs):
        """
        Default handler for a catalog.
        Loads a single catalog, assuming the region name can be found in the file name.
        """
        parent_region = kwargs.get("parent_region", False)
        if not self._path.exists():
            print(f"Path {self._path} does not exist! Perhaps it is in an external storage device that isn't attached.")
            return None

        if not self._path.is_file():
            files = [f for f in self._path.glob(f"*{region.name}*") if not f.name.startswith('.')]
            if len(files) > 1:
                raise NotImplementedError
            if len(files) == 0:
                new_path = self._path / str(parent_region.name)
                files = [f for f in new_path.glob(f"*{region.name}*") if not f.name.startswith('.')]
            try:
                file_path = files[0]
            except IndexError:
                logging.error(f"No file found for dtype catalog in region {region.name}!")
        else:
            file_path = self._path

        if file_path.suffix == ".csv":
            data = ascii.read(file_path)
            return Catalog(data)
        else:
            raise NotImplementedError(f"File loader not implemented for file type {file_path.suffix}")
    
class FileMaskHandler(Handler):
    pass

class SQLiteCatalogHandler(Handler):
    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config)
        self._initialize_connection()
    
    def _initialize_connection(self, *args, **kwargs):
        self._con = sqlite3.connect(self._path)
        sql = "SELECT * FROM sqlite_master where type='table'"
        cur = self._con.execute(sql)
        self._tnames = [t[1] for t in cur.fetchall()]
    
    def get_data(self, region: BaseRegion, *args, **kwargs):
        if region.name in self._tnames:
            query = f"SELECT * FROM \"{region.name}\""
            cur = self._con.execute(query)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]
            c = Catalog.from_rows(rows=rows, columns=columns)
            return c
        elif len(self._tnames) == 1:
            region_key = self._config['region']
            sql = f"SELECT * FROM {self._tnames[0]} WHERE {region_key} = \"{region.name}\""
            cur = self._con.execute(sql)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]
            c = Catalog.from_rows(rows=rows, columns=columns)
            return c
        else:
            raise NotImplementedError("Can't infer the structure of the database!")

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
