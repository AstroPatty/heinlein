from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from pytest import fixture

import heinlein
from heinlein import load_dataset
from heinlein.api import add

radius = 2 * u.arcmin

DATA_PATH = Path("/home/data")

DES_CENTER = SkyCoord(7.8, -33.9, unit="deg")


def setup_module():
    add_des()


@fixture
def dataset():
    heinlein.set_option("CACHE_SIZE", "10G")
    return load_dataset("des")


def add_des():
    DES_DATA_PATH = DATA_PATH / "des"
    catalog_path = DES_DATA_PATH / "catalog" / "des_test.db"
    mask_path = DES_DATA_PATH / "mask"
    add("des", "catalog", str(catalog_path), force=True)
    add("des", "mask", str(mask_path), force=True)


def test_des_cone_search(dataset):
    dataset = load_dataset("des")
    a = dataset.cone_search(DES_CENTER, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert all(masked_cat["coordinates"].separation(DES_CENTER) < radius)

    new_center = DES_CENTER.directional_offset_by(0, 4 * u.arcmin)
    a = dataset.cone_search(new_center, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
    assert all(masked_cat["coordinates"].separation(new_center) < radius)


def test_cache_option(dataset):
    heinlein.set_option("CACHE_ENABLED", False)
    data = dataset.cone_search(DES_CENTER, radius, dtypes=["catalog", "mask"])
    no_cache_cat = data["catalog"]
    no_cache_mask = data["mask"]
    heinlein.set_option("CACHE_ENABLED", True)
    data = dataset.cone_search(DES_CENTER, radius, dtypes=["catalog", "mask"])
    cache_cat = data["catalog"]
    cache_mask = data["mask"]
    import numpy as np

    diff = set(cache_cat["COADD_OBJECT_ID"]) - set(no_cache_cat["COADD_OBJECT_ID"])
    print(diff)
    mask = np.fromiter(
        map(lambda x: x in diff, cache_cat["COADD_OBJECT_ID"]), dtype=bool
    )
    diff_rows = cache_cat[mask]
    print(diff_rows)
    assert len(no_cache_cat) == len(cache_cat)
    assert len(no_cache_mask) == len(cache_mask)


def test_des_box_search(dataset):
    a = dataset.box_search(DES_CENTER, radius, dtypes=["catalog", "mask"])
    cat = a["catalog"]
    mask = a["mask"]
    masked_cat = mask.mask(cat)
    assert len(cat) >= len(masked_cat)
