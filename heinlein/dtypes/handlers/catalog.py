from pathlib import Path

import pandas as pd
from astropy.io import ascii
from astropy.table import Table
from sqlalchemy import create_engine, text

from heinlein.dtypes.catalog import Catalog
from heinlein.dtypes.handlers import handler


class heinleinIoException(Exception):
    pass


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
        subregion_key = self._config.get("subregion", None)
        if subregion_key is not None:
            splits = [rname.split(".") for rname in region_names]
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
            storage = self._get(region_names)

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

    def _get(self, region_names: list):
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
