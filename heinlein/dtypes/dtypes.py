from typing import Protocol, Any
from astropy.table import vstack
from heinlein.region.base import BaseRegion
def get_data_object(dtype: str, values: dict) -> Any:
    if len(values) == 1:
        return list(values.values())[0]
    else:

        good_values = [v for v in values.values() if v is not None]
        return_value = good_values[0].concatenate(good_values[1:])
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




        