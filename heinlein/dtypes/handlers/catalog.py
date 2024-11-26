import json
from pathlib import Path

import astropy.units as u
from astropy.io import ascii
from astropy.table import Table as AstropyTable
from sqlalchemy import MetaData
from sqlalchemy import Table as SQLTable
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

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
        self._inspector = inspect(self._engine)
        self._metadata = MetaData()
        self._metadata.reflect(bind=self._engine)
        # Get the table names
        self._tnames = self._inspector.get_table_names()

    def get_data_in_region(self, survey_regions: list[str], query_region: BaseRegion):
        ra_min, dec_min, ra_max, dec_max = query_region.bounds
        ra_cols = self._config.get("columns", {}).get("ra", [])
        dec_cols = self._config.get("columns", {}).get("dec", [])
        ra_min, dec_min, ra_max, dec_max = query_region.bounds
        if not isinstance(ra_cols, list):
            ra_cols = [ra_cols["key"]]
            ra_min = (ra_min * u.deg).to(ra_cols["unit"]).value
            ra_max = (ra_max * u.deg).to(ra_cols["unit"]).value

        if not isinstance(dec_cols, list):
            dec_cols = [dec_cols["key"]]
            dec_min = (dec_min * u.deg).to(dec_cols["unit"]).value
            dec_max = (dec_max * u.deg).to(dec_cols["unit"]).value

        if not ra_cols or not dec_cols:
            raise ValueError("Catalog does not have the correct columns for ra and dec")

        storage = {}
        with Session(self._engine) as session:
            for region in survey_regions:
                if region in self._tnames:
                    table = SQLTable(region, self._metadata, autoload_with=self._engine)
                    db_columns = table.columns.keys()
                    ra_col = set(ra_cols) & set(db_columns)
                    dec_col = set(dec_cols) & set(db_columns)
                    if len(ra_col) != 1 or len(dec_col) != 1:
                        raise ValueError(
                            "Catalog does not have the correct columns for ra and dec"
                        )
                    ra_name = list(ra_col)[0]
                    dec_name = list(dec_col)[0]
                    stmt = select(table).where(
                        table.c[ra_name].between(ra_min, ra_max)
                        & table.c[dec_name].between(dec_min, dec_max)
                    )
                    result = session.execute(stmt).fetchall()
                    data = AstropyTable(rows=result, names=table.columns.keys())
                    storage.update({region: Catalog(data, self._config)})

                else:
                    raise ValueError(f"Table {region} not found in database!")
        return storage

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
        with Session(self._engine) as session:
            for region, subregions in regions.items():
                region_names = [".".join([region, sr]) for sr in subregions]
                if str(region) in self._tnames:
                    table = SQLTable(region, self._metadata, autoload_with=self._engine)
                    stmt = select(table).where(table.c[subregion_key].in_(subregions))
                    result = session.execute(stmt).fetchall()
                    data = AstropyTable(rows=result, names=table.columns.keys())
                    if len(data) != 0:
                        for index, sr in enumerate(subregions):
                            mask = (data[region_key].astype(str) == region) & (
                                data[subregion_key].astype(str) == sr
                            )
                            storage.update({region_names[index]: data[mask]})
                    else:
                        storage.update({sr: AstropyTable() for sr in region_names})
                        # This needs to be fixed
                else:
                    storage.update({sr: AstropyTable() for sr in region_names})
        return storage

    def get(self, region_names: list):
        storage = {}
        if not set(region_names).issubset(self._tnames):
            raise ValueError(f"Tables {region_names} not found in database!")
        with Session(self._engine) as session:
            for region in region_names:
                table = SQLTable(region, self._metadata, autoload_with=self._engine)
                stmt = select(table)
                result = session.execute(stmt).fetchall()
                data = AstropyTable(rows=result, names=table.columns.keys())
                storage.update({region: data})
        return storage
