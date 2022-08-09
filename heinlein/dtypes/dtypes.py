from typing import Protocol, Any
from astropy.table import vstack
from heinlein.region.base import BaseRegion
def get_data_object(dtype: str, values: list) -> Any:
    if len(values) == 1:
        return values[0]
    else:
        return_value = values[0].concatenate(values[1:])
        return return_value 
class HeinleinData(Protocol):
    
    def __init__(self, *args, **kwargs):
        pass

    def get_data_from_region(self, region: BaseRegion, *args, **kwargs):
        pass
        
    def concatenate(self, *args, **kwargs):
        pass
    
class StarMask:

    def __init__(self, *args, **kwargs):
        pass

    def get_data_in_region(self, *args, **kwargs):
        pass




        