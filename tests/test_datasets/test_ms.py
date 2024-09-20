from pathlib import Path

import astropy.units as u

from heinlein import load_dataset
from heinlein.api import add

DATA_PATH = Path("/home/data")
MS_DATA_PATH = DATA_PATH / "ms"
radius = 120 * u.arcsec


def setup_module():
    add_ms()


def add_ms():
    catalog_path = MS_DATA_PATH / "catalog"
    add("ms", "catalog", str(catalog_path), force=True)


def test_ms():
    d = load_dataset("ms")
    d.set_field((3, 5))
    a = d.cone_search((0, 0), radius, dtypes=["catalog"])
    cat = a["catalog"]
    assert len(cat) > 0
