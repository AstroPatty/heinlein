import pickle
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from pytest import fixture

from heinlein import load_dataset, set_option
from heinlein.api import add
from heinlein.region.footprint import Footprint

DATA_PATH = Path("/home/data")
radius = 2 * u.arcmin


def setup_module():
    add_cfht()


@fixture
def dataset():
    set_option("CACHE_SIZE", "10G")
    return load_dataset("cfht")


@fixture
def center():
    regions_path = DATA_PATH / "cfht" / "test_regions.reg"
    with open(regions_path, "rb") as f:
        regions = pickle.load(f)
    bounds = [r.bounds for r in regions]

    overall_bounds = [
        min([b[0] for b in bounds]),
        min([b[1] for b in bounds]),
        max([b[2] for b in bounds]),
        max([b[3] for b in bounds]),
    ]

    center = SkyCoord(
        ra=(overall_bounds[0] + overall_bounds[2]) / 2 * u.deg,
        dec=(overall_bounds[1] + overall_bounds[3]) / 2 * u.deg,
    )
    return center


def add_cfht():
    catalog_path = DATA_PATH / "cfht" / "cfht_test.db"
    mask_path = DATA_PATH / "cfht" / "mask"
    add("cfht", "catalog", str(catalog_path), force=True)
    add("cfht", "mask", str(mask_path), force=True)


def test_cfht_cone_search(dataset, center):
    second_center = center.directional_offset_by(0, 4 * u.arcmin)
    a = dataset.cone_search(center, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0

    a = dataset.cone_search(second_center, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0


def test_cfht_box_search(dataset, center):
    data = dataset.box_search(center, 2 * radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
