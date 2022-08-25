from ast import Mult
from functools import reduce
from gettext import Catalog
from typing import Any, Union
import astropy.units as u
from shapely.geometry import Point, Polygon, box, MultiPolygon
from astropy.coordinates import SkyCoord
import numpy as np
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.region.base import BaseRegion

def Region(region: Union[SingleSphericalPolygon, dict] = None, *args, **kwargs) -> BaseRegion:
    """
    Factory function for building regions.
    """


    if type(region) == dict:
        return build_compound_region(region, *args, **kwargs)
    try:
        name = kwargs['name']
    except KeyError:
        name = None

    if 'center' in kwargs.keys():
        center = kwargs['center']
        radius = kwargs['radius']
        return CircularRegion(center, radius, name)
    return PolygonRegion(region, name)

def build_compound_region(regions: dict, *args, **kwargs) -> BaseRegion:
    first = list(regions.values())[0]
    second = list(regions.values())[1]
    a = first.union(second)
    full_region = reduce(lambda first, second: first.union(second), regions.values())
    region_obj = Region(points = b.boundary.coords)
    region_obj.add_subregions(regions)
    return region_obj
    
class PolygonRegion(BaseRegion):

    def __init__(self, polygon: SingleSphericalPolygon, name: str, *args, **kwargs):
        """
        Basic general-shape region object
        """
        super().__init__(polygon, "PolygonRegion", name)

    @property
    def center(self) -> Point:
        return self._flat_geometry.centroid
class CircularRegion(BaseRegion):

    def __init__(self, center: Union[SkyCoord, tuple], radius: Union[u.Quantity, float], name: str, *args, **kwargs) -> None:
        """
        Circular region
        Accepts point-radius for initialization.
        Shapely does not techincally have a "spherical regions" object
        """
        
        if type(center) == SkyCoord:
            self._skypoint = center
            self._center = Point(center.ra.value, center.dec.value)
        else:
            self._center = center
            self._skypoint = SkyCoord(*center, unit="deg")
        
        if type(radius) == u.Quantity:
            self._radius = radius.to(u.degree)
        else: #assume deg
            self._radius = radius*u.deg

        geometry = SingleSphericalPolygon.from_cone(self._center[0], self._center[1], self._radius.to(u.deg).value, *args, **kwargs)
        low_res_geometry = SingleSphericalPolygon.from_cone(self._center[0], self._center[1], self._radius.to(u.deg).value, steps = 4)
        super().__init__(geometry, "CircularRegion", name, *args, **kwargs)
        self.low_res_geometry = low_res_geometry

    @property
    def center(self) -> Point:
        return self._center

    @property
    def coordinate(self) -> SkyCoord:
        return self._skypoint

    @property
    def radius(self) -> u.quantity:
        return self._radius
    