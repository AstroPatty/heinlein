from heinlein.locations import BASE_DATASET_CONFIG_DIR
from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes import mask
from pathlib import Path
import logging
from astropy.io import fits
import numpy as np
import pickle

def setup(self, *args, **kwargs):
    self._regions = load_regions()

def load_regions():
    support_location = BASE_DATASET_CONFIG_DIR/ "support"
    pickled_path = support_location / "cfht_regions.reg"
    if pickled_path.exists():
        with open(pickled_path, 'rb') as f:
            regions = pickle.load(f)
            return regions


class MaskHandler(Handler):
    def __init__(self, path: Path, config: dict, *args ,**kwargs):
        super().__init__(path, config, "mask")

    def get_data(self, regions, *args, **kwargs):
        files = [f for f in self._path.glob("*.fits") if not f.name.startswith(".")]
        names = [r.name for r in regions]
        output = {}
        super_region_names = list(set([n.split("_")[0] for n in names]))
        regions_ = {n: list(filter(lambda x: x.name.startswith(n), regions)) for n in super_region_names}
        for name in super_region_names:
            matches = list(filter(lambda x: name in x.name, files))
            if len(matches) > 1:
                logging.error(f"Error: Found more than one mask for region {name}")
                continue
            elif len(matches) == 0:
                logging.error(f"Found no masks for region {name}")
                continue

            data = fits.open(matches[0])
            out = np.empty(1, dtype="object")
            out[0] = data
            mask_obj = mask.Mask(out, pixarray=True, **self._config)
            output.update({n.name: mask_obj for n in regions_[name]})
        
        return output

    def get_data_object(self, data, *args, **kwargs):
        ids = [id(d) for d in data.values()]
        n_unique = len(set(ids))
        storage = np.empty(n_unique, dtype=object)
        found = []
        i = 0
        for value in data.values():
            if id(value) not in found:
                storage[i] = value
                found.append(id(value))
                i += 1
        return storage[0].append(storage[1:])
