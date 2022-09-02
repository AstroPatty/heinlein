from abc import ABC, abstractmethod
import numpy as np
import pymangle
from astropy.io.fits import HDUList
from astropy.wcs import WCS, utils
from astropy.utils.exceptions import AstropyWarning
import warnings
import time
from shapely.geometry.base import BaseGeometry
from shapely.geometry import MultiPoint
from shapely.strtree import STRtree
from heinlein.region import BaseRegion

from spherical_geometry.polygon import SingleSphericalPolygon, SphericalPolygon

warnings.simplefilter('ignore', category=AstropyWarning)

def get_mask_objects(input_list, *args, **kwargs):
    output_data = np.empty(len(input_list), dtype="object")
    for index, obj in enumerate(input_list):
        if type(obj) == HDUList:
            output_data[index] = _fitsMask(obj, *args, **kwargs)
        elif type(obj) == pymangle.Mangle:
            output_data[index] = _mangleMask(obj)
        elif type(obj) == np.ndarray:
            if isinstance(obj[0], BaseGeometry):
                output_data[index] = _shapelyMask(obj)
            elif isinstance(obj[0], SingleSphericalPolygon):
                output_data[index] = _sphericalGeometryMask(obj)
            elif isinstance(obj[0], BaseRegion):
                output_data[index] = _regionMask(obj)

    return output_data

class Mask:

    def __init__(self, masks, *args, **kwargs):
        """
        Masks are much less regular than catalogs. There are many different
        formats, and some surveys mix formats. The "Mask" object is a wraper class
        that handles interfacing with all these different formats.
        """
        self._masks = get_mask_objects(masks, *args, **kwargs)

    def mask(self, catalog, *args, **kwargs):
        for mask in self._masks:
            catalog = mask.mask(catalog)
        return catalog

class _mask(ABC):

    def __init__(self, mask, *args, **kwargs):
        self._mask = mask

    @abstractmethod
    def mask(self, *args, **kwargs):
        pass

class _mangleMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        super().__init__(mask)

    def mask(self, catalog, *args, **kwargs):
        coords = catalog.coords
        ra = coords.ra.to("deg").value
        dec = coords.dec.to("deg").value
        contains = self._mask.contains(ra, dec)
        return catalog[~contains]

class _fitsMask(_mask):
    def __init__(self, mask, mask_key, *args, **kwargs):
        """
        If the mask is stored in a fits file, we assume we can 
        get the WCS info from the header in HDU 0, but we need to
        know where the actual mask is located, so we pass a key.
        """
        self._mask_key = mask_key
        super().__init__(mask)
        start = time.time()
        self._wcs = WCS(self._mask[0].header)
        self._mask_plane = self._mask[self._mask_key].data
        end = time.time()

    def mask(self, catalog, *args, **kwargs):
        coords = catalog.coords
        x, y = utils.skycoord_to_pixel(coords, self._wcs)
        x = np.round(x,0).astype(int)
        y = np.round(y,0).astype(int)
        masked = np.ones(len(x), dtype=bool)

        x_limit = self._mask_plane.shape[0]
        y_limit = self._mask_plane.shape[1]

        negative_check = (x < 0) | (y < 0)
        #Note: We already inverted indices above
        x_limit_check = x > x_limit
        y_limit_check = y > y_limit
        to_skip = negative_check | x_limit_check | y_limit_check

        masked[to_skip] = False
        pixel_values = self._mask_plane[x[~to_skip], y[~to_skip]] 
        masked[~to_skip] = pixel_values != 0
        return catalog[~masked]

class _regionMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        super().__init__(mask)
        self._init_tree()
    
    def _init_tree(self):
        geo_list = np.array([reg.geometry for reg in self._mask])
        indices = {id(geo): i for i, geo in enumerate(geo_list)}
        self._geo_idx = indices
        self._geo_tree = STRtree(geo_list)

    def mask(self, catalog):
        mp = MultiPoint(catalog._cartesian_points)
        not_masked = np.ones(len(catalog), dtype=bool)   
        for index, p in enumerate(mp.geoms):     
            a = self._geo_tree.query(p)
            for geo in a:
                if geo.contains(p):
                    not_masked[index] = False
                    break
        return catalog[not_masked]

class _shapelyMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        super().__init__(mask)
        self._init_region_tree

    def _init_region_tree(self, *args, **kwargs):
        self._tree = STRtree(self._mask)

    def mask(self, catalog):
        ras = catalog.coords.ra.to_value("deg")
        decs = catalog.coords.dec.to_value("deg")

class _sphericalGeometryMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        input_mask = SphericalPolygon(mask)
        super().__init__(input_mask)