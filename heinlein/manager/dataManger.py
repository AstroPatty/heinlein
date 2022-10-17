from abc import abstractmethod
from importlib import import_module

from abc import ABC
from heinlein.region.base import BaseRegion
from heinlein.utilities import warning_prompt_tf
from heinlein.config.config import globalConfig
from heinlein.manager.dconfig import DatasetConfig
import logging
import pathlib
from cacheout import LRUCache
import multiprocessing as mp

logger = logging.getLogger("manager")
class DataManager(ABC):

    def __init__(self, name, *args, **kwargs):
        """
        The datamanger keeps track of where data is located, either on disk or 
        otherwise.
        It also keeps a manifest, so it knows when files have been moved or changed.
        Managers should generally not be instatiated directly. They are used by Dataset
        objects to find data.

        parameters:

        name: <str> The name of the dataset
        """
        self.name = name
        self.globalConfig = globalConfig
        self._setup()
        self._cache = {}
        self._cache_lock = mp.Lock()

    
    def _setup(self, *args, **kwargs) -> None:
        """
        Performs basic setup of the manager
        Loads datset config if it exists, or prompts
        user if dataset does not exist.
        """

        if not DatasetConfig.exists(self.name): #If this dataset does not exist
            if self.globalConfig.interactive:
                write_new = warning_prompt_tf(f"Survey {self.name} not found, would you like to initialize it? ")
                if write_new:
                    self.config = DatasetConfig.create(self.name)
                else:
                    self.ready = False
            else: raise OSError(f"Dataset {self.name} does not exist!")

        else: #If it DOES exist, get the config data
            self.config = DatasetConfig.load(self.name)
        
        self.external = self.config.external
        self._data = self.config.data

    def get_path(self, dtype: str, *args, **kwargs):
        return pathlib.Path(self._data[dtype]['path'])

    def load_handlers(self, *args, **kwargs):
        from heinlein.dtypes import handlers
        if not hasattr(self, "_handlers"):
            self._handlers =  handlers.get_file_handlers(self._data, self.external)

    @staticmethod
    def exists(name: str) -> bool:
        """
        Checks if a datset exists
        """
        return DatasetConfig.exists(name)

    @abstractmethod
    def setup(self, *args, **kwargs):
        pass

    def validate_data(self, *args, **kwargs):
        pass

    @abstractmethod
    def add_data(self, *args, **kwargs):
        pass

    @abstractmethod
    def remove_data(self, *args, **kwargs):
        pass
    
    def get_from(self, dtypes: list, region_overlaps: list, *args, **kwargs):
        return_types = []
        new_data = {}
        self.load_handlers()

        for dtype in dtypes:
            try:
                path = self._data[dtype]
                return_types.append(dtype)
            except KeyError:
                print(f"No data of type {dtype} found for dataset {self.name}!")
        cached = self.get_cached_values(dtypes, region_overlaps)
        for dtype in return_types:

            if dtype in cached.keys():
                dtype_cache = cached[dtype]
                regions_to_get = [r for r in region_overlaps if r.name not in dtype_cache.keys()]
            else:
                regions_to_get = region_overlaps
            if len(regions_to_get) != 0:
                data_ = self._handlers[dtype].get_data(regions_to_get, *args, **kwargs)
                new_data.update({dtype: data_})

        if len(new_data) != 0:
            self.cache(new_data)


        storage = {}
        keys = set(new_data.keys()).union(set(cached.keys()))

        for k in keys:
            data = cached.get(k, {})
            new_d = new_data.get(k, {})
            if new_d is None and data is None:
                path = self.get_path(k)
                storage.update({k: path})
            elif type(new_d) != dict:
                storage.update({k: new_d})
            else:
                data.update(new_d)
                storage.update({k: data})
        return storage

    def get_data(self, dtypes: list, query_region: BaseRegion, region_overlaps: list, *args, **kwargs) -> dict:
        """
        Get data of a specificed type
        The manager is responsible for finding the path, and the giving it to the handlers
        """

        storage = self.get_from(dtypes, region_overlaps, *args, **kwargs)
        storage = self.parse_data(storage, *args, **kwargs)
        return storage

    def parse_data(self, data, *args, **kwargs):
        return_data = {}
        for dtype, values in data.items():
            #Now, we process into useful objects and filter further
            if data is None:
                logger.error(f"Unable to find data of type {dtype}")
                continue
            try:
                obj_ = self._handlers[dtype].get_data_object(values)
                return_data.update({dtype: obj_})
            except IndexError:
                return_data.update({dtype: None})
        return return_data

    def get_cached_values(self, dtypes: list, region_overlaps: list):
        cached_values = {}
        with self._cache_lock:
            for dtype in dtypes:
                try:
                    dtype_cache = self._cache[dtype]
                except KeyError:
                    #No cache for this datatype, continue
                    continue
                storage = {}
                cached = dtype_cache.get_many([reg.name for reg in region_overlaps])
                cached_values.update({dtype: cached})
        return cached_values

    def cache(self, data_storage: dict):
        """
        Top-level modules think in terms of datatypes, but the cache thinks in terms of regions
        So we have to do a translation
        
        """
        with self._cache_lock:
            for dtype, data in data_storage.items():
                if (data is None) or (type(data) != dict):
                    continue
                try:
                    dtype_cache = self._cache[dtype]
                except KeyError:
                    dtype_cache = LRUCache(maxsize=0)
                    self._cache.update({dtype: dtype_cache})
                dtype_cache.add_many({reg_name: d_obj for reg_name, d_obj in data.items()})
                self._cache.update({dtype: dtype_cache})
    

    @abstractmethod
    def clear_all_data(self, *args, **kwargs):  
        pass

    @abstractmethod
    def get_handler(self, dtype: str, *args, **kwargs):
        pass
