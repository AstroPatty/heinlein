from __future__ import annotations
from astropy.table import Table
import logging
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, concatenate as scc
from astropy.table import vstack
from shapely.strtree import STRtree
from spherical_geometry.vector import lonlat_to_vector
from copy import copy
from typing import TYPE_CHECKING, Type
import json
from heinlein.dtypes import mask
from heinlein.locations import MAIN_CONFIG_DIR

if TYPE_CHECKING:
    from heinlein.region import BaseRegion
    from heinlein.region import CircularRegion, PolygonRegion


def load_config():
    catalog_config_location = MAIN_CONFIG_DIR / "dtypes"/"catalog.json"
    with open(catalog_config_location, "rb") as f:
        data = json.load(f)
    return data
class Catalog(Table):
    _config = load_config()

    def __init__(self, *args, **kwargs):
        """
        Stores catalog data. Can be used like an astropy table, but includes
        some additional functionality.
        """
        super().__init__(*args, **kwargs)
        self._maskable_objects = {}
        derivative = [m in kwargs.keys() for m in ["masked", "copy"]]
        #Checks if this has been derived from another catalog (either by masking or copying)
        #If so, we have to be careful about how we perform setup.
        if not any(derivative) and len(self) != 0:
            self.setup(*args, **kwargs)
        
    def setup(self, *args, **kwargs):
        """
        Performs setup.
        """
        try:
            self._parmap = kwargs['parmap']
        except KeyError:
            self._find_coords()

        try:
            self._maskable_objects = kwargs['maskable_objects']
            self.__dict__.update(self._maskable_objects)
        except KeyError:
            self._init_points()

    def __copy__(self, *args, **kwargs):
        """
        Ensures extra objects are passed to a new table.
        """
        cp = super().__copy__()
        cp.setup(maskable_object = self._maskable_objects, parmap = self._parmap)
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
            return super().__setitem__(column, value)
        except (KeyError, AttributeError):
            return super().__setitem__(item, value)
    
    @classmethod
    def from_rows(cls, rows, columns):
        t = Table(rows=rows, names=columns)
        c = cls(t)
        return c

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

        new_cat.setup(**data)

        return new_cat
    
    def update_coords(self, coords: SkyCoord, *args, **kwargs):
        """
        Re-defines coordinates in the catalog using passed skycoords.
        This is primarily for use in lenskappa
        """
        self._skycoords = coords
        self['ra'] = coords.ra
        self['dec'] = coords.dec
        lon = self['ra'].to(u.deg)
        lat = self['dec'].to(u.deg)
        self._cartesian_points = np.dstack(lonlat_to_vector(lon, lat))[0]
        self._maskable_objects.update({'_skycoords': self._skycoords, '_cartesian_points': self._cartesian_points})


    def _find_coords(self, *args, **kwargs):
        """
        Searches through the catalog to try to find
        columns that could be coordinates.

        Known column aliases can be found in
        heinlein/config/dtypes/catalog.json
        """
        columns = set(self.colnames)
        ras = set(self._config['columns']['ra'])
        dec = set(self._config['columns']['dec'])
        ra_col = columns.intersection(ras)
        dec_col = columns.intersection(dec)

        if len(ra_col) == 1 and len(dec_col) == 1:
            ra_par = CatalogParam(list(ra_col)[0], "ra")
            dec_par = CatalogParam(list(dec_col)[0], "dec")
        else:
            print(self)
            print(len(self))
            raise KeyError("Unable to find a unique RA and DEC column")

        try:
            self._parmap.update([ra_par, dec_par])
        except AttributeError:
            self._parmap = ParameterMap([ra_par, dec_par])

        try:
            self['ra'].to(u.deg)
        except u.UnitConversionError:
            self['ra'] = self['ra']*u.deg
        try:
            self['dec'].to(u.deg)
        except u.UnitConversionError:
            self['dec'] = self['dec']*u.deg

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

    def _init_points(self, *args, **kwargs):
        """
        Initializes SkyCoords and cartesian points for
        objects in the catalog. These are used to extract
        objects from particular regions.
        """
        self._skycoords = SkyCoord(self['ra'], self['dec'])
        lon = self._skycoords.ra.to_value("deg")
        lat = self._skycoords.dec.to_value("deg")
        self._cartesian_points = np.dstack(lonlat_to_vector(lon, lat))[0]
        self._maskable_objects.update({'_skycoords': self._skycoords, '_cartesian_points': self._cartesian_points})

 
    @property
    def coords(self):
        return self._skycoords
    
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
        new.setup(**items)
        return new

    def get_data_from_region(self, region: BaseRegion):
        if len(self) == 0:
            return self
        if not hasattr(self, "_cartesian_points"):
            self._find_coords()
            self._init_points()
        if region.type == "CircularRegion":
            return self._get_items_in_circular_region(region)
        elif region.type == "PolygonRegion":
            return self._get_items_in_polygon_region(region)

    def _get_items_in_circular_region(self, region: CircularRegion):
        center = region.coordinate
        radius = region.radius
        mask = center.separation(self._skycoords) <= radius
        return self[mask]

    def _get_items_in_polygon_region(self, region: PolygonRegion):
        raise NotImplementedError

class CatalogParam:

    def __init__(self, col_name: str, std_name: str,  *args, **kwargs):
        """
        A class for handling catalog aliases. Note, this particular class DOES NOT
        check that the data frame actually contains the column until the values are requested.

        Arguments:
        col_name <str>: Name of the column in the dataframe
        std_name <str>: Standard name of the column

        """
        super().__init__(*args, **kwargs)
        self._col_name = col_name
        self._std_name = std_name
    
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
            return self._params[key].col

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

