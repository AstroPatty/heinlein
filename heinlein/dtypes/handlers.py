from asyncio import Handle
from cgi import parse_header
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
    def get_data(self, regions: list, *args, **kwargs):
        pass

class CsvCatalogHandler(Handler):

    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config)
    
    def get_data(self, regions: list, *args, **kwargs):
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
    
    def get_data(self, regions: list, *args, **kwargs):
        region_key = self._config['region']
        subregion_key = self._config.get("subregion", False)
        if subregion_key:
            splits = [str(reg.name).split(".") for reg in regions]
            regions_to_get = {}
            for split in splits:
                if len(split) == 2:
                    if split[0] in regions_to_get.keys():
                        regions_to_get[split[0]].append(split[1])
                    else:
                        regions_to_get.update({split[0]: [split[1]]})
                elif len(split) ==  2 and split[0] not in regions_to_get.keys():
                        regions_to_get.update({split[0]: []})
            return self.get_with_subregions(regions_to_get)
        else:
            regions_to_get = [str(r.name) for r in regions]
            return self._get(regions_to_get)

    def get_with_subregions(self, regions: dict):
        subregion_key = self._config['subregion']
        region_key = self._config.get('region', False)

        storage = {}
        for region, subregions in regions.items():
            if str(region) in self._tnames:
                table = self.get_where(region, {subregion_key: subregions})
                if table is not None:
                    region_names = [".".join([region, sr]) for sr in subregions]
                    for index, sr in enumerate(subregions):
                        mask = (table[region_key].astype(str) == region) & (table[subregion_key].astype(str) == sr)
                        storage.update({region_names[index]: table[mask]})
                else:
                    storage.update({region: self.get_all(region.name)})
                    #This needs to be fixed
            elif len(self._tnames) == 1:
                region_names = [".".join([region, sr]) for sr in subregions]

                table = self.get_where(self._tnames[0], {region_key: region.name, subregion_key: subregions})
                for index, sr in enumerate(subregions):
                    mask = table[subregion_key] == sr
                    storage.update({region_names[index]: table[mask]})

        return storage
    
    def _get(self, regions: list):
        storage = {}
        for region in regions:
            if region in self._tnames:
                table = self.get_all(region)
                storage.update({region: table})
            elif len(self._tnames) == 1:
                region_key = self._config['region']
                table = self.get_where(self._tnames[0], {region_key: region.name})
                storage.update({region: table})
        return storage

    def get_where(self, tname: str, conditions: dict):
        base_query = f"SELECT * FROM \"{tname}\" WHERE "
        base_condition = "{} = \"{}\""
        multiple_base_conditions = "{} IN ({})"
        output_conditions = []
        for k, vs in conditions.items():
            if type(vs) is list:
                c = "\",\"".join([str(v) for v in vs])
                c = "\"" + c + "\""
                output_conditions.append(multiple_base_conditions.format(k, c))
            else:
                output_conditions.append(base_condition.format(k, vs))
        query =  base_query + " AND ".join(output_conditions)
        return self.execute_query(query)

    def get_all(self, tname):
        query = f"SELECT * FROM \"{tname}\""
        return self.execute_query(query)


    def execute_query(self, query):
        cur = self._con.execute(query)
        table = self._parse_return(cur)
        return table
    
    def _parse_return(self, cursor, *args, **kwargs):
        rows = cursor.fetchall()
        if len(rows) == 0:
            return None
        columns = [d[0] for d in cursor.description]
        c = Catalog.from_rows(rows=rows, columns=columns)
        return c

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
