from typing import Any, Union
import astropy.units as u
from shapely.geometry import Point, Polygon
from astropy.coordinates import SkyCoord

from heinlein.data import get_handler
from heinlein.region.base import BaseRegion

def Region(*args, **kwargs) -> BaseRegion:
    """
    Factory function for building regions.
    """
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



class PolygonRegion(BaseRegion):

    def __init__(self, points, name: str, *args, **kwargs):
        """
        Basic general-shape region object
        """
        geometry = Polygon(points)

        super().__init__(geometry)
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
            self._radius = radius.to(u.degree).value
        else:
            self._radius = radius
        geometry = self._center.buffer(self._radius)
        super().__init__(geometry)

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

    @property
    def center(self) -> Point:
        return self._center
