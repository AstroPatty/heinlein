from heinlein import Region
import numpy as np

from pathlib import Path
import pandas as pd

EXPORT = ["read_regions"]

def setup(self, *args, **kwargs):
    self._regions = load_regions()

def load_regions():
    support_location = Path(__file__).parents[0] / "configs" / "support"
    regions = load_regions_from_pandas(support_location)
    return regions
    

def load_regions_from_pandas(support_location):
    tile_file = support_location / "des_tiles.csv"
    tile_data = pd.read_csv(tile_file)
    tiles = np.empty(len(tile_data), dtype = object)
    for index, row in tile_data.iterrows():
        ra_par = "RAC"
        dec_par = "DECC"
        corners = []
        for c in range(1, 5):
            ra = row[f"{ra_par}{c}"]
            dec = row[f"{dec_par}{c}"]
            corners.append((ra, dec))
        reg = Region(corners, name=row['TILENAME'])
        tiles[index] = reg

    return tiles    



