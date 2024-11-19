from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from astropy.coordinates import SkyCoord
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.locations import MAIN_CONFIG_DIR

logger = logging.getLogger("region")


def load_config(*args, **kwargs):
    """
    Loads the region config.
    """
    config_location = MAIN_CONFIG_DIR / "region" / "region.json"
    with open(config_location, "r") as f:
        config = json.load(f)
        return config


def create_bounding_box(bounds: tuple) -> SingleSphericalPolygon:
    """
    Create a SingleSphericalPolygon from bounds, setup as "RA1 DEC1 RA2 DEC2"
    Note, this does NOT check that the ra_min < ra_max or dec_min < dec_max,
    because some regions may straddle the 0/360 line or the poles.
    """

    ra_min, dec_min, ra_max, dec_max = bounds
    if ra_min == ra_max or dec_min == dec_max:
        raise ValueError("Invalid bounds: Box has zero width or height")
    RA_STRADDLES_ZERO = ra_min > ra_max
    DEC_STRADDLES_POLE = dec_min > dec_max
    ra_mid = (ra_min + ra_max) / 2
    dec_mid = (dec_min + dec_max) / 2
    if RA_STRADDLES_ZERO:
        ra_mid = (ra_mid + 180) % 360
    if DEC_STRADDLES_POLE:
        dec_mid = (dec_mid + 90) % 180
    ras = [ra_min, ra_max, ra_max, ra_min]
    decs = [dec_min, dec_min, dec_max, dec_max]
    return SingleSphericalPolygon.from_radec(
        ras, decs, center=(ra_mid, dec_mid), degrees=True
    )


current_config = load_config()


class BaseRegion(ABC):
    _config = current_config

    def __init__(
        self,
        polygon: SingleSphericalPolygon,
        bounds: tuple,
        name=None,
        regtype=None,
        *args,
        **kwargs,
    ):
        """
        Base region object.
        Regions should always be initialized with heinlein.Region

        parameters:

        geometry: <spherical_geometry.SphericalPolygon> The sky region
        type: <str> The type of the region
        name: <str> The name of the region (optional)
        """
        self.spherical_geometry = polygon
        self.bounding_box = create_bounding_box(bounds)
        self.name = name
        self._type = regtype

    def __getattribute__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions. Delegates unknown methods to the
        underlying spherical geometry object, IF that method is explicitly permitted
        in heinlein/config/region/region.json
        """
        try:
            config = object.__getattribute__(self, "_config")
            cmd_name = config["allowed_predicates"][__name]
            sg = object.__getattribute__(self, "spherical_geometry")
            predicate = getattr(sg, cmd_name)

            def do_predicate(other: BaseRegion):
                return predicate(other.spherical_geometry)

            return do_predicate
        except (AttributeError, KeyError):
            return object.__getattribute__(self, __name)

    @property
    def bounds(self):
        ra, dec = self.bounding_box.to_lonlat()
        min_ra, max_ra = ra[0], ra[2]
        min_dec, max_dec = dec[0], dec[1]
        return min_ra, min_dec, max_ra, max_dec

    @abstractmethod
    def contains(self, point: SkyCoord) -> bool:
        """
        Check if a point is in the region
        """
        pass
