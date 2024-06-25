from collections import OrderedDict
from functools import singledispatchmethod

CURRENT_CACHES = {}


def get_cache(dataset: str, max_size: float = 4e9):
    if dataset not in CURRENT_CACHES:
        CURRENT_CACHES[dataset] = Cache(max_size)
    else:
        CURRENT_CACHES[dataset].change_max_size(max_size)
    return CURRENT_CACHES[dataset]


def clear_cache(dataset: str):
    if dataset in CURRENT_CACHES:
        CURRENT_CACHES[dataset].empty()
    else:
        raise ValueError(f"No cache for dataset {dataset} found in memory")


class Cache:
    """
    A caching implementation that attempts to keep track of the amount of memory
    being used. Heinlein data objects must define a method that returns the
    approximate size of an object in bytes. The nice thing is that most of our
    data types are simple arrays of floats at the end of the day.

    The cache thinks in terms of survey regions. A single survey region may
    have multiple objects associated with it. When the cache evicts objects,
    it evicts all objects associated with a given survey region with a LRU
    policy.

    The cache assumes immutability of the underlying data. This means that if
    it recieves a request to add a piece of data that is already in the cache,
    it will raise an error.
    """

    def __init__(self, max_size: float = 4e9):
        self.max_size = max_size  # default to 4 GB
        self.cache = OrderedDict()
        self.sizes = {}
        self.size = 0

    def add(self, data):
        """
        Add objects to the cache. If the cache is full, evict objects until the
        object can be added.
        """
        data_to_cache = switch_major_key(data)
        for region_name, data in data_to_cache.items():
            if region_name in self.cache:
                dtypes_to_add = set(data.keys()) - set(self.cache[region_name].keys())
                if not dtypes_to_add:
                    raise ValueError("These objects are already in the cache")
            else:
                dtypes_to_add = data.keys()

            total_size = sum([data[dt].estimate_size() for dt in dtypes_to_add])
            self.make_space(total_size)
            self.size += total_size
            self.cache[region_name] = data
            self.sizes[region_name] = total_size

    def change_max_size(self, new_size: float):
        if new_size > self.size:
            self.max_size = new_size
            return True
        else:
            raise ValueError(
                "Cannot change the cache size to a value smaller than the current size"
            )

    def make_space(self, needed_space: int):
        if needed_space > self.max_size:
            raise ValueError(
                "Cannot make space for an object larger than the cache itself"
            )

        current_space = self.max_size - self.size
        if needed_space < current_space:
            return True  # we have enough space

        space_to_free = needed_space - current_space
        while space_to_free > 0:
            region_name, region_data = self.cache.popitem()
            region_space = self.sizes.pop(region_name)
            space_to_free -= region_space
            self.size -= region_space
            del region_data
        return True

    def empty(self):
        del self.cache
        self.cache = OrderedDict()
        self.sizes = {}
        self.size = 0

    def drop(self, region_names):
        for region_name in region_names:
            if region_name in self.cache:
                region_space = self.sizes.pop(region_name)
                self.size -= region_space
                del self.cache[region_name]

    @singledispatchmethod
    def get(self, region_name: str, dtypes):
        if region_name not in self.cache:
            raise ValueError("Region not in cache")
        if not isinstance(dtypes, list):
            dtypes = [dtypes]

        dtypes_in_cache = set(self.cache[region_name].keys())
        dtypes_to_get = set(dtypes).intersection(dtypes_in_cache)
        if not dtypes_to_get:
            raise ValueError("None of the requested objects are in the cache")

        self.cache.move_to_end(region_name, last=False)
        return {dtype: self.cache[region_name][dtype] for dtype in dtypes_to_get}

    @get.register
    def _(self, regions: set, dtypes):
        if not isinstance(dtypes, list):
            dtypes = [dtypes]
        output = {}
        for region in regions:
            try:
                output[region] = self.get(region, dtypes)
            except ValueError:
                continue
        return switch_major_key(output)

    def has_data(self, region_name, dtype):
        return region_name in self.cache and dtype in self.cache[region_name]


def switch_major_key(data: dict):
    """
    The godata cache thinks in terms of regions, while the rest of the codebase
    thinks in terms of data types. This function switch the major key from one to
    the other.
    """

    output = {}
    for major_key, minor_data in data.items():
        for minor_key, data in minor_data.items():
            if minor_key not in output:
                output[minor_key] = {}
            output[minor_key][major_key] = data
    return output
