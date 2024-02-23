from __future__ import annotations

import json

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.table import Table, vstack
from spherical_geometry.vector import lonlat_to_vector

from heinlein.dtypes import dobj
from heinlein.locations import MAIN_CONFIG_DIR
from heinlein.region import BaseRegion, CircularRegion


def load_config():
    catalog_config_location = MAIN_CONFIG_DIR / "dtypes" / "catalog.json"
    with open(catalog_config_location, "rb") as f:
        data = json.load(f)
    return data


def get_coordinates(catalog: Table):
    if "coordinates" in catalog.colnames and isinstance(
        catalog["coordinates"], SkyCoord
    ):
        return catalog["coordinates"]
    coords = SkyCoord(catalog["ra"], catalog["dec"])
    return coords


def get_cartesian_points(coordinates: SkyCoord):
    lon = coordinates.ra.to_value("deg")
    lat = coordinates.dec.to_value("deg")
    cartesian_points = np.dstack(lonlat_to_vector(lon, lat))[0]
    return cartesian_points


def label_coordinates(catalog: Table, config: dict = {}):
    """
    Takes a catalog and finds the coordinate columns (ra and dec)
    returns the catalog with the coordinate columns labeled
    """
    if not config:
        config = load_config()
        columns = set(catalog.colnames)
        ras = set(config["columns"]["ra"])
        dec = set(config["columns"]["dec"])
        ra_col = columns.intersection(ras)
        dec_col = columns.intersection(dec)
        if len(ra_col) != 1 or len(dec_col) != 1:
            raise ValueError("Catalog does not have the correct columns for ra and dec")
        ra_name = list(ra_col)[0]
        dec_name = list(dec_col)[0]
        ra_unit = u.deg
        dec_unit = u.deg
    else:
        ra_name = config["columns"]["ra"]["key"]
        dec_name = config["columns"]["dec"]["key"]
        ra_unit_name = config["columns"]["ra"].get("unit", "deg")
        dec_unit_name = config["columns"]["dec"].get("unit", "deg")
        ra_unit = getattr(u, ra_unit_name)
        dec_unit = getattr(u, dec_unit_name)

    catalog.rename_columns([ra_name, dec_name], ["ra", "dec"])
    catalog._has_radec = True
    try:
        catalog["ra"].to(u.deg)
    except u.UnitConversionError:
        catalog["ra"] = catalog["ra"] * ra_unit
    try:
        catalog["dec"].to(u.deg)
    except u.UnitConversionError:
        catalog["dec"] = catalog["dec"] * dec_unit

    return catalog


def Catalog(data: Table = None, config: dict = {}, *args, **kwargs):
    """
    Produces a catalog object from an astropy table. This locates the ra and dec
    columns, creates SkyCoords, and creates a cartesian representation of the
    coordinates for more efficient filtering. Produces a :class:`CatalogObject` which
    is used internally by the DataManager. When a pieces of data is actuall requested
    this object will produce a :class:`astropy.Table` with the data from the region.

    """
    if data is None:
        data = Table()
    if len(data) == 0:
        points = np.array([])
        return CatalogObject(data, points)

    labeled_data = label_coordinates(data, config)
    catalog_coordinates = get_coordinates(labeled_data)
    cartesian_points = get_cartesian_points(catalog_coordinates)
    data["coordinates"] = catalog_coordinates
    return CatalogObject(data, cartesian_points)


class CatalogObject(dobj.HeinleinDataObject):
    def __init__(self, data: Table, points: np.ndarray):
        self._data = data
        self._points = points

    def __len__(self):
        return len(self._data)

    def get_data_from_region(self, region: BaseRegion):
        if type(region) == CircularRegion:
            separation = region.coordinate.separation(self._data["coordinates"])
            mask = separation <= region.radius
            return self._data[mask]

        return self._data

    @classmethod
    def combine(cls, objects: list[CatalogObject]):
        data = vstack([o._data for o in objects if len(o._data) > 0])
        points = np.concatenate([o._points for o in objects])
        return cls(data, points)
