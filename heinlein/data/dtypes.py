from typing import Protocol, Any
from astropy.table import vstack


def get_data_object(dtype: str, values: list) -> Any:
    if dtype == "catalog":
        return vstack(values)

class HeinleinData(Protocol):
    
    def __init__(self, *args, **kwargs):
        pass
    
    def get_data_in_region(self, *args, **kwargs):
        pass


class Catalog:
    
    def __init__(self, *args, **kwargs):
        pass

    def get_data_in_region(self, *args, **kwargs):
        pass

class StarMask:

    def __init__(self, *args, **kwargs):
        pass

    def get_data_in_region(self, *args, **kwargs):
        pass




        