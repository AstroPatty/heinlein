import pickle
import subprocess
from pathlib import Path

import astropy.units as u

from heinlein import Region, load_dataset
from heinlein.api import add
from heinlein.region.footprint import Footprint

DATA_PATH = Path("/home/data")
DES_DATA_PATH = DATA_PATH / "des"
MS_DATA_PATH = DATA_PATH / "ms"
des_center = (7.8, -33.9)
radius = 120 * u.arcsecond


# For now, we are testing on des data
def setup_module():
    add_des()
    add_ms()
    add_cfht()
    add_hsc()


def add_cfht():
    catalog_path = DATA_PATH / "cfht" / "cfht_test.db"
    mask_path = DATA_PATH / "cfht" / "mask"
    add("cfht", "catalog", str(catalog_path), force=True)
    add("cfht", "mask", str(mask_path), force=True)


def add_hsc():
    catalog_path = DATA_PATH / "hsc" / "hsc_test.db"
    add("hsc", "catalog", str(catalog_path), force=True)
    mask_path = DATA_PATH / "hsc" / "masks"
    add("hsc", "mask", str(mask_path), force=True)


def add_des():
    catalog_path = DES_DATA_PATH / "catalog" / "des_test.db"
    mask_path = DES_DATA_PATH / "mask"
    add("des", "catalog", str(catalog_path), force=True)
    add("des", "mask", str(mask_path), force=True)


def add_ms():
    catalog_path = MS_DATA_PATH / "catalog"
    add("ms", "catalog", str(catalog_path), force=True)


def test_hsc():
    regions_path = DATA_PATH / "hsc" / "test_regions.reg"
    with open(regions_path, "rb") as f:
        regions = pickle.load(f)
    regions = {r.name: r for r in regions}
    f = Footprint(regions)
    d = load_dataset("hsc")

    sample = f.sample(1)

    print("HSC CONE SEARCH: ", sample, radius)
    circle = Region.circle(sample, radius)
    overlaps = d.footprint.get_overlapping_region_names(circle)
    print(overlaps)

    data = d.cone_search(sample, radius, dtypes=["catalog", "mask"])
    cat = data["catalog"]
    mask = data["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0


def test_cfht():
    regions_path = DATA_PATH / "cfht" / "test_regions.reg"
    with open(regions_path, "rb") as f:
        regions = pickle.load(f)
    regions = {r.name: r for r in regions}
    f = Footprint(regions)
    d = load_dataset("cfht")
    sample = f.sample(1)

    a = d.cone_search(sample, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert len(cat) > 0


def test_des():
    print("TESTING DES")
    d = load_dataset("des")
    a = d.cone_search(des_center, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)


def test_ms():
    print("TESTING MS")
    d = load_dataset("ms")
    d.set_field((3, 5))
    a = d.cone_search((0, 0), radius, dtypes=["catalog"])
    cat = a["catalog"]
    assert len(cat) > 0
