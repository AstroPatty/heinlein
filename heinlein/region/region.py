from functools import singledispatchmethod

import astropy.units as u
from astropy.coordinates import SkyCoord
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.region import sampling
from heinlein.region.base import BaseRegion, create_bounding_box
from heinlein.utilities.utilities import initialize_grid


def parse_angle_list(angles: list[u.Quantity]):
    """
    Parse a list of angles into floats. In units of degrees.
    """
    return list(
        map(
            lambda angle: angle.to(u.deg).value
            if isinstance(angle, u.Quantity)
            else angle,
            angles,
        )
    )


class Region:
    @staticmethod
    def circle(
        center: SkyCoord | tuple,
        radius: u.Quanity | float,
        name: str = None,
        *args,
        **kwargs,
    ):
        """
        Return a circular region. Centered on center, radius of `radius`
        The "center" is anything that can be parsed to a SkyCoord
        If no units provided, will default to degrees
        """
        if isinstance(center, SkyCoord):
            center = (center.ra.value, center.dec.value)
        if isinstance(radius, u.Quantity):
            radius = radius.to_value("deg").value
        return CircularRegion(center, radius, name, *args, **kwargs)

    @staticmethod
    def box(bounds: tuple, name: str = None):
        try:
            if len(bounds) != 4:
                raise ValueError("Invalid bounds: must be 4 values")
        except TypeError:
            raise ValueError("Invalid bounds: must be a tuple of 4 values")

        bounds_degree = parse_angle_list(bounds)
        return BoxRegion(bounds_degree, name)


class BoxRegion(BaseRegion):
    def __init__(self, bounds: tuple, name: str = None, *args, **kwargs):
        """
        Basic general-shape region object.

        Parameters:

        polygon <spherical_geometry.SingleSphericalPolygon>: The spherical polygon
        representing the region

        name <str>: a name for the region (optional)
        """
        polygon = create_bounding_box(*bounds)
        super().__init__(polygon, bounds, name, *args, **kwargs)
        self._sampler = None

    def generate_circular_tile(self, radius, *args, **kwargs):
        """
        Return a circular tile, drawn randomly from the region.
        """
        if getattr(self, "_sampler", None) is None:
            self._get_sampler()
        return self._sampler.get_circular_sample(radius)

    def generate_circular_tiles(self, radius, n, *args, **kwargs):
        if self._sampler is None:
            self._get_sampler()
        return self._sampler.get_circular_samples(radius, n)

    def _get_sampler(self, *args, **kwargs):
        self._sampler = sampling.Sampler(self)

    def initialize_grid(self, density=1000, *args, **kwargs):
        bounds = self.sky_geometry.bounds
        area = self.sky_geometry.area
        coords = initialize_grid(bounds, area, density)
        return coords

    generate_grid = initialize_grid


class CircularRegion(BaseRegion):
    def __init__(self, center: tuple, radius: tuple, name: str = None, *args, **kwargs):
        """
        Circular region. Accepts point-radius for initialization.

        parameters:

        center <SkyCoord>: The center of the region
        radius <astropy.units.quantity>: The radius of the region
        name <str>: a name for the region (optional)
        """
        self._center = center
        self._radius = radius
        self._skypoint = SkyCoord(*center, unit="deg")
        self._unitful_radius = radius * u.deg

        geometry = SingleSphericalPolygon.from_cone(
            *self.center,
            self.radius,
            *args,
            **kwargs,
        )
        bounds = (
            center.ra - radius,
            center.dec - radius,
            center.ra + radius,
            center.dec + radius,
        )
        super().__init__(geometry, bounds, name, *args, **kwargs)

    @property
    def center(self) -> SkyCoord:
        return self._skypoint

    @property
    def radius(self) -> u.quantity:
        return self._unitful_radius

    @singledispatchmethod
    def contains_point(self, point: SkyCoord):
        separation = point.separation(self.center)
        return separation <= self.radius

    @contains_point.register
    def _(self, point: tuple):
        point = SkyCoord(*point, unit="deg")
        return self.contains_point(point)
