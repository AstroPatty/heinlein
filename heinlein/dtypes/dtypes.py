from typing import Protocol, Any
from astropy.table import vstack
from heinlein.region.base import BaseRegion

def get_data_object(dtype: str, values: dict) -> Any:
    if type(values) != dict:
        return values
    if len(values) == 1:
        return list(values.values())[0]
    else:
        good_values = [v for v in values.values() if v is not None]
        return_value = good_values[0].concatenate(good_values[1:])
        return return_value 

        