import itertools
from multiprocessing import allow_connection_pickling
import astropy.units as u
from astropy.coordinates import SkyCoord
from heinlein import Region
from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.catalog import Catalog, ParameterMap
from heinlein.dataset.dataset import Dataset, dataset_extension
from shapely import geometry
import numpy as np
import logging
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
                for i in range(8):
                    for j in range(8):
                        key = f"{i}_{j}_{x_i}_{y_i}"
                        reg = Region.polygon(subregion, name=key)
                        regions.append(reg)
        dataset._regions = regions

def get_region_overlaps(dataset: Dataset, query_region, *args, **kwargs):
    field = dataset.get_parameter("ms_field")
    if not field:
        print("Critical Error: Getting data with the millennium simulation requires a field to be set")
        print("Call ms.set_field(field) to set")
        return []
    field_key = f"{field[0]}_{field[1]}"
    overlaps = dataset.get_region_overlaps(query_region, bypass=True)
    overlaps = list(filter(lambda x: x.name.startswith(field_key), overlaps))
    return overlaps

@dataset_extension
def set_plane(dataset: Dataset, plane_number, *args, **kwargs):
    dataset.set_parameter("ms_plane", plane_number)

@dataset_extension
def set_field(dataset: Dataset, field: tuple, *args, **kwargs):
    if type(field) != tuple or len(field) != 2 or not all([type(a) == int for a in field]):
        print("Error: Millennium simulation fields must be a tuple with two ints")
        return
    dataset.set_parameter("ms_field", field)
    dataset.dump_all()

def get_position_from_index(x, y):
    """
    Returns an angular position (in degrees) based on a given x, y index
    Where x,y are in the range [0, 4096]. This matches with the
    gridpoints defined by the millenium simulation.
    The position returned is with reference to the center of the field,
    so negative values are possible
    """
    l_field = (4.0*u.degree) #each field is 4 deg x 4 deg
    n_pix = 4096.0
    l_pix = l_field/n_pix
    pos_x =  -2.0*u.deg + (x+0.5) * l_pix
    pos_y =  -2.0*u.deg + (y+0.5) * l_pix
    return pos_x,pos_y

def get_index_from_position(pos_x, pos_y):
        """
        Returns the index of the nearest grid point given an angular position.
        
        """
        try:
            pos_x_rad = pos_x.to(u.radian)
            pos_y_rad = pos_y.to(u.radian)
        except:
            logging.error("Need angular distances to get kappa indices!")
            raise

        l_field = (4.0*u.degree) #each field is 4 deg x 4 deg
        n_pix = 4096.0
        l_pix = l_field/n_pix

        x_pix = (pos_x + 2.0*u.deg)/l_pix - 0.5
        y_pix = (pos_y + 2.0*u.deg)/l_pix -0.5
        return int(round(x_pix.value)), int(round(y_pix.value))


@dataset_extension
def generate_grid(dataset: Dataset, radius = 120*u.arcsec, overlap = 1):
    """
        Generates a grid of locations to compute weighted number counts on.
        Here, the locations are determined by the grid points defined in the
        millenium simulation.
        Params:
        aperture: Size of the aperture to consider. Should be an astropy quantity
        overlap: If 1, adjacent tiles do not overlap (centers have spacing of
            2*aperture). If above 1, tile spacing = 2*(aperture/overlap).
        """


        #First, find the corners of the tiling region.
        #Since we don't allow tiles to overlap with the edge of the field.
    min_pos = -2.0*u.degree + radius
    max_pos = 2.0*u.degree - radius
    bl_corner = get_index_from_position(min_pos, min_pos)
    tr_corner = get_index_from_position(max_pos, max_pos)
    #Since there's rounding involved above, check to make sure the tiles don't
    #Overlap with the edge of the field.
    min_pos_x, min_pos_y = get_position_from_index(*bl_corner)
    max_pos_x, max_pos_y = get_position_from_index(*tr_corner)

    min_vals = -2.0*u.degree
    max_vals = 2.0*u.degree
    pix_distance = 4.0*u.deg/4096.0

    x_diff = min_pos_x - min_vals
    y_diff = min_pos_y - min_vals
    x_index = bl_corner[0]
    y_index = bl_corner[1]

    #Make sure we're fully within the field
    if x_diff < radius:
        x_index += 1
    if y_diff < radius:
        y_index += 1
    bl_corner = (x_index, y_index)

    x_diff = max_vals - max_pos_x
    y_diff = max_vals - max_pos_y
    x_index = tr_corner[0]
    y_index = tr_corner[1]

    #Make sure we're fully within the field.
    if x_diff < radius:
        x_index -= 1
    if y_diff < radius:
        y_index -= 1
    tr_corner = (x_index, y_index)

    min_pos_x, min_pos_y = get_position_from_index(*bl_corner)
    max_pos_x, max_pos_y = get_position_from_index(*tr_corner)

    x_pos = min_pos_x
    x_grid = []
    while x_pos < max_pos_x:
        x_grid.append(x_pos.value)
        if overlap == 'all':
            x_pos += pix_distance
        else:
            x_pos += 2* (radius/overlap)

    y_pos = min_pos_y
    y_grid = []
    while y_pos < max_pos_y:
        y_grid.append(y_pos.value)
        if overlap == 'all':
            y_pos += pix_distance
        else:
            y_pos += 2* (radius/overlap)
    y_mesh, x_mesh = np.meshgrid(x_grid, y_grid)
    x_points = x_mesh.flatten()
    y_points = y_mesh.flatten()
    return SkyCoord(x_points, y_points, unit="deg")


"""
def get_data(self, regions: list, field: tuple = None, *args, **kwargs):
    valid = list(range(0, 8))
    allowed_fields = list(itertools.product(valid, valid))
    print(field)
    print(regions)
    print(self)
    if field is None:
        raise ValueError("Millennium simulation requires a specification of the field for all data retrieval operations")
    if field not in allowed_fields:
        raise ValueError(f"Invalid field! Expected (i,j) 0 < i, j < 8 but got {field}")

    print(allowed_fields)
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
"""