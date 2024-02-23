import astropy.units as u
import numpy as np
from shapely import GeometryCollection, Point


class Sampler:
    def __init__(self, footprint: GeometryCollection, *args, **kwargs):
        """
        Base class for samplers
        """
        self.setup(footprint)

    def setup(self, footprint: GeometryCollection, *args, **kwargs):
        self._footprint = footprint
        bounds = self._footprint.bounds
        ra1, ra2 = bounds[0], bounds[2]
        dec1, dec2 = bounds[1], bounds[3]
        ra_range = (min(ra1, ra2), max(ra1, ra2))
        dec_range = (min(dec1, dec2), max(dec1, dec2))
        phi_range = np.radians(ra_range)
        # Keeping everything in radians for simplicity
        # Convert from declination to standard spherical coordinates
        theta_range = (90.0 - dec_range[0], 90.0 - dec_range[1])
        # Area element on a sphere is dA = d(theta)d(cos[theta])
        # Sampling uniformly on the surface of a sphere means sampling uniformly
        # Over cos theta
        costheta_range = np.cos(np.radians(theta_range))
        self._low_sampler_range = [phi_range[0], costheta_range[0]]
        self._high_sampler_range = [phi_range[1], costheta_range[1]]
        self._sampler = np.random.default_rng()

    def sample(self, n=1, tolerance: u.Quantity = None, *args, **kwargs):
        vals = self._sampler.uniform(self._low_sampler_range, self._high_sampler_range)
        ra = np.degrees(vals[0])
        theta = np.degrees(np.arccos(vals[1]))
        dec = 90 - theta

        shapely_point = Point(ra, dec)

        if self._footprint.contains(shapely_point):
            if tolerance is None:
                return ra, dec
            region = shapely_point.buffer(tolerance.to(u.deg).value)
            if self._footprint.contains_properly(region):
                return ra, dec
        return self.sample(n)
