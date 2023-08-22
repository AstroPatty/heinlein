from __future__ import annotations
from ast import Param
from astropy.table import Table, vstack
import logging
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, concatenate as scc
from astropy.table import vstack
from abc import ABC, abstractmethod, abstractclassmethod
from shapely.geometry import MultiPoint

from spherical_geometry.vector import lonlat_to_vector
from copy import copy
from typing import TYPE_CHECKING, Type
import json
from heinlein.dtypes import mask
from heinlein.locations import MAIN_CONFIG_DIR


from heinlein.region import BaseRegion
from heinlein.region import CircularRegion, PolygonRegion
from heinlein.dtypes import dobj

def load_config():
    catalog_config_location = MAIN_CONFIG_DIR / "dtypes"/"catalog.json"
    with open(catalog_config_location, "rb") as f:
        data = json.load(f)
    return data


def get_coordinates(catalog: Table):
    if 'coordinates' in catalog.colnames\
        and isinstance(catalog['coordinates'], SkyCoord):
            return catalog['coordinates']
    coords = SkyCoord(catalog['ra'], catalog['dec'])
    return coords

def get_cartesian_points(coordinates: SkyCoord):
    lon = coordinates.ra.to_value("deg")
    lat = coordinates.dec.to_value("deg")
    cartesian_points = np.dstack(lonlat_to_vector(lon, lat))[0]
    return cartesian_points

def label_coordinates(catalog: Table):
    """
    Takes a catalog and finds the coordinate columns (ra and dec)
    returns the catalog with the coordinate columns labeled
    """

    config = load_config()
    columns = set(catalog.colnames)
    ras = set(config['columns']['ra'])
    dec = set(config['columns']['dec'])
    ra_col = columns.intersection(ras)
    dec_col = columns.intersection(dec)
    if len(ra_col) == 1 and len(dec_col) == 1:
        ra_name = list(ra_col)[0]
        dec_name = list(dec_col)[0]
        catalog.rename_columns([ra_name, dec_name], ["ra", "dec"])
        catalog._has_radec = True
        try:
            catalog['ra'].to(u.deg)
        except u.UnitConversionError:
            catalog['ra'] = catalog['ra']*u.deg
        try:
            catalog['dec'].to(u.deg)
        except u.UnitConversionError:
            catalog['dec'] = catalog['dec']*u.deg

    else:
        raise ValueError("Catalog does not have the correct columns for ra and dec")
    
    return catalog




class CatalogObject(dobj.HeinleinDataObject):

    def __init__(self, data: Table, points: np.ndarray):
        self._data = data
        self._points = points
    
    def __len__(self):
        return len(self._data)

    def get_data_from_region(self, region: BaseRegion):
        if type(region) == CircularRegion:
            separation = region.coordinate.separation(self._data['coordinates'])
            mask = separation <= region.radius
            return self._data[mask]

        return self._data
    
    @classmethod
    def combine(cls, objects: list[CatalogObject]):
        data = vstack([o._data for o in objects])
        points = np.concatenate([o._points for o in objects])
        return cls(data, points)



def Catalog(data: Table, *args, **kwargs):
    """
    
    
    """
    labeled_data = label_coordinates(data)
    catalog_coordinates = get_coordinates(labeled_data)
    cartesian_points = get_cartesian_points(catalog_coordinates)
    data['coordinates'] = catalog_coordinates
    return CatalogObject(data, cartesian_points)
