import json
import pickle
import re
from importlib.resources import read_binary, read_text

import numpy as np
import pandas as pd
from astropy.io import fits
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein import Region
from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.mask import Mask

try:
    import pymangle
except ImportError:
    pymangle = None
    print("Pymangle not installed, Mangle masks will not be available")

EXPORT = ["load_regions"]


def load_regions():
    data = read_binary("heinlein_des", "regions.reg")
    regions = pickle.loads(data)
    return regions


def load_config():
    data = read_text("heinlein_des", "config.json")
    config = json.loads(data)
    return config


def load_regions_from_pandas(support_location):
    tile_file = support_location / "des_tiles.csv"
    tile_data = pd.read_csv(tile_file)
    tiles = {}
    for index, row in tile_data.iterrows():
        ra_par = "RAC"
        dec_par = "DECC"
        ras = np.zeros(4)
        decs = np.zeros(4)
        for c in range(1, 5):
            ra = row[f"{ra_par}{c}"]
            dec = row[f"{dec_par}{c}"]
            ras[c - 1] = ra
            decs[c - 1] = dec

        center_point = (row["RA_CENT"], row["DEC_CENT"])
        geo = SingleSphericalPolygon.from_radec(ras, decs, center=center_point)
        reg = Region(geo, name=row["TILENAME"])
        tiles.update({row["TILENAME"]: reg})
    return tiles


class MaskHandler(Handler):
    def __init__(self, *args, **kwargs):
        kwargs.update({"type": "mask"})
        super().__init__(*args, **kwargs)
        if pymangle is not None:
            self.mangle_files = self._project.list("data/mask/mangle")["files"]
        else:
            self.mangle_files = []
        self.plane_files = self._project.list("data/mask/plane")["files"]

    def get_data(self, region_names, *args, **kwargs):
        regex = re.compile("|".join(region_names))
        mangle_matches = list(filter(lambda x: regex.match(x), self.mangle_files))
        plane_matches = list(filter(lambda x: regex.match(x), self.plane_files))

        return self._get(region_names, plane_matches, mangle_matches, *args, **kwargs)

    def _get(self, regions, plane_files, mangle_files=None, *args, **kwargs):
        output = {}
        for region in regions:
            mangle_file = list(filter(lambda x, y=region: y in x, mangle_files))
            plane_file = list(filter(lambda x, y=region: y in x, plane_files))
            bad = False
            if len(mangle_file) == 0 and pymangle is not None:
                print(f"Unable to find Mangle mask for region {region}")
                bad = True
            if len(plane_file) == 0:
                print(f"Unable to find plane file for region {region}")
                bad = True
            if bad:
                continue

            plane_path = self._project.get(f"data/mask/plane/{plane_file[0]}")
            plane_msk = fits.open(plane_path, memmap=True)
            masks = [plane_msk]

            if mangle_files:
                mangle_path = self._project.get(f"data/mask/mangle/{mangle_file[0]}")
                mangle_msk = pymangle.Mangle(mangle_path)
                masks.append(mangle_msk)

            output.update({region: Mask(masks, pixarray=True, **self._config)})
        return output

    def get_data_object(self, data, *args, **kwargs):
        masks = list(data.values())
        return masks[0].append(masks[1:])
