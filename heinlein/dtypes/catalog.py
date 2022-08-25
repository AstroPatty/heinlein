from __future__ import annotations
from astropy.table import Table
import logging
import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord, concatenate as scc
from astropy.table import vstack
from shapely.geometry import Point
from shapely.strtree import STRtree
from copy import copy
from typing import TYPE_CHECKING
import time

if TYPE_CHECKING:
    from heinlein.region import BaseRegion
    from heinlein.region import CircularRegion, PolygonRegion


class Catalog(Table):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._maskable_objects = {}
        if "masked" not in kwargs.keys() and len(self) != 0:
            self.setup(*args, **kwargs)

    def setup(self, *args, **kwargs):


        try:
            self._parmap = kwargs['parmap']
        except KeyError:
            self._find_coords()

        try:
            self._maskable_objects = kwargs['maskable_objects']
            self.__dict__.update(self._maskable_objects)
        except KeyError:
            self._init_points()

        self._init_search_tree()

    @classmethod
    def from_rows(cls, rows, columns):
        t = Table(rows=rows, names=columns)
        return cls(t)

    def concatenate(self, others: list = [], *args, **kwargs):

        if len(others) == 0:
            return self
        others = [o for o in others if o is not None]
        data = {"parmap": self._parmap}



        maskables = [o._maskable_objects for o in others]
        data['maskable_objects'] = {}
        for name, obj_ in self._maskable_objects.items():

            new_obj = copy(obj_)

            other_objs = [o[name] for o in maskables]
            if name == "_skycoords":

                new_obj = scc([new_obj] + other_objs)
                data['maskable_objects'].update({'_skycoords': new_obj})

            else:
                all_others = np.hstack(other_objs)
                new_obj = np.concatenate((new_obj, all_others))

                data['maskable_objects'].update({name: new_obj})

        cats = [self]
        for o in others:
            cats.append(o)

        new_cat = vstack(cats)

        new_cat.setup(**data)

        return new_cat


    def _find_coords(self, *args, **kwargs):
        """
        Searches through the catalog to try to find
        columns that could be coordinates.
        """
        columns = self.colnames
        if "ra" in columns and "dec" in columns:
            ra_par = CatalogParam("ra", "ra")
            dec_par = CatalogParam("dec", "dec")
        elif "RA" in columns and "DEC" in columns:
            ra_par = CatalogParam("RA", "ra")
            dec_par = CatalogParam("DEC", "dec")
        self._parmap = ParameterMap([ra_par, dec_par])
        self['ra'] = self['ra']*u.deg
        self['dec'] = self['dec']*u.deg

    def _init_points(self, *args, **kwargs):
        """
        Initializes SkyCoords and cartesian points for
        objects in the catalog. These are used to extract
        objects from particular regions.
        """
        self._skycoords = SkyCoord(self['ra'], self['dec'])
        coordinates = list(zip(self._skycoords.ra.to(u.deg).value, self._skycoords.dec.to(u.deg).value))
        self._cartesian_points = np.empty(len(coordinates), dtype=object)
        self._cartesian_points[:] = [Point(p) for p in coordinates]
        self._maskable_objects.update({'_skycoords': self._skycoords, '_cartesian_points': self._cartesian_points})

    def _init_search_tree(self, *args, **kwargs):
        points = self._cartesian_points
        self._point_dictionary = {id(p): i for i,p in enumerate(self._cartesian_points)}
        self._search_tree = STRtree(points)

    def __getitem__(self, key):
        try:
            val =  super().__getitem__(key)
            return val
        except KeyError:
            column = self._parmap.get(key)
            return super().__getitem__(column)

    def __setitem__(self, item, value):
        try:
            column = self._parmap.get(item)
            return super().__setitem__(column, value)
        except (KeyError, AttributeError):
            return super().__setitem__(item, value)

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
        import matplotlib.pyplot as plt
        items = {"parmap": self._parmap, 'maskable_objects': maskables}
        new = super()._new_from_slice(slice_, *args, **kwargs)
        new.setup(**items)
        return new

    def get_data_from_region(self, region: BaseRegion):
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
        import matplotlib.pyplot as plt 
        mask = center.separation(self._skycoords) <= radius
        return self[mask]

    def _get_items_in_polygon_region(self, region: PolygonRegion):
        raise NotImplementedError

class CatalogParam:

    def __init__(self, col_name: str, std_name: str,  *args, **kwargs):
        """
        A class for handling catalog parameters. Note, this particular class DOES NOT
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
    
class QuantParam(CatalogParam):
    """
    Class for handling parameters with numerical data.
    Can deal with logs
    Can also accept an astropy unit.
    The reason for this is that Pandas dataframes has some weird buggy
    interactions with astropy units.
    """
    def __init__(self, col_name, std_name, unit = None, is_log = False, *args, **kwargs):
        super().__init__(col_name, std_name, *args, **kwargs)
        self._is_log = False
        self._unit = unit
    
    @property
    def unit(self):
        return self._unit
        
    def get_values(self, cat, *args, **kwargs):
        vals = np.array(super().get_values(cat, *args, **kwargs))
        if self._is_log:
            vals = np.power(10, vals)
        if self._unit is not None:
            return vals*self._unit
        else:
            return vals

class ParameterMap:

    logger = logging.getLogger("Parameters")
    def __init__(self, params = [], *args, **kwargs):
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
