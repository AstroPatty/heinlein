from pathlib import Path

from heinlein.utilities.prep import database_from_csvs

DATA_PATH = Path("/home/data")
DES_CATALOG_PATH = DATA_PATH / "des" / "catalog"


def test_catalog_prep():
    csvs = list(DES_CATALOG_PATH.glob("*.csv"))
    database_from_csvs("des", csvs)
    assert True
