from heinlein import Region
from heinlein.locations import BASE_DATASET_CONFIG_DIR
import numpy as np

from pathlib import Path
import pandas as pd
from spherical_geometry.polygon import SingleSphericalPolygon
import pickle

EXPORT = ["load_regions"]

def setup(self, *args, **kwargs):
    self._regions = list(load_regions().values())

def load_regions():
    support_location = BASE_DATASET_CONFIG_DIR/ "support"
    pickled_path = support_location / "des_tiles.reg"
    print(pickled_path)
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



