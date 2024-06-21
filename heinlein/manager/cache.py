from collections import OrderedDict

from heinlein.dtypes.dobj import HeinleinDataObject


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

    def add(self, region_name: str, data: dict[str, HeinleinDataObject]):
        """
        Add objects to the cache. If the cache is full, evict objects until the
        object can be added.
        """
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

    def get(self, region_name, dtypes):
        if region_name not in self.cache:
            raise ValueError("Region not in cache")
        if not isinstance(dtypes, list):
            dtypes = [dtypes]
        if not all([dtype in self.cache[region_name] for dtype in dtypes]):
            raise ValueError("Not all data types are in the cache")

        self.cache.move_to_end(region_name, last=False)
        return {dtype: self.cache[region_name][dtype] for dtype in dtypes}

    def has_data(self, region_name, dtype):
        return region_name in self.cache and dtype in self.cache[region_name]
