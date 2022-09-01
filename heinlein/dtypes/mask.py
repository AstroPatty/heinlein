from abc import ABC
import numpy as np
import pymangle
from astropy.io.fits import HDUList

import heinlein

def get_mask_objects(input_list):
    output_data = np.empty(len(input_list), dtype="object")
    for index, obj in enumerate(input_list):
        if type(obj) == HDUList:
            output_data[index] = _fitsMask(obj)
        elif type(obj) == pymangle.Mangle:
            output_data[index] = _mangleMask(obj)
    return output_data

class Mask:

    def __init__(self, masks, *args, **kwargs):
        """
        Masks are much less regular than catalogs. There are many different
        formats, and some surveys mix formats. The "Mask" object is a wraper class
        that handles interfacing with all these different formats.
        """
        self._masks = get_mask_objects(masks)

    def mask(self, catalog, *args, **kwargs):
        pass


class _mask(ABC):

    def __init__(self, *args, **kwargs):
        pass

    def mask(self, *args, **kwargs):
        pass

class _mangleMask(_mask):
    def __init__(self, mask):
        self._mask = mask

class _fitsMask(_mask):
    def __init__(self, mask):
        self._mask = mask