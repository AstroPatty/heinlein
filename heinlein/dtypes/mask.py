import warnings
from abc import ABC, abstractmethod
from functools import singledispatchmethod
from gettext import Catalog

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io.fits import HDUList
from astropy.nddata import Cutout2D
from astropy.nddata.utils import NoOverlapError
from astropy.utils.exceptions import AstropyWarning
from astropy.wcs import WCS, utils
from shapely import get_num_geometries
from shapely.geometry import MultiPoint
from shapely.strtree import STRtree
from spherical_geometry.vector import lonlat_to_vector

from heinlein.dtypes.dobj import HeinleinDataObject
from heinlein.region import BaseRegion, CircularRegion

warnings.simplefilter("ignore", category=AstropyWarning)


def get_mask_objects(input_list, *args, **kwargs):
    output_data = np.empty(len(input_list), dtype="object")
    for index, obj in enumerate(input_list):
        if type(obj) == HDUList:
            # if kwargs.get("pixarray", False):
            #    output_data[index] = _pixelArrayMask(obj, *args, **kwargs)
            # else:
            output_data[index] = _fitsMask.from_hdu(obj, *args, **kwargs)
        elif type(obj) == np.ndarray:
            if isinstance(obj[0], BaseRegion):
                output_data[index] = _regionMask(obj)

    return output_data


class Mask(HeinleinDataObject):
    def __init__(self, masks=[], *args, **kwargs):
        """
        Masks are much less regular than catalogs. There are many different
        formats, and some surveys mix formats. The "Mask" object is a wraper class
        that handles interfacing with all these different formats.
        """
        self._masks = get_mask_objects(masks, *args, **kwargs)
        self._check_filter = False
        self._can_filter = False

    @classmethod
    def combine(cls, masks, *args, **kwargs):
        all_masks = [m._masks for m in masks]
        all_masks = np.hstack(all_masks)
        return cls.from_masks(all_masks)

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
            masks[index + 1] = m_._masks
        masks[0] = self._masks
        all_masks = np.hstack(masks)
        return Mask.from_masks(all_masks)

    def get_data_from_region(self, region: BaseRegion):
        if not self._check_filter:
            self._can_filter = any(
                [hasattr(mask, "get_data_from_region") for mask in self._masks]
            )
        if not self._can_filter:
            raise AttributeError

        return_vals = []
        for mask in self._masks:
            try:
                submask = mask.get_data_from_region(region)
                if submask is not None:
                    return_vals.append(submask)
            except AttributeError:
                return_vals.append(mask)
        return Mask.from_masks(return_vals)


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
        coords = catalog["coordinates"]
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
        m_ = x_lims | y_lims  # These objects are outside this particular mask

        # plt.scatter(coords.ra, coords.dec, transform=ax.get_transform('world'))

        unmasked_objects = np.zeros(len(coords), dtype=bool)
        unmasked_objects[~m_] = self._mask[x[~m_], y[~m_]]

        return unmasked_objects

    @singledispatchmethod
    def mask(self, catalog: Catalog, *args, **kwargs):
        coords = catalog["coordinates"]
        mask = self._check(coords)
        return catalog[mask]

    @mask.register
    def _(self, coords: SkyCoord):
        mask = self._check(coords)
        return coords[mask]


class _fitsMask(_mask):
    def __init__(self, mask, wcs, mask_data):
        super().__init__(mask)
        self._wcs = wcs
        self._mask_plane = mask_data

    @classmethod
    def from_hdu(cls, mask, mask_key, pixarray=False, *args, **kwargs):
        """
        If the mask is stored in a fits file, we assume we can
        get the WCS info from the header in HDU 0, but we need to
        know where the actual mask is located, so we pass a key.
        A fits mask assumes masked pixels have a value > 0
        """

        wcs = WCS(mask[0].header)
        mask_key = mask_key
        mask_plane = mask[mask_key].data
        return cls(mask, wcs, mask_plane)

    @classmethod
    def from_cutout(cls, cutout):
        wcs = cutout.wcs
        data = cutout.data
        return cls(cutout, wcs, data)

    def _check(self, coords):
        y, x = utils.skycoord_to_pixel(coords, self._wcs)
        # The order of numpy axes is the opposite of the order
        # in fits images. All the data is being stored in
        # arrays, so we have to flip things here.
        x = np.round(x, 0).astype(int)
        y = np.round(y, 0).astype(int)
        masked = np.ones(len(x), dtype=bool)

        x_limit = self._mask_plane.shape[0]
        y_limit = self._mask_plane.shape[1]

        negative_check = (x < 0) | (y < 0)
        # Note: We already inverted indices above
        x_limit_check = x >= x_limit
        y_limit_check = y >= y_limit
        to_skip = negative_check | x_limit_check | y_limit_check

        masked[to_skip] = False
        pixel_values = self._mask_plane[x[~to_skip], y[~to_skip]]
        masked[~to_skip] = pixel_values > 0
        return ~masked

    @singledispatchmethod
    def mask(self, catalog: Catalog, *args, **kwargs):
        coords = catalog["coordinates"]
        mask = self._check(coords)
        return catalog[mask]

    def get_data_from_region(self, region):
        if type(region) == CircularRegion:
            center = region.coordinate
            size = (region.radius, region.radius)
        else:
            return NotImplementedError

        try:
            cutout = Cutout2D(self._mask_plane, center, size, wcs=self._wcs, copy=True)
        except NoOverlapError:
            return None

        return _fitsMask.from_cutout(cutout)

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
        self._geo_list = np.array([reg.geometry for reg in self._mask])
        self._geo_tree = STRtree(self._geo_list)

    @singledispatchmethod
    def mask(self, catalog: Catalog):
        cmask = self.generate_mask(catalog["coordinates"])
        return catalog[cmask]

    @mask.register
    def _(self, coords: SkyCoord):
        cmask = self.generate_mask(coords)
        return coords[cmask]

    def generate_mask(self, coords: SkyCoord):
        ra = coords.ra.to_value("deg")
        dec = coords.dec.to_value("deg")
        points = MultiPoint(np.dstack(lonlat_to_vector(ra, dec))[0])
        mask = self._check(points)
        return mask

    def _check(self, points):
        mask = np.ones(get_num_geometries(points), dtype=bool)
        for index, p in enumerate(points.geoms):
            a = self._geo_tree.query(p)
            for geo in a:
                if self._geo_list[geo].contains(p):
                    mask[index] = False
                    break
        return mask
