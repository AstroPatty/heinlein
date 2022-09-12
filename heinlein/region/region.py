from ast import Mult
from functools import reduce
from typing import Union
import astropy.units as u
from shapely.geometry import Point
from astropy.coordinates import SkyCoord
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.region.base import BaseRegion

class Region:

    @staticmethod
    def circle(center: Union[SkyCoord, tuple], radius: Union[u.Quantity, float], *args, **kwargs):
        """
        Return a circular region. Centered on center, radius of `radius`
        The "center" is anything that can be parsed to a SkyCoord
        If no units provided, will default to degrees
        """
        sky_center = center
        sky_radius = radius
        if type(center) == SkyCoord and type(radius) == u.Quantity:
            return CircularRegion(center, radius)
        elif type(center) == tuple:
            try:
                center_coord = SkyCoord(*sky_center)
            except u.UnitTypeError:
                center_coord = SkyCoord(*sky_center, unit="deg")
        elif type(center) == SkyCoord:
            center_coord = center

        if type(sky_radius) != u.Quantity:
            sky_radius = sky_radius*u.deg

        return CircularRegion(center_coord, sky_radius, *args, **kwargs)

    @staticmethod
    def polygon(coords, *args, **kwargs):
        if type(coords) == SingleSphericalPolygon:
            return PolygonRegion(coords, *args, **kwargs)


def build_compound_region(regions: dict, *args, **kwargs) -> BaseRegion:
    first = list(regions.values())[0]
    second = list(regions.values())[1]
    a = first.union(second)
    full_region = reduce(lambda first, second: first.union(second), regions.values())
    region_obj = Region(points = b.boundary.coords)
    region_obj.add_subregions(regions)
    return region_obj
    
class PolygonRegion(BaseRegion):

    def __init__(self, polygon: SingleSphericalPolygon, name: str = None, *args, **kwargs):
        """
        Basic general-shape region object
        """
        super().__init__(polygon, "PolygonRegion", name)

    @property
    def center(self) -> Point:
        return self._flat_geometry.centroid
class CircularRegion(BaseRegion):

    def __init__(self, center: SkyCoord, radius: u.Quantity, name = None, *args, **kwargs) -> None:
        """
        Circular region
        Accepts point-radius for initialization.
        Shapely does not techincally have a "spherical regions" object
        """
        
        self._skypoint = center
        self._radius = radius
        self._center = Point(center.ra.to_value("deg"), center.dec.to_value("deg"))

        geometry = SingleSphericalPolygon.from_cone(center.ra.to(u.deg).value, center.dec.to(u.deg).value, self._radius.to(u.deg).value, *args, **kwargs)
        super().__init__(geometry, "CircularRegion", name, *args, **kwargs)

    @property
    def center(self) -> Point:
        return self._center

    @property
    def coordinate(self) -> SkyCoord:
        return self._skypoint

    @property
    def radius(self) -> u.quantity:
        return self._radius
    