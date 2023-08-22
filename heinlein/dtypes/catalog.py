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


class HeinleinDataObject(ABC):
    """
    This is a generic class that is used for storing data objects in the cache. An
    object of this type will never actually be given to the user. The data objects
    must define a `get_data_from_region` method, which will return the data from the
    region provided.
    
    """
    @abstractmethod
    def get_data_from_region(self, region: BaseRegion):
        pass

    @abstractclassmethod
    def combine(cls, objects: list[HeinleinDataObject]):
        pass


class CatalogObject(HeinleinDataObject):

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


class Catalog_:
    """
    A catalog is effectively an :class:`astropy.table.Table` with some additional 
    functionality. It will automatically locate right acension and declination
    columns and label them as such. It will the generate sky coordinate objects 
    and palce them in the `coordinates` column.

    In general, you should not create objects of this class directly.

    :param data: The data to load into the catalog
    :type data: :class:`astropy.table.Table`

    """
    def __init__(self, data: Table, cartesian_points = None, *args, **kwargs):
        """
        A catalog is effectively an :class:`astropy.table.Table` with some additional 
        functionality. It will automatically locate right acension and declination
        columns and label them as such. It will the generate sky coordinate objects 
        and palce them in the `coordinates` column.

        In general, you should not create objects of this class directly.

        """
        try:
            self._data = label_coordinates(data)
            self._has_radec = True
            coordinates = get_coordinates(self._data)
            self._data['coordinates'] = coordinates
            if cartesian_points is None:
                cartesian_points = get_cartesian_points(self._data)
            self._cartesian_points = cartesian_points

        except ValueError:
            self._data = data
            self._has_radec = False
            self._cartesian_points = None
            logging.warning("Catalog does not have ra and dec columns. Cannot perform spatial operations on this catalog")

    def __len__(self):
        return len(self._data)

    def __str__(self) -> str:
        return self._data.__str__()
    
    def __getattr__(self, __name):
        """
        This allows operations to "fall through" to the underlying table.
        astropy tables are not built for big-data analytics, so the eventual
        goal is to replace this will a polars dataframe.
        """

        return getattr(self._data, __name)
    
    def __getitem__(self, key):
        """
        Implements masking using heinlein masks, as well
        as column aliases.
        """
        if type(key) == mask.Mask:
            return key.mask(self)

        val =  self._data.__getitem__(key)
        if type(val) == Table:
            try:
                points = self._cartesian_points[val]
            except (IndexError, TypeError):
                points = None

            return Catalog(val, cartesian_points=points)
        return val

    def __setitem__(self, item, value):
        """
        Implements setting with column aliases
        """
        return self._data.__setitem__(item, value)
    
    @property
    def points(self):
        return self._cartesian_points

    @classmethod
    def new_from_mask(cls, mask: mask.Mask, *args, **kwargs):
        data = mask._data
        return cls(data, *args, **kwargs)

    @classmethod
    def concatenate(cls, cats: list[Catalog]):
        good_catalogs = list(filter(lambda x: len(x) != 0, cats))
        if len(good_catalogs) == 0:
            return cls(Table())
        elif len(good_catalogs) == 1:
            return good_catalogs[0]

        column_sets = [set(c._data.colnames) for c in good_catalogs]
        #Chcek if all the sets are the same
        if not all([c == column_sets[0] for c in column_sets[1:]]):
            raise ValueError("Cannot concatenate catalogs with different columns")
    
        new_data = vstack([c._data for c in good_catalogs])
        #If all the catalogs have the same columns, that implies that either they
        #all have coordinates, or none of them do. So we can just check the first
        #it also implies they should all have the same parameter map
        all_points = np.concatenate([c._cartesian_points for c in good_catalogs])
        return Catalog(new_data, cartesian_points=MultiPoint(all_points))

    def get_data_from_region(self, region: BaseRegion):
        if type(region) == CircularRegion:
            center = region.coordinate
            radius = region.radius
            mask = center.separation(self['coordinates']) <= radius
            return self[mask]
        raise NotImplementedError("Only circular regions are currently supported for catalogs")
