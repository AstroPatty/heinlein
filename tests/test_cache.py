from pathlib import Path

import pytest
from astropy.io import fits

from heinlein.dtypes.mask import Mask
from heinlein.manager.cache import clear_cache, get_cache

DATA_PATH = Path("/home/data")
DES_MASK_PATH = DATA_PATH / "des" / "mask" / "plane"


@pytest.fixture(scope="module")
def cache():
    return get_cache("des", max_size=6e8)


@pytest.fixture(scope="module")
def masks():
    mask_files = DES_MASK_PATH.glob("*.fits")
    mask_data = {f.stem: fits.open(f) for f in mask_files}
    mask_objects = {k: Mask([v], mask_key=1) for k, v in mask_data.items()}

    return mask_objects


def test_too_large(cache, masks):
    data = {"mask": masks}

    with pytest.raises(MemoryError):
        cache.add(data)


def test_replacement(cache, masks):
    keys = list(masks.keys())
    mask1 = {"mask": {keys[0]: masks[keys[0]]}}
    mask2 = {"mask": {keys[1]: masks[keys[1]]}}
    cache.add(mask1)
    cache.add(mask2)
    with pytest.raises(KeyError):
        cache.get(keys[0], "mask")


def test_get(cache, masks):
    keys = list(masks.keys())
    mask1 = {"mask": {keys[0]: masks[keys[0]]}}
    cache.add(mask1)
    data = cache.get(keys[0], "mask")
    assert data["mask"] == masks[keys[0]]


def test_clear(cache, masks):
    keys = list(masks.keys())
    mask1 = {"mask": {keys[1]: masks[keys[1]]}}
    cache.add(mask1)
    clear_cache("des")

    with pytest.raises(KeyError):
        cache.get(keys[0], "mask")
    assert cache.size == 0 and not cache.sizes and not cache.cache
