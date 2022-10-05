from abc import ABC, abstractmethod
from functools import  singledispatchmethod
from gettext import Catalog
import numpy as np
import pymangle
from astropy.io.fits import HDUList
from astropy.wcs import WCS, utils
from astropy.utils.exceptions import AstropyWarning
import warnings
from shapely.geometry.base import BaseGeometry
from shapely.geometry import MultiPoint
from shapely.strtree import STRtree
from heinlein.region import BaseRegion
from astropy.coordinates import SkyCoord
from spherical_geometry.vector import lonlat_to_vector, vector_to_lonlat
from shapely import geometry
from heinlein.region.region import CircularRegion

warnings.simplefilter('ignore', category=AstropyWarning)


def get_mask_objects(input_list, *args, **kwargs):
    output_data = np.empty(len(input_list), dtype="object")
    for index, obj in enumerate(input_list):
        if type(obj) == HDUList:
            if kwargs.get("pixarray", False):
                output_data[index] = _pixelArrayMask(obj, *args, **kwargs)
            else:
                output_data[index] = _fitsMask(obj, *args, **kwargs)
        elif type(obj) == pymangle.Mangle:
            output_data[index] = _mangleMask(obj)
        elif type(obj) == np.ndarray:
            if isinstance(obj[0], BaseGeometry):
                output_data[index] = _shapelyMask(obj)
            elif isinstance(obj[0], BaseRegion):
                output_data[index] = _regionMask(obj)

    return output_data

class Mask:

    def __init__(self, masks = [], *args, **kwargs):
        """
        Masks are much less regular than catalogs. There are many different
        formats, and some surveys mix formats. The "Mask" object is a wraper class
        that handles interfacing with all these different formats.
        """
        self._masks = get_mask_objects(masks, *args, **kwargs)

    def __len__(self):
        return len(self._masks)

    @classmethod
    def from_masks(cls, masks, *args, **kwargs):
        m = cls()
        m._masks = masks
        return m

    def mask(self, catalog: Catalog, *args, **kwargs):
        for mask in self._masks:
            catalog = mask.mask(catalog)
            if len(catalog) == 0:
                return catalog
        return catalog


    def append(self, other):

        if len(other) == 0:
            return self

        masks = np.empty(1 + len(other), dtype=object)
        for index, m_ in enumerate(other):
            masks[index+1] = m_._masks
        masks[0] = self._masks
        all_masks = np.hstack(masks)
        return Mask.from_masks(all_masks)
        
        

class _mask(ABC):

    def __init__(self, mask, *args, **kwargs):
        """
        Basic mask object. Handles a single mask of an arbitary type.
        """
        self._mask = mask

    @abstractmethod
    def mask(self, *args, **kwargs):
        """
        For subclasses, the actual masking logic will be implmeneted here.
        """
        pass

class _mangleMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        """
        Implementation for masks in mangle format
        """
        super().__init__(mask)

    @singledispatchmethod
    def mask(self, catalog: Catalog, *args, **kwargs):
        coords = catalog.coords
        contains = self._check(coords)
        return catalog[~contains]

    @mask.register
    def _(self, coords: SkyCoord):
        contains = self._check(coords)
        return coords[~contains]

    def _check(self, coords):
        ra = coords.ra.to("deg").value
        dec = coords.dec.to("deg").value
        contains = self._mask.contains(ra, dec)
        return contains

class _pixelArrayMask(_mask):
    def __init__(self, mask, mask_key, *args, **kwargs):
        super().__init__(mask)
        self._wcs = WCS(mask[0].header)
        self._mask_key = mask_key
        self._init_pixel_array()

    def _init_pixel_array(self, *args, **kwargs):
        mask = self._mask[self._mask_key].data
        
        pixels = np.where(mask > 0)
        pixel_coords = np.ones(mask.shape, dtype=bool)
        pixel_coords[pixels] = False
        self._mask.close()
        self._mask = pixel_coords

    def _check(self, coords, *args, **kwargs):
        pix_coords = self._wcs.world_to_pixel(coords)
        shape = self._mask.shape
        x = np.round(pix_coords[0], 0).astype(int)
        y = np.round(pix_coords[1], 0).astype(int)
        x_lims = (x < 0) | (x >= shape[0])
        y_lims = (y < 0) | (y >= shape[1])
        m_ = x_lims | y_lims #These objects are outside this particular mask

        unmasked_objects = np.ones(len(coords), dtype=bool )
        unmasked_objects[~m_] = self._mask[x[~m_], y[~m_]]
        return unmasked_objects

    @singledispatchmethod
    def mask(self, catalog: Catalog, *args, **kwargs):
        coords = catalog.coords
        mask = self._check(coords)
        return catalog[mask]
    
    @mask.register
    def _(self, coords: SkyCoord):
        mask = self._check(coords)
        return coords[mask]

class _fitsMask(_mask):
    def __init__(self, mask, mask_key, pixarray = False, *args, **kwargs):
        """
        If the mask is stored in a fits file, we assume we can 
        get the WCS info from the header in HDU 0, but we need to
        know where the actual mask is located, so we pass a key.
        A fits mask assumes masked pixels have a value > 0
        """
        super().__init__(mask)

        self._wcs = WCS(mask[0].header)
        self._mask_key = mask_key
        self._mask_plane = self._mask[self._mask_key].data

    def _check(self, coords):
        x, y = utils.skycoord_to_pixel(coords, self._wcs)
        x = np.round(x,0).astype(int)
        y = np.round(y,0).astype(int)
        masked = np.ones(len(x), dtype=bool)

        x_limit = self._mask_plane.shape[0]
        y_limit = self._mask_plane.shape[1]

        negative_check = (x < 0) | (y < 0)
        #Note: We already inverted indices above
        x_limit_check = x >= x_limit
        y_limit_check = y >= y_limit
        to_skip = negative_check | x_limit_check | y_limit_check

        masked[to_skip] = False
        pixel_values = self._mask_plane[x[~to_skip], y[~to_skip]] 
        masked[~to_skip] = (pixel_values > 0)
        return ~masked

    @singledispatchmethod
    def mask(self, catalog: Catalog, *args, **kwargs):
        coords = catalog.coords
        mask = self._check(coords)
        return catalog[mask]

    @mask.register
    def _(self, coords: SkyCoord):
        mask = self._check(coords)
        return coords[mask]
class _regionMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        """
        Implementation for masks defined as regions.
        """
        super().__init__(mask)
        self._init_tree()
    
    def _init_tree(self):
        geo_list = np.array([reg.geometry for reg in self._mask])
        indices = {id(geo): i for i, geo in enumerate(geo_list)}
        self._geo_idx = indices
        self._geo_tree = STRtree(geo_list)

    @singledispatchmethod
    def mask(self, catalog: Catalog):
        import time
        mp = {'skycoords': catalog.coords, "points": MultiPoint(catalog.points)}
        mask = self._check(mp)
        return catalog[mask]

    @mask.register
    def _(self, coords: SkyCoord):
        ra = coords.ra.to_value("deg")
        dec = coords.dec.to_value("deg")
        points = np.dstack(lonlat_to_vector(ra, dec))[0]
        mp = {'skycoords': coords, 'points': MultiPoint(points)}
        mask = self._check(mp)
        return coords[mask]

    def _check(self, points_dict):
        points = points_dict['points']
        skycoords = points_dict['skycoords']
        mask = np.ones(len(points.geoms), dtype=bool)
        for index, p in enumerate(points.geoms):
            a = self._geo_tree.query(p)
            for geo in a:
                if geo.contains(p):
                    mask[index] = True
                    break
        return mask

class _shapelyMask(_mask):
    def __init__(self, mask, *args, **kwargs):
        """
        Implmentations for masks defined as shapely polygons
        """
        super().__init__(mask)
        self._init_region_tree

    def _init_region_tree(self, *args, **kwargs):
        self._tree = STRtree(self._mask)

    def mask(self, catalog):
        ras = catalog.coords.ra.to_value("deg")
        decs = catalog.coords.dec.to_value("deg")
        points = geometry.MultiPoint(list(zip(ras, decs)))
        mask = np.ones(len(catalog), dtype=bool)
        for index, point in enumerate(points.geoms):
            if mask[index]:
                for submask in self._mask:
                    if submask.contains(point):
                        mask[index] = False
        
        return catalog[mask]