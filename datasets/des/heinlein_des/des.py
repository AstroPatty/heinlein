import json
import pickle
import re
from importlib.resources import files
from pathlib import Path

from astropy.io import fits

from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.mask import Mask

try:
    import pymangle
except ImportError:
    pymangle = None
    print("Pymangle not installed, Mangle masks will not be available")

EXPORT = ["load_regions"]


def load_regions():
    resources = files("heinlein_des")
    with open(resources / "regions.reg", "rb") as f:
        regions = pickle.load(f)
    return regions


def load_config():
    resources = files("heinlein_des")
    with open(resources / "config.json") as f:
        config = json.load(f)
    return config


class MaskHandler(Handler):
    def __init__(self, path: Path, *args, **kwargs):
        kwargs.update({"type": "mask"})
        super().__init__(path, *args, **kwargs)
        if pymangle is not None:
            self.mangle_files = [f for f in path.glob("mangle/*") if f.is_file()]
        else:
            self.mangle_files = []
        self.plane_files = [f for f in path.glob("plane/*") if f.is_file()]

    def get_data(self, region_names, *args, **kwargs):
        regex = re.compile("|".join(region_names))
        mangle_matches = list(filter(lambda x: regex.match(x.name), self.mangle_files))
        plane_matches = list(filter(lambda x: regex.match(x.name), self.plane_files))

        return self._get(region_names, plane_matches, mangle_matches, *args, **kwargs)

    def _get(self, regions, plane_files, mangle_files=None, *args, **kwargs):
        output = {}
        for region in regions:
            mangle_file = list(filter(lambda x, y=region: y in x.name, mangle_files))
            plane_file = list(filter(lambda x, y=region: y in x.name, plane_files))
            bad = False
            if len(mangle_file) == 0 and pymangle is not None:
                print(f"Unable to find Mangle mask for region {region}")
                bad = True
            if len(plane_file) == 0:
                print(f"Unable to find plane file for region {region}")
                bad = True
            if bad:
                continue

            plane_path = plane_file[0]
            plane_msk = fits.open(plane_path, memmap=True)
            masks = [plane_msk]

            if mangle_files:
                mangle_path = mangle_file[0]
                mangle_msk = pymangle.Mangle(str(mangle_path))
                masks.append(mangle_msk)

            output.update({region: Mask(masks, pixarray=True, **self._config)})
        return output

    def get_data_object(self, data, *args, **kwargs):
        masks = list(data.values())
        return masks[0].append(masks[1:])
