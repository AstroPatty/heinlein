from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from heinlein.utilities.prep import database_from_csvs

DATA_PATH = Path("/home/data")
DES_CATALOG_PATH = DATA_PATH / "des" / "catalog"

DES_ORIGINAL_DB_PATH = DATA_PATH / "des" / "catalog" / "des_test.db"
DES_TEST_DB_PATH = DATA_PATH / "des" / "catalog" / "des.db"


@pytest.fixture()
def catalog_path():
    yield DES_TEST_DB_PATH
    try:
        DES_TEST_DB_PATH.unlink()
    except FileNotFoundError:
        pass


def test_catalog_prep(catalog_path):
    csvs = list(DES_CATALOG_PATH.glob("*.csv"))
    path = database_from_csvs("des", csvs)
    assert path == catalog_path
    assert path.exists()
    assert compare_databases(DES_ORIGINAL_DB_PATH, catalog_path)


def compare_databases(db1: Path, db2: Path):
    # Connect to the databases
    reference_engine = create_engine(f"sqlite:///{db1}").connect()
    test_engine = create_engine(f"sqlite:///{db2}").connect()
    # Get the table names
    reference_tables = inspect(reference_engine).get_table_names()
    test_tables = inspect(test_engine).get_table_names()
    # Compare the table names
    assert set(reference_tables) == set(test_tables)
    # Compare the data in the tables
    for table in reference_tables:
        query = text(f"SELECT COADD_OBJECT_ID FROM '{table}' ORDER BY COADD_OBJECT_ID")
        reference_data = reference_engine.execute(query).fetchall()
        test_data = test_engine.execute(query).fetchall()
        assert reference_data == test_data
    return True
