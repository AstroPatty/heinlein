from __future__ import annotations
from abc import abstractmethod
import logging
from typing import Any, Tuple, Union
from shapely.geometry import Polygon, Point
import numpy as np
from functools import partial
import inspect

logger = logging.getLogger("region")
class BaseRegion:

    def __init__(self, geometry, type, *args, **kwargs):
        """
        Base region object. Placed in its own file to get around
        circular imports
        """
        self._geometry = geometry
        self._type = type
        self.validate_geometry(self._geometry)
        self._cache = {}
        self.check_for_edges()
        self._subregions = {}

    def __getattr__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions
        """
        try:
            return partial(self._delegate_relationship, method_name=__name)
        except AttributeError:
            raise AttributeError(f"{type(self)} has no attribute \'{__name}")
        

    def _delegate_relationship(self, other: BaseRegion, method_name: str, *args, **kwargs) -> Any:
        for geo in self.geometry:
            for other_geo in other.geometry:
                f = getattr(geo, method_name)
                if f(other_geo, *args, **kwargs):
                    return True
        return False

    def add_subregion(self, name: str, subregion: BaseRegion, overwrite=False) -> None:
        """
        Adds a subregion to a region. These can be used to more finely filter a dataset,
        if necessary. The subregion must be entirely contained within the original region.

        Paramaters:
        name <str>: A name for the subregion
        subregion <heinlein.BaseRegion>: A region object
        
        """
        if not self.contains(subregion):
            logger.error("A subregion must be entirely contained within its superregion!")
            return False
        if name in self._subregions.keys() and not overwrite:
            logger.error(f"Region already has a subregion named {name}. "\
                        "Set ovewrite = True to silence this warning")
            return False
        self._subregions.update({name: subregion})
        return True

    @property
    def geometry(self, *args, **kwargs) -> list:
        return self._geometries

    @property
    def type(self) -> str:
        return self._type

    def center(self, *args, **kwargs):
        pass

    def cache(self, ref: Any, dtype: str) -> None:
        self._cache.update({dtype: ref})

    def get_data(self, handlers: dict, paths: dict, data: dict) -> None:
        for type, handler in handlers.items():
            try:
                d = self._cache[type]
            except KeyError:
                d = handler(paths[type], self)
                self._cache.update({type: d})
            data[type].append(d)
    
    def check_for_edges(self, *args, **kwargs) -> None:
        """
        Shapely is a 2D geometry package, meaning it doesn't
        understand that RA 359.9 is right next to RA 0.1. This
        function checks if the region falls near that boundary
        (or the equivalent for DEC)
        """

        bounds = self._geometry.bounds
        x_min, y_min, x_max, y_max = bounds

        x_edge = BaseRegion.check_x_edge(x_min, x_max)
        y_edge = BaseRegion.chcek_y_edge(y_min, y_max)
        self._edge_overlap = (x_edge, y_edge)
        if any(self._edge_overlap):
            self.build_wrapped_regions()
        else:
            self._geometries = [self._geometry]

    @abstractmethod
    def build_wrapped_regions(self, *args, **kwargs) -> None:
        """
        Shapely is a 2D geometry package, meaning it doesnt understand
        spherical geometry. This function handles a region that goes over
        the longitude/latitude line.
        """
        pass


    @staticmethod
    def check_x_edge(minx: float, maxx: float) -> bool:
        dx = maxx - minx

        maxx_r = (maxx + 90) % 360
        minx_r = (minx + 90) % 360

        dx_r = maxx_r - minx_r
        return (dx_r < 0) and (abs(dx_r) < abs(dx))


    @staticmethod
    def chcek_y_edge(minx: float, maxx: float) -> bool:
        dx = maxx - minx

        maxx_r = (maxx - 45) % 360
        minx_r = (minx - 45) % 360

        dx_r = maxx_r - minx_r

        return (dx_r < 0) and (abs(dx_r) < abs(dx))

    @staticmethod
    def validate_geometry(geo: Union[Point, Polygon]) -> bool:
        """
        Regions should always be provided as RA and  IN DEGREES
        This function checks to make sure these values make sense
        """
        if type(geo) == Polygon:
            points = geo.exterior.coords
        else:
            points = [geo.centroid]

        def check(coord: Tuple):
            ra = coord[0]
            dec = coord[1]
            ra_check = (ra > 360) or (ra < 0)
            dec_check = abs(dec) > 90
            return ra_check or dec_check
            
        if any([check(p) for p in points]):
            logger.warning("Warning: Region objects expect RAs and Decs but got points outside the bounds!")
        
