import json
import logging
import pickle
from importlib.resources import files
from pathlib import Path

import numpy as np
from astropy.io import fits

from heinlein.dtypes import mask
from heinlein.dtypes.handlers.handler import Handler


def load_regions():
    resources = files("heinlein_cfht")
    with open(resources / "regions.reg", "rb") as f:
        regions = pickle.load(f)
    return regions


def load_config():
    resources = files("heinlein_cfht")
    with open(resources / "config.json") as f:
        config = json.load(f)
    return config


class MaskHandler(Handler):
    def __init__(self, path: Path, config: dict, *args, **kwargs):
        super().__init__(path, config, "mask")
        self.known_files = [f for f in self._path.glob("*") if f.is_file()]

    def get_data(self, regions, *args, **kwargs):
        output = {}
        super_region_names = list(set([n.split("_")[0] for n in regions]))
        regions_ = {
            n: list(filter(lambda x: x.startswith(n), regions))
            for n in super_region_names
        }
        for name in super_region_names:
            matches = list(filter(lambda x: name in x.name, self.known_files))
            if len(matches) > 1:
                logging.error(f"Error: Found more than one mask for region {name}")
                continue
            elif len(matches) == 0:
                logging.error(f"Found no masks for region {name}")
                continue

            path = matches[0]
            data = fits.open(path)
            out = np.empty(1, dtype="object")
            out[0] = data
            mask_obj = mask.Mask(out, pixarray=True, **self._config)
            output.update({n: mask_obj for n in regions_[name]})
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
