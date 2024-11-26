import json
from pathlib import Path

import pandas as pd
from astropy.io import ascii
from astropy.table import Table
from sqlalchemy import create_engine, text

from heinlein.dtypes.catalog import Catalog
from heinlein.dtypes.handlers import handler
from heinlein.locations import MAIN_CONFIG_DIR
from heinlein.region.base import BaseRegion


class heinleinIoException(Exception):
    pass


def load_config():
    catalog_config_location = MAIN_CONFIG_DIR / "dtypes" / "catalog.json"
    with open(catalog_config_location, "rb") as f:
        data = json.load(f)
    return data


def get_catalog_handler(config: dict, dconfig: dict):
    data = config.get("data", {})
    base_dconfig = load_config()
    new_dconfig = base_dconfig | dconfig  # dconfig gets priority
    try:
        path = Path(data["catalog"])
    except KeyError:
        raise heinleinIoException("No catalog path found in config!")

    if path.is_dir():
        return CsvCatalogHandler(path, new_dconfig)

    elif path.suffix == ".db":
        return SQLiteCatalogHandler(path, new_dconfig)
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
    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config, "catalog")
        if not path.exists():
            raise heinleinIoException(f"Path {path} does not exist!")
        elif path.suffix != ".db":
            raise heinleinIoException(f"Path {path} is not a .db file!")

        self.create_engine()

    def create_engine(self, *args, **kwargs):
        self._engine = create_engine(f"sqlite:///{self._path}")
        self._con = self._engine.connect()
        sql = "SELECT * FROM sqlite_master where type='table'"
        cur = self._con.execute(text(sql))
        self._tnames = [t[1] for t in cur.fetchall()]

    def get_data_in_region(self, survey_regions: list[str], query_region: BaseRegion):
        ra_min, dec_min, ra_max, dec_max = query_region.bounds
        ra_cols = self._config.get("columns", {}).get("ra", [])
        dec_cols = self._config.get("columns", {}).get("dec", [])

        if not isinstance(ra_cols, list):
            ra_cols = [ra_cols["key"]]
        if not isinstance(dec_cols, list):
            dec_cols = [dec_cols["key"]]

        if not ra_cols or not dec_cols:
            raise ValueError("Catalog does not have the correct columns for ra and dec")

        storage = {}
        for region in survey_regions:
            if region in self._tnames:
                db_column_names = self._engine.execute(
                    f"PRAGMA table_info({region})"
                ).fetchall()
                db_column_names = [c[1] for c in db_column_names]
                ra_col = set(ra_cols) & set(db_column_names)
                dec_col = set(dec_cols) & set(db_column_names)
                if len(ra_col) != 1 or len(dec_col) != 1:
                    raise ValueError(
                        "Catalog does not have the correct columns for ra and dec"
                    )
                ra_name = list(ra_col)[0]
                dec_name = list(dec_col)[0]
                ranges = {
                    ra_name: (ra_min, ra_max),
                    dec_name: (dec_min, dec_max),
                }
                data = self.get_in_ranges(region, ranges)
                storage.update({region: Catalog(data, self._config)})

            else:
                raise ValueError(f"Table {region} not found in database!")

    def get_data_by_regions(self, survey_regions: list[str], *args, **kwargs):
        subregion_key = self._config.get("subregion", None)
        if subregion_key is not None:
            splits = [rname.split(".") for rname in survey_regions]
            regions_to_get = {}
            for split in splits:
                if len(split) == 2:
                    if split[0] in regions_to_get.keys():
                        regions_to_get[split[0]].append(split[1])
                    else:
                        regions_to_get.update({split[0]: [split[1]]})
                elif len(split) == 2 and split[0] not in regions_to_get.keys():
                    regions_to_get.update({split[0]: []})

            storage = self.get_with_subregions(regions_to_get)
        else:
            storage = self.get(survey_regions)

        return {k: Catalog(table, self._config) for k, table in storage.items()}

    def get_with_subregions(self, regions: dict):
        subregion_key = self._config.get("subregion", None)
        region_key = self._config.get("region", None)
        storage = {}
        for region, subregions in regions.items():
            region_names = [".".join([region, sr]) for sr in subregions]
            if str(region) in self._tnames:
                table = self.get_where(region, {subregion_key: subregions})
                if len(table) != 0:
                    for index, sr in enumerate(subregions):
                        mask = (table[region_key].astype(str) == region) & (
                            table[subregion_key].astype(str) == sr
                        )
                        storage.update({region_names[index]: table[mask]})
                else:
                    storage.update({sr: Catalog() for sr in region_names})
                    # This needs to be fixed
            elif len(self._tnames) == 1:
                region_names = [".".join([region, sr]) for sr in subregions]

                table = self.get_where(
                    self._tnames[0],
                    {region_key: region.name, subregion_key: subregions},
                )
                for index, sr in enumerate(subregions):
                    mask = table[subregion_key] == sr
                    storage.update({region_names[index]: table[mask]})
            else:
                storage.update({sr: Table() for sr in region_names})
        return storage

    def get(self, region_names: list):
        storage = {}
        for region in region_names:
            if region in self._tnames:
                table = self.get_all(region)

                storage.update({region: table})

            elif len(self._tnames) == 1:
                region_key = self._config.get("region", None)
                table = self.get_where(self._tnames[0], {region_key: region.name})
                storage.update({region: table})
        return storage

    def get_in_ranges(self, tname: str, ranges: dict[str, tuple]):
        base_query = f'SELECT * FROM "{tname}" WHERE '
        base_condition = "{} BETWEEN {} AND {}"
        output_conditions = []
        for k, (v1, v2) in ranges.items():
            output_conditions.append(base_condition.format(k, v1, v2))
        query = base_query + " AND ".join(output_conditions)
        table = self.execute_query(query)
        return self._parse_return(table)

    def get_where(self, tname: str, conditions: dict):
        base_query = f'SELECT * FROM "{tname}" WHERE '
        base_condition = '{} = "{}"'
        multiple_base_conditions = "{} IN ({})"
        output_conditions = []
        for k, vs in conditions.items():
            if isinstance(vs, list):
                c = '","'.join([str(v) for v in vs])
                c = '"' + c + '"'
                output_conditions.append(multiple_base_conditions.format(k, c))
            else:
                output_conditions.append(base_condition.format(k, vs))
        query = base_query + " AND ".join(output_conditions)
        table = self.execute_query(query)
        return self._parse_return(table)

    def get_all(self, tname):
        query = f'SELECT * FROM "{tname}"'
        table = self.execute_query(query)
        return self._parse_return(table)

    def execute_query(self, query):
        q = text(query)
        data = pd.read_sql(q, self._con)
        return data

    def _parse_return(self, data, *args, **kwargs):
        if len(data) == 0:
            return Catalog()

        # replace all None with np.nan
        data = Table.from_pandas(data)
        return data
