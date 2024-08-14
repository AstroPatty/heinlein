from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, create_engine, text

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
    column_config = load_config()["columns"]
    for csv in csvs:
        data = pd.read_csv(csv)
        for name, aliases in column_config.items():
            for alias in aliases:
                if alias in data.columns:
                    data = data.rename({alias: name})

        if region_key not in data.columns:
            raise KeyError(f"Region key {region_key} not found in {csv.name}")
        if index_key not in data.columns:
            raise KeyError(f"Index key {index_key} not found in {csv.name}")
        partitions = data.groupby(region_key)
        for rname, partition in partitions:
            meta.reflect(engine)
            tables_in_db = meta.tables.keys()
            if rname not in tables_in_db:
                partition.to_sql(
                    rname,
                    engine,
                    if_exists="fail",
                )

            else:
                partition.to_sql(
                    f"{rname}_temp",
                    engine,
                    if_exists="fail",
                )

                query = text(
                    f"""
                    INSERT INTO '{rname}'
                    SELECT * FROM '{rname}_temp'
                    WHERE {index_key} NOT IN (SELECT {index_key} FROM '{rname}')
                    """
                )
                engine.execute(query)
                engine.execute(text(f"DROP TABLE '{rname}_temp'"))
                engine.commit()
    return db_path


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
