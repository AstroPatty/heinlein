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

class BaseRegion(Protocol):

    def __init__(self, *args, **kwargs):
        pass
    def overlaps(self, *args, **kwargs):
        pass
    def center(self, *args, **kwargs):
        pass


class PolygonRegion:

    def __init__(self, points, name: str, *args, **kwargs):
        """
        Core region object. All points are assumed to be in units
        of degrees.
        """
        self._geometry = Polygon(points)
        self.name = name

    def overlaps(self, other) -> bool:
        return self._geometry.intersects(other._geometry)
    
    @property
    def center(self) -> Point:
        return self._geometry.centroid

class CircularRegion:

    def __init__(self, center: Union[SkyCoord, tuple], radius: Union[u.Quantity, float], name: str, *args, **kwargs):
        """
        Core region object. All points are assumed to be in units
        of degrees.
        """
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
