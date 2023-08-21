from __future__ import annotations
from ast import Param
from astropy.table import Table, vstack
import logging
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, concatenate as scc
from astropy.table import vstack

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
    catalog['coordinates'] = coords
    return coords,

def get_cartesian_points(catalog: Table):
    coords = catalog['coordinates']
    lon = coords.ra.to_value("deg")
    lat = coords.dec.to_value("deg")
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



class Catalog:

    def __init__(self, data: Table, cartesian_points = None, *args, **kwargs):
        """
        A catalog is essentially an Astropy table with some additional functionality.        
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

class Catalog_(Table):
    _config = load_config()

    def __init__(self, *args, **kwargs):
        """
        Stores catalog data. Can be used like an astropy table, but includes
        some additional functionality.
        """
        cleaned_kwargs = self.pre_setup(*args, **kwargs)
        super().__init__(*args, **cleaned_kwargs)
        self._maskable_objects = {}
        self._has_radec = False
        derivative = [m in kwargs.keys() for m in ["masked", "copy"]]
         #Checks if this has been derived from another catalog (either by masking or copying)
        #If so, we have to be careful about how we perform setup.
        if not any(derivative):
            self.setup(*args, **kwargs)
            
    def pre_setup(self, *args, **kwargs):
        """
        Checks for any inputs that might be incompatibile
        with the astropy Table and stores them for later use
        """
        self._parmap = kwargs.pop("parmap", None)
        self._maskable_objects = kwargs.pop("maskable_objects", None)
        return kwargs

    def setup(self, *args, **kwargs):
        """
        Performs setup.
        """
        if len(self) == 0:
            return
                
        else:
            for param in self._parmap:
                col = param.get_values(self)

                if param.unit is not None and col.unit is None:
                    unit = getattr(u, param.unit) 
                    col *= unit
                    self[param.col] = col

        if self._maskable_objects:
            self.__dict__.update(self._maskable_objects)
            
    def post_setup(self, parmap, maskable_objects):
        self._parmap = parmap
        self._maskable_objects = maskable_objects
        self.setup()


    def __copy__(self, *args, **kwargs):
        """
        Ensures extra objects are passed to a new table.
        """
        cp = super().__copy__()
        cp.post_setup(maskable_objects = self._maskable_objects, parmap = self._parmap)
        return cp

    def __getitem__(self, key):
        """
        Implements masking using heinlein masks, as well
        as column aliases.
        """
        if type(key) == mask.Mask:
            return key.mask(self)

        try:
            val =  super().__getitem__(key)
            return val
        except KeyError:
            column = self._parmap.get(key)
            return super().__getitem__(column)

    def __setitem__(self, item, value):
        """
        Implements setting with column aliases
        """
        try:
            column = self._parmap.get(item)
            if column is None:
                raise KeyError
            return super().__setitem__(column, value)
        except (KeyError, AttributeError):
            return super().__setitem__(item, value)
    

    @classmethod
    def from_rows(cls, rows, columns, *args, **kwargs):
        t = Table(rows=rows, names=columns)
        c = cls(t, *args, **kwargs)
        return c
    
    @classmethod
    def read(cls, *args, **kwargs):
        parameter_map = kwargs.pop("parmap", None)
        data = Table.read(*args, **kwargs)
        output =  cls(data,parmap=parameter_map)
        return output

    def concatenate(self, others: list = [], *args, **kwargs):
        """
        heinlein objects need a concatenate method, so that 
        they can be combined when doing a query.

        This implements concatenate for catalogs, ensures extra
        objects don't have to be re-created. 
        """
        good_others = list(filter(lambda x: len(x) != 0, others))
        if len(good_others) == 0:
            return self
        elif len(self) == 0:
            return good_others[0].concatenate(good_others[1:])

        data = {"parmap": self._parmap}

        maskables = [o._maskable_objects for o in good_others]
        data['maskable_objects'] = {}
        for name, obj_ in self._maskable_objects.items():

            new_obj = copy(obj_)

            other_objs = [o[name] for o in maskables]
            if name == "_skycoords":

                new_obj = scc([new_obj] + other_objs)
                data['maskable_objects'].update({'_skycoords': new_obj})

            else:
                all_others = np.vstack(other_objs)
                new_obj = np.concatenate((new_obj, all_others))
                data['maskable_objects'].update({name: new_obj})

        cats = [self]
        for o in others:
            cats.append(o)

        new_cat = vstack(cats)
        new_cat.post_setup(**data)
        return new_cat
    
    def update_coords(self, coords: SkyCoord, *args, **kwargs):
        """
        Re-defines coordinates in the catalog using passed skycoords.
        This is primarily for use in lenskappa
        """
        self['coordinates'] = coords
        self['ra'] = coords.ra
        self['dec'] = coords.dec
        lon = self['ra'].to(u.deg)
        lat = self['dec'].to(u.deg)
        self._cartesian_points = np.dstack(lonlat_to_vector(lon, lat))[0]
        self._maskable_objects.update({'_cartesian_points': self._cartesian_points})

    def add_alias(self, column_name, alias_name, *args, **kwargs):
        """
        Adds a column alias. Once the alias has been added, the column
        can be accessed with it's actual name or the alias.

        params:

        column_name: <str> The name of the column
        alias_name: <str> The alias for the column
        """
        par = CatalogParam(column_name, alias_name)
        self._parmap.update(par)

    def add_aliases(self, aliases, *args, **kwargs):
        """
        Add several aliases.

        aliases: <dict> {column_name: alias_name}
        """
        pars = [CatalogParam(k, v) for k, v in aliases.items()]
        self._parmap.update(pars)
        
 
    @property
    def coords(self):
        return self['coordinates']
    
    @property
    def points(self):
        return self._cartesian_points

    def get_passthrough_items(self, *args, **kwargs):
        items = {}
        items.update({"parmap": self._parmap})
        items = {name: value for name, value in self._maskable_objects.items()}

        return items
    
    def _new_from_slice(self, slice_, *args, **kwargs):
        """
        This is an overload of the equivalent function
        in an astropy Table which correctly handles
        the additional information created.
        """
        maskables = {name: value[slice_] for name, value in self._maskable_objects.items()}
        items = {"parmap": self._parmap, 'maskable_objects': maskables}
        new = super()._new_from_slice(slice_, *args, **kwargs)
        new.post_setup(**items)
        return new

    def get_data_from_region(self, region: BaseRegion):
        if len(self) == 0:
            return self
        if region.type == "CircularRegion":
            return self._get_items_in_circular_region(region)
        elif region.type == "PolygonRegion":
            return self._get_items_in_polygon_region(region)

    def _get_items_in_circular_region(self, region: CircularRegion):
        center = region.coordinate
        radius = region.radius
        mask = center.separation(self['coordinates']) <= radius
        return self[mask]

    def _get_items_in_polygon_region(self, region: PolygonRegion):
        raise NotImplementedError

class CatalogParam:

    def __init__(self, col_name: str, std_name: str, unit: u.Quantity = None,  *args, **kwargs):
        """
        A class for handling catalog aliases. Note, this particular class DOES NOT
        check that the data frame actually contains the column until the values are requested.

        Arguments:
        col_name <str>: Name of the column in the dataframe
        std_name <str>: Standard name of the column

        """
        self._col_name = col_name
        self._std_name = std_name
        self.unit = unit

    def get_values(self, cat, *args, **kwargs):
        try:
            return cat[self._col_name]

        except:
            logging.error("Unable to find values for paramater {} in catalog".format(self._std_name))
            raise

    @property
    def standard(self):
        return self._std_name
    @property
    def col(self):
        return self._col_name
    
class ParameterMap:

    logger = logging.getLogger("Parameters")
    def __init__(self, params = [], *args, **kwargs):
        """
        Holds all the aliases for a catalog.
        """
        self._setup_params(params)
    
    @classmethod
    def get_map(cls, map: dict):
        if not map:
            return None
        params = []
        for key, val in map.items():
            if type(val) == str:
                p = CatalogParam(val, key)
            elif type(val) == dict:
                catalog_key = val['key']
                unit = val.get("unit", None)
                p = CatalogParam(catalog_key, key, unit)
            params.append(p)
        return cls(params)
                
    def __iter__(self):
        return self._params.__iter__()

    def __next__(self):
        return self._params.__next__()

    @property
    def names(self):
        return list(self._colmap.keys())

    def __iter__(self):
        self.n = 0
        return self
    def __next__(self):
        if self.n < len(self._params):
            result = list(self._params.values())[self.n]
            self.n += 1
            return result
        else:
            raise StopIteration


    def get(self, key, *args, **kwargs):
        if key in self._colmap.keys():
            return key
        else:
            try:
                col = self._params[key].col
                return col
            except KeyError:
                return None

    def _setup_params(self, params, *args, **kwargs):
        if not params:
            return
        self._params = params
        self._validate_params()
        self._params = {p.standard: p for p in self._params}
        self._colmap = {p.col: p.standard for p in self._params.values()}

    def _validate_params(self, *args, **kwargs):
        if not all([issubclass(type(p), CatalogParam) for p in self._params]):
            self.logger.error("The parameters passed to the map were not parameter objects!")
            raise ValueError
        stds = [p.standard for p in self._params]
        if len(stds) != len(set(stds)):
            self.logger.error("Multiple parameters sere passed for the same standard name!")
            raise ValueError
        
        cols = [p.col for p in self._params]
        if len(cols) != len(set(cols)):
            logging.error("Multiple parameters were passed for the same catalog column!")
            raise ValueError
        

    def update(self, new_parameters = [], *args, **kwargs):
        if not new_parameters:
            return
        if not all( [issubclass(type(p), CatalogParam) for p in new_parameters]):
            self.logger.error("New parameters were not all of type Param")
            return
        
        for p in new_parameters:
            if p.standard in self._params.keys():
                self.logger.info(f"Updating parameter {p.standard}")
            if p.col in self._colmap.keys():
                self.logger.info(f"Updating column reference for {p.col}")
            

            self._params.update({p.standard: p})
            self._colmap.update({p.col: p.standard})
