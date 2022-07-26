from ast import excepthandler
from typing import Protocol, Union
import astropy.units as u
from shapely.geometry import Point, Polygon
from astropy.coordinates import SkyCoord


def Region(*args, **kwargs):
    try:
        name = kwargs['name']
    except KeyError:
        name = None
    try:
        center = kwargs['center']
        radius = kwargs['radius']
        return CircularRegion(center, radius, name)
    except:
        return PolygonRegion(*args, **kwargs)

class HeinleinCacheException(Exception):
    pass 


class BaseRegion:

    def __init__(self, *args, **kwargs):
        self._cache = {}

    def overlaps(self, *args, **kwargs):
        pass
    def center(self, *args, **kwargs):
        pass
    def cache(self, ref, dtype):
        self._cache.update({dtype: ref})
    def get_data(self, dtype):
        try:
            return self._cache[dtype]
        except KeyError:
            raise HeinleinCacheException


class PolygonRegion(BaseRegion):

    def __init__(self, points, name: str, *args, **kwargs):
        """
        Core region object. All points are assumed to be in units
        of degrees.
        """
        super().__init__()
        self._geometry = Polygon(points)
        self.name = name

    def overlaps(self, other) -> bool:
        return self._geometry.intersects(other._geometry)
    
    @property
    def center(self) -> Point:
        return self._geometry.centroid

class CircularRegion(BaseRegion):

    def __init__(self, center: Union[SkyCoord, tuple], radius: Union[u.Quantity, float], name: str, *args, **kwargs):
        """
        Core region object. All points are assumed to be in units
        of degrees.
        """
        super().__init__()
        if type(center) == SkyCoord:
            self._skypoint = center
            self._center = Point(center.ra.value, center.dec.value)
        else:
            self._center = Point(center)
            self._skypoint = SkyCoord(*center, unit="deg")
        
        if type(radius) == u.Quantity:
            self._radius = radius.to(u.degree).value
        else:
            self._radius = radius

        self._geometry = self._center.buffer(self._radius)

    def overlaps(self, other) -> bool:
        return self._geometry.intersects(other._geometry)
    
    @property
    def center(self) -> Point:
        return self._center
