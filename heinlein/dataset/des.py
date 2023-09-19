import pickle
import re

import numpy as np
import pandas as pd
import pymangle
from astropy.io import fits
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein import Region
from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.mask import Mask
from heinlein.locations import BASE_DATASET_CONFIG_DIR

EXPORT = ["load_regions"]


def setup(self, *args, **kwargs):
    self._regions = list(load_regions().values())


def load_regions():
    support_location = BASE_DATASET_CONFIG_DIR / "support"
    pickled_path = support_location / "des_tiles.reg"
    if pickled_path.exists():
        with open(pickled_path, "rb") as f:
            regions = pickle.load(f)
    else:
        regions = load_regions_from_pandas(support_location)
    return regions


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
        self.mangle_files = self._project.list("data/mask/mangle")["files"]
        self.plane_files = self._project.list("data/mask/plane")["files"]

    def get_data(self, region_names, *args, **kwargs):
        regex = re.compile("|".join(region_names))
        mangle_matches = list(filter(lambda x: regex.match(x), self.mangle_files))
        plane_matches = list(filter(lambda x: regex.match(x), self.plane_files))

        return self._get(region_names, mangle_matches, plane_matches, *args, **kwargs)

    def _get(self, regions, mangle_files, plane_files, *args, **kwargs):
        output = {}
        for region in regions:
            mangle_file = list(filter(lambda x, y=region: y in x, mangle_files))
            plane_file = list(filter(lambda x, y=region: y in x, plane_files))
            bad = False
            if len(mangle_file) == 0:
                print(f"Unable to find Mangle mask for region {region}")
                bad = True
            if len(plane_file) == 0:
                print(f"Unable to find plane file for region {region}")
                bad = True
            if bad:
                continue

            mangle_path = self._project.get(f"data/mask/mangle/{mangle_file[0]}")
            plane_path = self._project.get(f"data/mask/plane/{plane_file[0]}")
            mangle_msk = pymangle.Mangle(str(mangle_path))
            plane_msk = fits.open(plane_path, memmap=True)
            output.update(
                {region: Mask([mangle_msk, plane_msk], pixarray=True, **self._config)}
            )
        return output

    def get_data_object(self, data, *args, **kwargs):
        masks = list(data.values())
        return masks[0].append(masks[1:])
