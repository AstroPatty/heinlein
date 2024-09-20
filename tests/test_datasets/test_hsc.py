import pickle
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from pytest import fixture

from heinlein import load_dataset, set_option
from heinlein.api import add
from heinlein.region.footprint import Footprint

radius = 2 * u.arcmin

DATA_PATH = Path("/home/data")


def setup_module():
    add_hsc()


def add_hsc():
    catalog_path = DATA_PATH / "hsc" / "hsc_test.db"
    add("hsc", "catalog", str(catalog_path), force=True)
    mask_path = DATA_PATH / "hsc" / "masks"
    add("hsc", "mask", str(mask_path), force=True)


@fixture
def center():
    regions_path = DATA_PATH / "hsc" / "test_regions.reg"
    with open(regions_path, "rb") as f:
        regions = pickle.load(f)
    regions = {r.name: r for r in regions}
    f = Footprint(regions)
    center = f._footprint.centroid
    center = SkyCoord(center.x, center.y, unit="deg")
    return center


@fixture
def dataset():
    set_option("CACHE_SIZE", "10G")
    return load_dataset("hsc")


def test_hsc_cone_search(dataset, center):
    second_center = center.directional_offset_by(0, 4 * u.arcmin)

    data = dataset.cone_search(center, radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0

    data = dataset.cone_search(second_center, radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0


def test_hsc_box_search(dataset, center):
    data = dataset.box_search(center, 2 * radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
