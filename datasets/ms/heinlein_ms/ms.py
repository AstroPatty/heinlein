import json
import logging
from importlib.resources import read_text

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from shapely import geometry

from heinlein import Region
from heinlein.dataset.dataset import Dataset, dataset_extension


def load_config():
    data = read_text("heinlein_ms", "config.json")
    config = json.loads(data)
    return config


def load_regions():
    full_width = (4.0 * u.degree).value
    width = (1.0 * u.degree).value
    min = (-1.5 * u.degree).value
    # Locations in the MS are given in radians for reasons unknown.
    regions = {}
    for i in range(8):
        for j in range(8):
            for x_i in range(4):
                for y_i in range(4):
                    x_center = full_width * i + min + x_i * width
                    y_center = full_width * j + min + y_i * width
                    x_min = x_center - width / 2
                    y_min = y_center - width / 2
                    x_max = x_center + width / 2
                    y_max = y_center + width / 2
                    subregion = geometry.box(x_min, y_min, x_max, y_max)
                    key = "{}_{}".format(str(x_i), str(y_i))
                    key = f"{i}_{j}_{x_i}_{y_i}"
                    reg = Region.polygon(subregion, name=key)
                    regions.update({key: reg})
    return regions


def get_overlapping_regions(dataset: Dataset, query_region, *args, **kwargs):
    field = dataset.get_parameter("ms_field")
    if not field:
        print(
            "Critical Error: Getting data with the millennium simulation "
            "requires a field to be set"
        )
        print("Call ms.set_field(field) to set")
        return []
    # move the query region to the correct field
    overlap_region = query_region.translate(
        field[0] * 4 * u.degree, field[1] * 4 * u.degree
    )

    overlaps = dataset.footprint.get_overlapping_regions(overlap_region)
    return overlaps


def _get_many_region_overlaps(dataset: Dataset, others: list, *args, **kwargs):
    field = dataset.get_parameter("ms_field")
    field_key = f"{field[0]}_{field[1]}"

    region_overlaps = [dataset._geo_tree.query(other.geometry) for other in others]
    overlaps = [[dataset._regions[i] for i in overlaps] for overlaps in region_overlaps]
    overlaps = [
        [o for o in overlap if o.intersects(others[i])]
        for i, overlap in enumerate(overlaps)
    ]
    overlaps = [
        list(filter(lambda x: x.name.startswith(field_key), o)) for o in overlaps
    ]
    return overlaps


@dataset_extension
def set_plane(dataset: Dataset, plane_number, *args, **kwargs):
    dataset.set_parameter("ms_plane", plane_number)


@dataset_extension
def set_field(dataset: Dataset, field: tuple, *args, **kwargs):
    if (
        type(field) != tuple
        or len(field) != 2
        or not all([isinstance(a, int) for a in field])
    ):
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
    l_field = 4.0 * u.degree  # each field is 4 deg x 4 deg
    n_pix = 4096.0
    l_pix = l_field / n_pix
    pos_x = -2.0 * u.deg + (x + 0.5) * l_pix
    pos_y = -2.0 * u.deg + (y + 0.5) * l_pix
    return pos_x, pos_y


def get_index_from_position(pos_x, pos_y):
    """
    Returns the index of the nearest grid point given an angular position.

    """
    try:
        pos_x.to(u.radian)
        pos_y.to(u.radian)
    except:
        logging.error("Need angular distances to get kappa indices!")
        raise

    l_field = 4.0 * u.degree  # each field is 4 deg x 4 deg
    n_pix = 4096.0
    l_pix = l_field / n_pix

    x_pix = (pos_x + 2.0 * u.deg) / l_pix - 0.5
    y_pix = (pos_y + 2.0 * u.deg) / l_pix - 0.5
    return int(round(x_pix.value)), int(round(y_pix.value))


@dataset_extension
def generate_grid(dataset: Dataset, radius=120 * u.arcsec, overlap=1):
    """
    Generates a grid of locations to compute weighted number counts on.
    Here, the locations are determined by the grid points defined in the
    millenium simulation.
    Params:
    aperture: Size of the aperture to consider. Should be an astropy quantity
    overlap: If 1, adjacent tiles do not overlap (centers have spacing of
        2*aperture). If above 1, tile spacing = 2*(aperture/overlap).
    """

    # First, find the corners of the tiling region.
    # Since we don't allow tiles to overlap with the edge of the field.
    min_pos = -2.0 * u.degree + radius
    max_pos = 2.0 * u.degree - radius
    bl_corner = get_index_from_position(min_pos, min_pos)
    tr_corner = get_index_from_position(max_pos, max_pos)
    # Since there's rounding involved above, check to make sure the tiles don't
    # Overlap with the edge of the field.
    min_pos_x, min_pos_y = get_position_from_index(*bl_corner)
    max_pos_x, max_pos_y = get_position_from_index(*tr_corner)

    min_vals = -2.0 * u.degree
    max_vals = 2.0 * u.degree
    pix_distance = 4.0 * u.deg / 4096.0

    x_diff = min_pos_x - min_vals
    y_diff = min_pos_y - min_vals
    x_index = bl_corner[0]
    y_index = bl_corner[1]

    # Make sure we're fully within the field
    if x_diff < radius:
        x_index += 1
    if y_diff < radius:
        y_index += 1
    bl_corner = (x_index, y_index)

    x_diff = max_vals - max_pos_x
    y_diff = max_vals - max_pos_y
    x_index = tr_corner[0]
    y_index = tr_corner[1]

    # Make sure we're fully within the field.
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
        if overlap == "all":
            x_pos += pix_distance
        else:
            x_pos += 2 * (radius / overlap)

    y_pos = min_pos_y
    y_grid = []
    while y_pos < max_pos_y:
        y_grid.append(y_pos.value)
        if overlap == "all":
            y_pos += pix_distance
        else:
            y_pos += 2 * (radius / overlap)
    y_mesh, x_mesh = np.meshgrid(x_grid, y_grid)
    x_points = x_mesh.flatten()
    y_points = y_mesh.flatten()
    return SkyCoord(x_points, y_points, unit="deg")
