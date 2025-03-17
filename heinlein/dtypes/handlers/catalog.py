from pathlib import Path

import pandas as pd
from astropy.io import ascii
from astropy.table import Table
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from heinlein.dtypes.catalog import Catalog
from heinlein.dtypes.handlers import handler


class heinleinIoException(Exception):
    pass


def get_region_table_names(config: dict, region_names: list) -> dict[str, list]:
    regions_to_get = {}
    subregion_key = config.get("subregion", None)
    if subregion_key is not None:
        splits = [rname.split(".") for rname in region_names]
        for split in splits:
            if len(split) == 2:
                if split[0] in regions_to_get.keys():
                    regions_to_get[split[0]].append(split[1])
                else:
                    regions_to_get.update({split[0]: [split[1]]})
            elif len(split) == 2 and split[0] not in regions_to_get.keys():
                regions_to_get.update({split[0]: []})
    else:
        for region in region_names:
            regions_to_get.update({region: []})

    return regions_to_get


def split_table_by(table: Table, key: str) -> dict[str, Table]:
    """
    Splits a table by a given key.
    Returns a dictionary of tables, where the
    keys are the unique values of the given key.
    """
    unique_values = set(table[key])
    tables = {}
    for value in unique_values:
        tables.update({value: table[table[key] == value]})
    return tables


def get_catalog_handler(config: dict, dconfig: dict):
    data = config.get("data", {})
    try:
        path = Path(data["catalog"])
    except KeyError:
        raise heinleinIoException("No catalog path found in config!")

    if path.is_dir():
        return CsvCatalogHandler(path, dconfig)

    elif path.suffix == ".db":
        return SQLiteCatalogHandler(path, dconfig)
    else:
        raise heinleinIoException("Catalog path is not a directory or a .db file!")


class CsvCatalogHandler(handler.Handler):
    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config, "catalog")
        self.known_files = [f for f in self._path.glob("*") if f.is_file()]

    def get_data(self, region_names: list, *args, **kwargs):
        """
        Default handler for a catalog.
        Loads a single catalog, assuming the region name can be found in the file name.
        """
        storage = {}
        files = {}
        for name in region_names:
            region_file = list(filter(lambda x: name in x.name, self.known_files))
            if len(region_file) == 0:
                raise heinleinIoException(
                    "No file found for region "
                    f"{name}! Perhaps it is in an external"
                    " storage device that isn't attached."
                )
            elif len(region_file) != 1:
                raise heinleinIoException(
                    "Multiple files found for region {name}! Found {region_file}"
                )
            files.update({name: region_file[0]})

        for name, path in files.items():
            if not path.exists():
                print(
                    f"Path {self._path} does not exist! Perhaps it is "
                    "in an external storage device that isn't attached."
                )
                return None
            data = ascii.read(path)
            storage.update({name: Catalog(data, self._config)})
        return storage


class SQLiteCatalogHandler(handler.Handler):
    region_query = """SELECT * FROM \"{}\""""
    subergion_query = """SELECT * FROM \"{}\" WHERE {} IN ({})"""

    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config, "catalog")
        if not path.exists():
            raise heinleinIoException(f"Path {path} does not exist!")
        elif path.suffix != ".db":
            raise heinleinIoException(f"Path {path} is not a .db file!")

        self._create_engine()

    def _create_engine(self, *args, **kwargs):
        self._engine = create_engine(f"sqlite:///{self._path}")
        self._con = self._engine.connect()
        sql = "SELECT * FROM sqlite_master where type='table'"
        cur = self._con.execute(text(sql))
        self._tnames = [t[1] for t in cur.fetchall()]

    def get_data(self, region_names: list, *args, **kwargs):
        regions_to_get = get_region_table_names(self._config, region_names)
        storage = {}
        for region, subregions in regions_to_get.items():
            if not subregions:
                query = self.region_query.format(region)
                try:
                    table = self.execute_query(query)
                except OperationalError:
                    continue
                storage.update({region: Table.from_pandas(table)})
            else:
                subregion_key = self._config.get("subregion", None)
                search_subregions = ",".join([f'"{sr}"' for sr in subregions])
                query = self.subergion_query.format(
                    region, subregion_key, search_subregions
                )
                try:
                    table = self.execute_query(query)
                except OperationalError:
                    continue
                tables_by_subregion = split_table_by(table, subregion_key)
                for subregion, sub_table in tables_by_subregion.items():
                    storage.update(
                        {f"{region}.{subregion}": Table.from_pandas(sub_table)}
                    )

        return {k: Catalog(table, self._config) for k, table in storage.items()}

    def execute_query(self, query):
        q = text(query)
        data = pd.read_sql(q, self._con)
        return data
