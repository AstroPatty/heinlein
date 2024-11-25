import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.region import sampling
from heinlein.region.base import BaseRegion, create_bounding_box
from heinlein.utilities.utilities import initialize_grid


def parse_angle_list(angles: list[u.Quantity]):
    """
    Parse a list of angles into floats. In units of degrees.
    """
    angles = list(
        map(
            lambda angle: angle.to(u.deg).value
            if isinstance(angle, u.Quantity)
            else angle,
            angles,
        )
    )
    # Regularize RAs to be between 0 and 360
    angles[0] = angles[0] % 360
    angles[2] = angles[2] % 360
    # Regularize DECs to be between -90 and 90
    # -92 should map to 88
    angles[1] = (angles[1] + 90) % 180 - 90
    angles[3] = (angles[3] + 90) % 180 - 90
    return angles


def create_reflections(bounds: tuple) -> list[tuple]:
    """
    Bounds checking is complicated when region straddles the 0/360 line
    or the poles. This function creates the reflections of the region
    across the 0/360 line and the poles if necessary.

    Because of how the angles are parsed, we can always guarantee that
    RAs are between 0 and 360 and DECs are between -90 and 90
    """
    output_bounds = [bounds]
    ra_min, dec_min, ra_max, dec_max = bounds
    if ra_min > ra_max:
        output_bounds.append((ra_min - 360, dec_min, ra_max, dec_max))
        output_bounds.append((ra_min, dec_min, ra_max + 360, dec_max))
    if dec_min > dec_max:
        new_bounds = []
        for bound_set in output_bounds:
            ra_min, dec_min, ra_max, dec_max = bound_set
            new_bounds.append((ra_min, dec_min + 180, ra_max, dec_max))
            new_bounds.append((ra_min, dec_min, ra_max, dec_max - 180))
        output_bounds.extend(new_bounds)
    return output_bounds


class Region:
    @staticmethod
    def circle(
        center: SkyCoord | tuple,
        radius: u.Quantity | float,
        name: str = None,
        *args,
        **kwargs,
    ):
        """
        Return a circular region. Centered on center, radius of `radius`
        The "center" is anything that can be parsed to a SkyCoord_
        If no units provided, will default to degrees
        """
        if not isinstance(center, SkyCoord):
            center = SkyCoord(*center, unit="deg")
        if not isinstance(radius, u.Quantity):
            radius = radius * u.deg

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


class PolygonRegion(BaseRegion):
    def __init__(
        self, points: list[tuple], inside=None, name: str = None, *args, **kwargs
    ):
        """
        Polygon region. Accepts a list of points for initialization.

        parameters:

        points <list>: A list of points that define the polygon
        name <str>: a name for the region (optional)
        """
        ra = [point[0] for point in points]
        dec = [point[1] for point in points]
        polygon = SingleSphericalPolygon.from_lonlat(ra, dec, inside)
        ra_min = min(ra)
        ra_max = max(ra)
        dec_min = min(dec)
        dec_max = max(dec)
        bounds = (ra_min, dec_min, ra_max, dec_max)
        super().__init__(polygon, bounds, name, "PolygonRegion", *args, **kwargs)
        self._sampler = None

    def contains(self, point: SkyCoord) -> bool:
        return self.spherical_geometry.contains_radec(
            point.ra.deg, point.dec.deg, degrees=True
        )


class BoxRegion(BaseRegion):
    def __init__(self, bounds: tuple, name: str = None, *args, **kwargs):
        """
        Basic general-shape region object.

        Parameters:

        polygon <spherical_geometry.SingleSphericalPolygon>: The spherical polygon
        representing the region

        name <str>: a name for the region (optional)
        """
        polygon = create_bounding_box(bounds)
        super().__init__(polygon, bounds, name, "BoxRegion", *args, **kwargs)
        self._sampler = None

    def contains(self, point: SkyCoord) -> bool:
        """
        Check if a point is contained within the region

        Spherical gemoetry's contain method is much too slow
        for large numbers of points. Eventually I would like
        to migrate to Googles S2 library for this, but for now
        we do basic bounds checking.
        """
        bounds_to_check = create_reflections(self.bounds)
        mask = np.zeros((len(point), 4 * len(bounds_to_check)), dtype=bool)
        bounds = np.array(bounds_to_check).flatten()
        ra_mins = bounds[::4]
        dec_mins = bounds[1::4]
        ra_maxs = bounds[2::4]
        dec_maxs = bounds[3::4]
        ra_arr = point.ra.deg[:, np.newaxis]  #
        dec_arr = point.dec.deg[:, np.newaxis]
        mask[:, 0::4] = ra_arr >= ra_mins
        mask[:, 1::4] = dec_arr >= dec_mins
        mask[:, 2::4] = ra_arr <= ra_maxs
        mask[:, 3::4] = dec_arr <= dec_maxs
        # At this point we have a 2d array of shape (len(point), 4*len(bounds_to_check))
        # Each row is a point, each group of four entires in the row is a comparison to
        # one of the sets of bounds
        # If any group of four in the row is all true, the point is in the region
        mask = mask.reshape(len(point), len(bounds_to_check), 4)
        mask = mask.all(axis=2).any(axis=1)
        return mask

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
    def __init__(
        self, center: SkyCoord, radius: u.Quantity, name: str = None, *args, **kwargs
    ):
        """
        Circular region. Accepts point-radius for initialization.

        parameters:

        center <SkyCoord>: The center of the region
        radius <astropy.units.quantity>: The radius of the region
        name <str>: a name for the region (optional)
        """
        self._center = (center.ra.deg, center.dec.deg)
        self._radius = radius.to_value("deg")
        self._skypoint = center
        self._unitful_radius = radius
        geometry = SingleSphericalPolygon.from_cone(
            *self._center,
            self._radius,
        )
        bounds = (
            self._center[0] - self._radius,
            self._center[1] - self._radius,
            self._center[0] + self._radius,
            self._center[1] + self._radius,
        )
        super().__init__(geometry, bounds, name, "CircularRegion", *args, **kwargs)

    @property
    def center(self) -> SkyCoord:
        return self._skypoint

    @property
    def radius(self) -> u.quantity:
        return self._unitful_radius

    def contains(self, points: SkyCoord) -> bool | np.ndarray:
        distance = self.center.separation(points)
        return distance <= self.radius
