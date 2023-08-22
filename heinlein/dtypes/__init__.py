from __future__ import annotations
from .dtypes import get_data_object
from abc import ABC, abstractmethod, abstractclassmethod
from heinlein.region import BaseRegion

__all__ = ["get_data_object"]

class HeinleinDataObject(ABC):
    """
    This is a generic class that is used for storing data objects in the cache. An
    object of this type will never actually be given to the user. The data objects
    must define a `get_data_from_region` method, which will return the data from the
    region provided.
    
    """
    @abstractmethod
    def get_data_from_region(self, region: BaseRegion):
        pass

    @abstractclassmethod
    def combine(cls, objects: list[HeinleinDataObject]):
        pass
