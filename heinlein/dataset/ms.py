import itertools
import astropy.units as u
from heinlein import Region
from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.catalog import Catalog, ParameterMap
from shapely import geometry
import pandas as pd

def setup(dataset, *args, **kwargs):
        width = (4.0*u.degree).to(u.radian).value
        region = geometry.box(0, 0, width, width) #in degrees
        region = Region.polygon(region.exterior.coords)
        width = (1.0*u.degree).value
        min = (-1.5*u.degree).value
        #Locations in the MS are given in radians for reasons unknown.
        regions = []
        for x_i in range(4):
            for y_i in range(4):
                x_center = min + x_i*width
                y_center = min + y_i*width
                x_min = x_center - width/2
                y_min = y_center - width/2
                x_max = x_center + width/2
                y_max = y_center + width/2
                subregion = geometry.box(x_min, y_min, x_max, y_max)
                key = "{}_{}".format(str(x_i), str(y_i))
                for i in range(7):
                    for j in range(7):
                        key = f"{i}_{j}_{x_i}_{y_i}"
                        reg = Region.polygon(subregion, name=key)
                        regions.append(reg)
        dataset._regions = regions

def _get_region_overlaps(self, query_region, *args, **kwargs):
    field = kwargs["field"]
    field_key = f"{field[0]}_{field[1]}"
    overlaps = self._get_region_overlaps(query_region, bypass=True)
    overlaps = list(filter(lambda x: x.name.startswith(field_key), overlaps))
    return overlaps


class CatalogHandler(Handler):

    def __init__(self, *args, **kwargs):
        kwargs.update({"type": "catalog"})
        r_ = list(range(8))
        self.allowed_fields = list(itertools.product(r_, r_))
        super().__init__(*args, **kwargs)

        self._map = ParameterMap.get_map(self._config)

    def get_data(self, regions: list, field: tuple = None, *args, **kwargs):
        if field is None:
            raise ValueError("Millennium simulation requires a specification of the field for all data retrieval operations")
        if field not in self.allowed_fields:
            raise ValueError(f"Invalid field! Expected (i,j) 0 < i, j < 8 but got {field}")
        regnames = [r.name for r in regions]
        basename = "GGL_los_8_{}_N_4096_ang_4_SA_galaxies_on_plane_27_to_63.images.txt"
        files = [basename.format(r) for r in regnames]
        all_files = [f.name for f in self._path.glob("*.txt") if not f.name.startswith(".")]
        found = [f in all_files for f in files]
        output = {}
        if not all(found):
            missing = [rn for i, rn in enumerate(regnames) if not found[i]]
            raise FileNotFoundError(f"Missing files for fields {missing}")
        for index, name in enumerate(regnames):
            path = self._path / files[index]
            data = Catalog.read(path, format="ascii", parmap = self._map)
            output.update({name: data})
        
        return output