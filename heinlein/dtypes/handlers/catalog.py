
from ast import Param
from pathlib import Path
import logging
import sqlite3
import numpy as np
from yaml import parse
from heinlein.dtypes.handlers import handler
from heinlein.dtypes.catalog import Catalog, ParameterMap

from astropy.io import ascii

from heinlein.dtypes import catalog

def get_catalog_handler(path: Path, dconfig: dict):
    if not path.is_file():
        return CsvCatalogHandler(path, dconfig)
    elif path.suffix == ".db":
        return SQLiteCatalogHandler(path, dconfig)


class CsvCatalogHandler(handler.Handler):

    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config, "catalog")
        self._map = ParameterMap.get_map(self._config)
    
    def get_data(self, region_names: list, *args, **kwargs):
        """
        Default handler for a catalog.
        Loads a single catalog, assuming the region name can be found in the file name.
        """
        storage = {}
        parent_region = kwargs.get("parent_region", False)
        if not self._path.exists():
            print(f"Path {self._path} does not exist! Perhaps it is in an external storage device that isn't attached.")
            return None
        if not self._path.is_file():
            for name in region_names:
                files = [f for f in self._path.glob(f"*{name}*") if not f.name.startswith('.')]
                if len(files) > 1:
                    raise NotImplementedError
                if len(files) == 0:
                    new_path = self._path / str(parent_region.name)
                    files = [f for f in new_path.glob(f"*{name}*") if not f.name.startswith('.')]
                try:
                    file_path = files[0]
                    data = ascii.read(file_path)
                    storage.update({name: Catalog(data, parmap=self._map)})
                except IndexError:
                    logging.error(f"No file found for dtype catalog in region {name}!")
        else:
            file_path = self._path
            if file_path.suffix == ".csv":
                data = ascii.read(file_path)
                for name in region_names:
                    mask = data[self._config['region']] == name
                    storage.update({name: Catalog(data[mask], parmap=self._map)})
        return storage


class SQLiteCatalogHandler(handler.Handler):
    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config, "catalog")
        self._initialize_connection()
        self._map = ParameterMap.get_map(self._config)

    def _initialize_connection(self, *args, **kwargs):
        self._con = sqlite3.connect(self._path, cached_statements=1)
        sql = "SELECT * FROM sqlite_master where type='table'"
        cur = self._con.execute(sql)
        self._tnames = [t[1] for t in cur.fetchall()]
    
    def get_data(self, region_names: list, *args, **kwargs):
        subregion_key = self._map.get("subregion")
        if subregion_key is not None:
            splits = [rname.split(".") for rname in region_names]
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
            return self._get(region_names)

    def get_with_subregions(self, regions: dict):
        subregion_key = self._map.get('subregion')
        region_key = self._map.get('region')
        storage = {}
        for region, subregions in regions.items():
            region_names = [".".join([region, sr]) for sr in subregions]
            if str(region) in self._tnames:
                table = self.get_where(region, {subregion_key: subregions})
                if len(table) != 0:
                    for index, sr in enumerate(subregions):
                        mask = (table[region_key].astype(str) == region) & (table[subregion_key].astype(str) == sr)
                        storage.update({region_names[index]: table[mask]})
                else:
                    storage.update({sr: Catalog() for sr in region_names})                    
                    #This needs to be fixed
            elif len(self._tnames) == 1:
                region_names = [".".join([region, sr]) for sr in subregions]

                table = self.get_where(self._tnames[0], {region_key: region.name, subregion_key: subregions})
                for index, sr in enumerate(subregions):
                    mask = table[subregion_key] == sr
                    storage.update({region_names[index]: table[mask]})
            else:
                storage.update({sr: Catalog() for sr in region_names})
        return storage
    
    def _get(self, region_names: list):
        storage = {}
        for region in region_names:
            if region in self._tnames:
                table = self.get_all(region)

                storage.update({region: table})

            elif len(self._tnames) == 1:
                region_key = self._map.get('region')
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
            return Catalog()
        rows = np.array(rows, dtype=object)
        missing_values = np.where(rows == None)
        rows[missing_values] = -1
        columns = [d[0] for d in cursor.description]
        c = Catalog.from_rows(rows=rows, columns=columns, parmap = self._map)
        return c
