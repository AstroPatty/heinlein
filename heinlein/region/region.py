from functools import singledispatchmethod
from math import ceil
from typing import Union
import astropy.units as u
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely import geometry
from astropy.coordinates import SkyCoord
from spherical_geometry.polygon import SingleSphericalPolygon
from spherical_geometry.vector import vector_to_lonlat
from heinlein.region.base import BaseRegion
from heinlein.region import sampling
from heinlein.utilities.utilities import initialize_grid
import numpy as np

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
        """
        Return a generically-shaped region:
        """
        if type(coords) == SingleSphericalPolygon:
            return PolygonRegion(coords, *args, **kwargs)
        elif issubclass(type(coords), BaseGeometry):
            points = coords.exterior.xy
            poly = SingleSphericalPolygon.from_radec(points[0], points[1])
            return PolygonRegion(poly, *args, **kwargs)


    @staticmethod
    def box(bounds, *args, **kwargs):
        if not (type(bounds) == list or len(args) == 3):
            print("Error box region expects 4 inputs")
            return
        if len(args) == 3:
            bounds_ = [bounds] + list(args)
        else:
            bounds_ = bounds
        box_ = geometry.box(*bounds_)
        b_ = Region.polygon(box_)
        b_.box_ = box_
        return b_



class PolygonRegion(BaseRegion):

    def __init__(self, polygon, name: str = None, *args, **kwargs):
        """
        Basic general-shape region object.

        Parameters:

        polygon <spherical_geometry.SingleSphericalPolygon>: The spherical polygon representing the region
        name <str>: a name for the region (optional)
        """
        super().__init__(polygon, "PolygonRegion", name)
        self._sampler = None

    @property
    def center(self) -> Point:
        """
        Return the center of the region
        """
        return self._flat_geometry.centroid

    def generate_circular_tile(self, radius, *args, **kwargs):
        """
        Return a circular tile, drawn randomly from the region.
        """
        if self._sampler is None:
            self._get_sampler()
        return self._sampler.get_circular_sample(radius)
    
    def _get_sampler(self, *args, **kwargs):
        self._sampler = sampling.Sampler(self)

    def contains(self, reg: BaseRegion):
        return self.sky_geometry.contains(reg.sky_geometry)

    def initialize_grid(self, density=1000, *args, **kwargs):
        bounds = self.sky_geometry.bounds
        area = self.sky_geometry.area
        coords = initialize_grid(bounds, area, density)
        return coords

class CircularRegion(BaseRegion):

    def __init__(self, center: SkyCoord, radius: u.Quantity, name = None, *args, **kwargs) -> None:
        """
        Circular region. Accepts point-radius for initialization.

        parameters:

        center <SkyCoord>: The center of the region
        radius <astropy.units.quantity>: The radius of the region
        name <str>: a name for the region (optional)
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
    
    @singledispatchmethod
    def contains(self, point: SkyCoord):
        separation = point.separation(self.coordinate)
        return separation <= self.radius

    @contains.register
    def _(self, point: geometry.Point, *args, **kwargs):
        lonlat = vector_to_lonlat(point.x, point.y, point.z)
        return self.contains(SkyCoord(*lonlat, unit="deg"))

    def initialize_grid(self, density, *args, **kwargs):
        bounds = self.sky_geometry.bounds
        area = geometry.box(*bounds).area
        grid = initialize_grid(bounds, area, density)
        center = self.coordinate
        return grid[center.separation(grid) < self.radius]