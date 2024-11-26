from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from pytest import fixture

from heinlein import load_dataset
from heinlein.api import add

DATA_PATH = Path("/home/data")
MS_DATA_PATH = DATA_PATH / "ms"
radius = 120 * u.arcsec


def setup_module():
    add_ms()


@fixture
def dataset():
    dataset = load_dataset("ms")
    dataset.set_field((3, 5))
    return dataset


def add_ms():
    catalog_path = MS_DATA_PATH / "catalog" / "ms.db"
    add("ms", "catalog", str(catalog_path), force=True)


def test_ms(dataset):
    coordinate = SkyCoord(0, 0, unit="deg")
    a = dataset.cone_search((0, 0), radius, dtypes=["catalog"])
    cat = a["catalog"]
    assert len(cat) > 0
    assert all(cat["coordinates"].separation(coordinate) < radius)


def test_ms_box_search(dataset):
    cone_results = dataset.cone_search((0, 0), radius, dtypes=["catalog"])
    box_results = dataset.box_search((0, 0), 2 * radius, dtypes=["catalog"])
    cat = box_results["catalog"]
    assert len(cat) > 0
    cone_halo_ids = cone_results["catalog"]["HaloID"]
    box_halo_ids = cat["HaloID"]

    assert set(cone_halo_ids).issubset(set(box_halo_ids))
    assert len(cone_halo_ids) < len(box_halo_ids)
