import pickle
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

from heinlein import load_dataset
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


def test_hsc():
    regions_path = DATA_PATH / "hsc" / "test_regions.reg"
    with open(regions_path, "rb") as f:
        regions = pickle.load(f)
    regions = {r.name: r for r in regions}
    f = Footprint(regions)
    center = f._footprint.centroid
    center = SkyCoord(center.x, center.y, unit="deg")
    second_center = center.directional_offset_by(0, 4 * u.arcmin)
    d = load_dataset("hsc")

    data = d.cone_search(center, radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0

    data = d.cone_search(second_center, radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0
