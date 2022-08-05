from __future__ import annotations
from abc import abstractmethod
import logging
from typing import Any, Tuple, Union
from xml.dom.minidom import Attr
from shapely.geometry import Polygon, Point
from shapely.affinity import translate
import numpy as np
from functools import partial
import json

from heinlein.locations import MAIN_CONFIG_DIR
logger = logging.getLogger("region")
class BaseRegion:

    def __init__(self, geometry, type, *args, **kwargs):
        """
        Base region object. Placed in its own file to get around
        circular imports
        """
        self._geometry = geometry
        self._type = type
        self._validate_geometry()
        self.check_for_edges()
        self.setup()

    def setup(self, *args, **kwargs):
        self._cache = {}
        self._subregions = {}
        config_location = MAIN_CONFIG_DIR / "region.json"
        with open(config_location, "r") as f:
            self._config = json.load(f)

    def __getattr__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions
        """
        if __name in self._config['allowed_predicates']:
            return partial(self._delegate_relationship, method_name=__name)
        else:
            raise AttributeError(f"{self._type} has no attribute \'{__name}\'")
        
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
        cycle = (x_edge[0], y_edge[0])
        overlap = (x_edge[1], y_edge[1])
        if any(overlap):
            self.build_overlap_regions()
        elif any(cycle):
            self.build_cycle_regions()
        else:
            self._geometries = [self._geometry]

    @abstractmethod
    def build_cycle_regions(self, *args, **kwargs) -> None:
        """
        Shapely is a 2D geometry package, meaning it doesnt understand
        spherical geometry. This function handles a region that goes over
        the longitude/latitude line. 
        """
        pass
    
    def _validate_geometry(self, *args, **kwargs):
        x_min, y_min, x_max, y_max = self._geometry.bounds
        x_bounds = np.array([x_min, x_max])
        y_bounds = np.array([y_min, y_max])
        if np.all(x_bounds > 360):
            x_shift = -360 * (x_bounds[0] // 360)
        elif np.all(x_bounds < 0):
            x_shift = - 360*(x_bounds[1] // 360)
        else:
            x_shift = 0

        if np.all(y_bounds > 90):
            y_shift = -90 * (y_bounds[0] // 90)
        elif np.all(y_bounds < -90):
            y_shift = 90 + 90*(y_bounds[1] // 90)
        else:
            y_shift = 0
        geo = translate(self._geometry, x_shift, y_shift)
        self._geometry = geo

    def build_overlap_regions(self, *args, **kwargs):
        """
        This function handles cases when the region is at least partially out of bounds
        """
        x_min, y_min, x_max, y_max = self._geometry.bounds
        if x_min < 0:
            x_geometries = [self._geometry, translate(self._geometry, 360)]
        elif x_max > 360:
            x_geometries = [self._geometry, translate(self._geometry, -360)]
        else:
            x_geometries = [self._geometry]
        
        if y_min < -90:
            y_geometries = [translate(g, 0, 90) for g in x_geometries]
        elif y_max > 90:
            y_geometries = [translate(g, 0, -90) for g in x_geometries]
        else:
            y_geometries = []
        
        self._geometries = x_geometries + y_geometries




    @staticmethod
    def check_x_edge(minx: float, maxx: float) -> bool:
        dx = maxx - minx

        maxx_r = (maxx + 90) % 360
        minx_r = (minx + 90) % 360

        dx_r = maxx_r - minx_r
        cycle = (dx_r < 0) and (abs(dx_r) < abs(dx))
        overlap = maxx > 360 or minx < 0
        return (cycle, overlap)


    @staticmethod
    def chcek_y_edge(miny: float, maxy: float) -> bool:
        dy = maxy - miny

        maxy_r = (maxy - 45) % 90
        miny_r = (miny - 45) % 90

        dy_r = maxy_r - miny_r
        cycle = (dy_r < 0) and (abs(dy_r) < abs(dy))
        overlap = miny < -90 or maxy > 90
        return (cycle, overlap)
