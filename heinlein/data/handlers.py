
from functools import partial

def get_handler(survey_mod, regions, dtype):
    """
    Returns a function to get data from a particular region.
    This allows for lazy evaluation, which is useful with large datasets.
    """
    try:
        h_name = f"get_{dtype}"
        handler = getattr(survey_mod, h_name)
        return partial(handler, regions=regions)
    except AttributeError:
        return get_defualt_handler(dtype)

def get_defualt_handler(dtype):
    pass

def get_catalog(survey_mod, regions):
    pass
