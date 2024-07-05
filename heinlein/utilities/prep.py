from pathlib import Path

import polars as pl
from sqlalchemy import MetaData, create_engine

from heinlein.dtypes.catalog import load_config
from heinlein.manager.manager import get_manager, initialize_dataset


def database_from_csvs(dataset_name: str, csvs: list[Path]):
    try:
        manager = get_manager(dataset_name)
    except FileNotFoundError:
        initialize_dataset(dataset_name)
        manager = get_manager(dataset_name)
    try:
        catalog_config = manager.config["dconfig"]["catalog"]
    except KeyError:
        raise KeyError("Catalog configuration not found in dataset configuration")

    db_path = csvs[0].parent / f"{dataset_name}.db"
    engine = create_engine(f"sqlite:///{db_path}").connect()

    region_key = catalog_config["region"]
    index_key = catalog_config["index_key"]

    meta = MetaData()
    column_config = load_config()["colunms"]
    for csv in csvs:
        data = pl.read_csv(csv)
        for name, aliases in column_config.items():
            for alias in aliases:
                if alias in data.columns:
                    data = data.rename({alias: name})

        if region_key not in data.columns:
            raise KeyError(f"Region key {region_key} not found in {csv.name}")
        if index_key not in data.columns:
            raise KeyError(f"Index key {index_key} not found in {csv.name}")
        partitions = data.partition_by(region_key, as_dict=True)
        for region, partition in partitions.items():
            meta.reflect(engine)
            tables_in_db = meta.tables.keys()
            if region not in tables_in_db:
                partition.write_database(
                    region,
                    engine,
                    if_exists="fail",
                    engine_options={"index_label": index_key},
                )

            else:
                partition.write_database(
                    f"{region}_temp",
                    engine,
                    if_exists="fail",
                    engine_options={"index_label": index_key},
                )

                engine.execute(
                    f"""
                    INSERT OR IGNORE {region} SELECT * FROM {region}_temp
                    """
                )
                engine.execute(
                    f"""
                    DROP TABLE {region}_temp
                    """
                )


def regularize_sqlite_databse(database_path: Path):
    engine = create_engine(f"sqlite:///{database_path}").connect()
    column_config = load_config()["columns"]
    meta = MetaData()
    meta.reflect(engine)
    tables_in_db = meta.tables.keys()

    for table in tables_in_db:
        table = meta.tables[table]
        for name, aliases in column_config.items():
            for alias in aliases:
                if alias in table.columns:
                    engine.execute(
                        f"""
                        ALTER TABLE {table} RENAME COLUMN {alias} TO {name}
                        """
                    )
