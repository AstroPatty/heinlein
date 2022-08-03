from typing import Any, Union
import astropy.units as u
from shapely.geometry import Point, Polygon
from astropy.coordinates import SkyCoord

from heinlein.dtypes import get_handler
from heinlein.region.base import BaseRegion

def Region(*args, **kwargs) -> BaseRegion:
    """
    Factory function for building regions.
    """
    try:
        name = kwargs['name']
    except KeyError:
        kwargs.update({"name": "None"})
    try:
        center = kwargs['center']
        radius = kwargs['radius']
        return CircularRegion(type="CircularRegion", *args, **kwargs)
    except KeyError:
        kwargs.update({"type": "PolygonRegion"})
        return PolygonRegion(*args, **kwargs)



class PolygonRegion(BaseRegion):

    def __init__(self, points, name: str, *args, **kwargs):
        """
        Basic general-shape region object
        """
        input_points = [Point(p) for p in points]
        geometry = Polygon(input_points)
        super().__init__(geometry, *args, **kwargs)
        self.name = name
    
    @property
    def center(self) -> Point:
        return self._geometry.centroid

    def build_wrapped_regions(self, *args, **kwargs) -> None:
        
        points = self._geometry.exterior.xy
        if self._edge_overlap[0]:
            x_vals = points[0]
            shift_right = [x if (x > 180) else (x + 360) for x in x_vals]    
            shift_left = [x if (x < 180) else (x - 360) for x in x_vals ]
            x_coords = [shift_left, shift_right]
        else:
            x_coords = [points[0]]

        if self._edge_overlap[1]:
            y_vals = points[1]
            shift_right = [y if (y > 90) else (y + 180) for y in y_vals]    
            shift_left = [y if (y < 90) else (y - 189) for y in y_vals ]
            y_coords = [shift_left, shift_right]
        else:
            y_coords = [points[1]]

        geometry = []

        for x_ in x_coords:
            for y_ in y_coords:
                points = list(zip(x_, y_))
                geometry.append(Polygon(points))
        self._geometries = geometry


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
            self._center = Point(center)
            self._skypoint = SkyCoord(*center, unit="deg")
        
        if type(radius) == u.Quantity:
            self._radius = radius.to(u.degree)
        else: #assume deg
            self._radius = radius*u.deg
        geometry = self._center.buffer(self._radius.value)
        super().__init__(geometry, *args, **kwargs)

    def build_wrapped_regions(self, *args, **kwargs) -> None:
        x_coord, y_coord = self._center.xy
        if self._edge_overlap[0]:
            shift_right = [x if (x > 180) else (x + 360) for x in x_coord]    
            shift_left = [x if (x < 180) else (x - 360) for x in x_coord]
            x_coords = [shift_left, shift_right]
        else:
            x_coords = x_coord

        if self._edge_overlap[1]:
            shift_right = [y if (y > 90) else (y + 180) for y in y_coord]    
            shift_left = [y if (y < 90) else (y - 189) for y in y_coord]
            y_coords = [shift_left, shift_right]
        else:
            y_coords = y_coord

        geometry = []
        for x_ in x_coords:
            for y_ in y_coords:
                points = list(zip(x_, y_))
                geometry.append(Point(points).buffer(self._raidus))
        self._geometries = geometry
    
    def contains(self, other):
        try:
            coords = other.coords
        except AttributeError:
            raise NotImplementedError
        
        return self._skypoint.separation(coords) <= self._radius


    @property
    def center(self) -> Point:
        return self._center

    @property
    def coordinate(self) -> SkyCoord:
        return self._skypoint

    @property
    def radius(self) -> u.quantity:
        return self._radius