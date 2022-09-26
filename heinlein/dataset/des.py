from heinlein import Region
from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.mask import Mask
from heinlein.locations import BASE_DATASET_CONFIG_DIR
import numpy as np
import re
from pathlib import Path
import pandas as pd
from spherical_geometry.polygon import SingleSphericalPolygon
import pickle
import pymangle
from astropy.io import fits

EXPORT = ["load_regions"]

def setup(self, *args, **kwargs):
    self._regions = list(load_regions().values())

def load_regions():
    support_location = BASE_DATASET_CONFIG_DIR/ "support"
    pickled_path = support_location / "des_tiles.reg"
    if pickled_path.exists():
        with open(pickled_path, 'rb') as f:
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
        corners = []
        ras = np.zeros(4)
        decs = np.zeros(4)
        for c in range(1, 5):
            ra = row[f"{ra_par}{c}"]
            dec = row[f"{dec_par}{c}"]
            ras[c-1] = ra
            decs[c-1] = dec

        center_point = (row['RA_CENT'], row['DEC_CENT'])
        geo = SingleSphericalPolygon.from_radec(ras, decs, center=center_point)
        reg = Region(geo, name=row['TILENAME'])
        tiles.update({row['TILENAME']: reg})
    return tiles    


class MaskHandler(Handler):
    def __init__(self, *args, **kwargs):
        kwargs.update({"type": "mask"})
        super().__init__(*args, **kwargs)
        self.mangle_files = [f for f in (self._path / "mangle").glob("*.pol") if not f.name.startswith(".")]
        self.plane_files = [f for f in (self._path / "plane").glob("*.fits") if not f.name.startswith(".")]
    
    def get_data(self, regions, *args, **kwargs):
        names = [r.name for r in regions]
        nreg = len(names)
        regex = re.compile("|".join(names))
        mangle_matches = list(filter(lambda x, y=regex: regex.match(x.name), self.mangle_files))
        plane_matches = list(filter(lambda x, y=regex: regex.match(x.name), self.plane_files))
        return self._get(names, mangle_matches, plane_matches, *args, **kwargs)

    def _get(self, regions, mangle_files, plane_files, *args, **kwargs):
        output = {}
        for region in regions:
            mangle_file = list(filter(lambda x, y=region: y in x.name,mangle_files ))
            plane_file = list(filter(lambda x, y=region: y in x.name,plane_files ))
            bad = False
            if len(mangle_file) == 0:
                print(f"Unable to find Mangle mask for region {region}")
                bad = True
            if len(plane_file) == 0:
                print(f"Unable to find plane file for region {region}")
                bad = True
            if bad:
                continue

            mangle_msk = pymangle.Mangle(str(mangle_file[0]))
            plane_msk = fits.open(plane_file[0], memmap=True)
            output.update({region: Mask([mangle_msk, plane_msk], pixarray=True, **self._config)})
        return output
    
    def get_data_object(self, data, *args, **kwargs):
        masks = list(data.values())
        return masks[0].append(masks[1:])
