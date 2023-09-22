import logging
import multiprocessing as mp
from abc import ABC, abstractmethod
from importlib import import_module
from inspect import getmembers, isclass, isfunction
from pathlib import Path

from cacheout import LRUCache
from godata import create_project, has_collection, has_project, load_project
from godata.project import GodataProjectError

from heinlein.config.config import globalConfig
from heinlein.locations import BASE_DATASET_CONFIG_DIR
from heinlein.region.base import BaseRegion
from heinlein.utilities import warning_prompt_tf

logger = logging.getLogger("manager")


def check_overload(f):
    def wrapper(self, *args, **kwargs):
        bypass = kwargs.get("bypass", False)
        if self.external is None or bypass:
            return f(self, *args, **kwargs)
        else:
            try:
                ext_fn = self._external_definitions[f.__name__]
                return ext_fn(self, *args, **kwargs)
            except KeyError:
                return f(self, *args, **kwargs)

    return wrapper


def get_default_config(name: str) -> Path:
    """
    Returns the default config for a dataset
    """
    path = BASE_DATASET_CONFIG_DIR / f"{name}.json"
    if not path.exists():
        path = BASE_DATASET_CONFIG_DIR / "default.json"
    return path


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

    def get_config(self):
        return self.config.get("config")

    def _setup(self, *args, **kwargs) -> None:
        """
        Performs basic setup of the manager
        Loads datset config if it exists, or prompts
        user if dataset does not exist.
        """

        if not has_collection(".heinlein") or not has_project(
            self.name, ".heinlein"
        ):  # If this dataset does not exist
            if self.globalConfig.interactive:
                write_new = warning_prompt_tf(
                    f"Survey {self.name} not found, would you like to initialize it? "
                )
                if write_new:
                    self.config = create_project(self.name, ".heinlein")
                    config_path = get_default_config(self.name)
                    self.config.store(config_path, "config")

                else:
                    self.ready = False
            else:
                raise OSError(f"Dataset {self.name} does not exist!")

        else:  # If it DOES exist, get the config data
            self.config = load_project(self.name, ".heinlein")
            try:
                # Find the external implementation for this dataset, if it exists.
                cfg = self.config.get("config")
                self.external = import_module(f".{cfg['slug']}", "heinlein.dataset")
            except KeyError:
                self.external = None
            self._initialize_external_implementation()

    def _initialize_external_implementation(self):
        if self.external is None:
            self._external_definitions = {}
            return
        fns = [f for f in getmembers(self.external, isfunction)]
        fns = list(
            filter(lambda f, m=self.external: f[1].__module__ == m.__name__, fns)
        )
        external_functions = {fn[0]: fn[1] for fn in fns}

        classes = [f for f in getmembers(self.external, isclass)]
        classes = list(
            filter(lambda f, m=self.external: f[1].__module__ == m.__name__, classes)
        )
        external_classes = {cl[0]: cl[1] for cl in classes}

        fn_keys = set(external_functions.keys())
        cls_keys = set(external_classes.keys())
        if len(fn_keys.intersection(cls_keys)) != 0:
            print(
                "Error: Overloaded functions and classes in dataset implementations"
                "Should all have unique names, but found duplicates for {keys_}"
            )
            exit()
        self._external_definitions = {**external_classes, **external_functions}

    def get_external(self, key, *args, **kwargs):
        return self._external_definitions.get(key, None)

    def get_path(self, dtype: str, *args, **kwargs):
        return self.config.get(f"data/{dtype}", as_path=True)

    def load_handlers(self, *args, **kwargs):
        from heinlein.dtypes import handlers

        if not hasattr(self, "_handlers"):
            known_dtypes_ = self.config.list("data")
            known_dtypes = []
            for ff in known_dtypes_.values():
                known_dtypes.extend(ff)
            self._handlers = handlers.get_file_handlers(
                known_dtypes, self.config, self._external_definitions
            )

    @staticmethod
    def exists(name: str) -> bool:
        """
        Checks if a datset exists
        """
        try:
            return has_project(name, ".heinlein")
        except GodataProjectError:  # Need to eport the GodataProjectError here
            return False

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

    @check_overload
    def get_from(self, dtypes: list, region_overlaps: list, *args, **kwargs):
        return_types = []
        new_data = {}
        if not isinstance(region_overlaps[0], str):
            regnames = [r.name for r in region_overlaps]
        else:
            regnames = region_overlaps

        self.load_handlers()

        for dtype in dtypes:
            try:
                path = self.config.has_path(f"data/{dtype}")
                return_types.append(dtype)
            except KeyError:
                print(f"No data of type {dtype} found for dataset {self.name}!")
        cached = self.get_cached_values(dtypes, regnames)
        for dtype in return_types:
            if dtype in cached.keys():
                dtype_cache = cached[dtype]
                regions_to_get = [r for r in regnames if r not in dtype_cache.keys()]
            else:
                regions_to_get = regnames
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
            elif not isinstance(new_d, dict):
                storage.update({k: new_d})
            else:
                data.update(new_d)
                storage.update({k: data})
        return storage

    @check_overload
    def get_data(
        self,
        dtypes: list,
        query_region: BaseRegion,
        region_overlaps: list,
        *args,
        **kwargs,
    ) -> dict:
        """
        Get data of a specificed type
        The manager is responsible for finding the path, and the giving
        it to the handlers
        """

        storage = self.get_from(dtypes, region_overlaps, *args, **kwargs)
        storage = self.parse_data(storage, *args, **kwargs)
        return storage

    def load(self, regions: list, dtypes: list, *args, **kwargs):
        """
        Loads data for particular named regions into the cache
        """
        self.get_from(dtypes, regions)

    def dump(self, regions: list, *args, **kwargs):
        """
        Dumps data for some particular named regions from the cache
        """
        for dtype, data in self._cache.items():
            nd = data.delete_many(regions)
            logging.info(f"Delete {nd} items from the {dtype} cache")

    def dump_all(self):
        for dtype, data in self._cache.items():
            nd = data.clear()
            logging.info(f"Delete {nd} items from the {dtype} cache")

    def parse_data(self, data, *args, **kwargs):
        return_data = {}
        for dtype, values in data.items():
            # Now, we process into useful objects and filter further
            if data is None:
                logger.error(f"Unable to find data of type {dtype}")
                continue
            try:
                objs = list(values.values())
                data_obj = objs[0].combine(objs)
                return_data.update({dtype: data_obj})
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
                    # No cache for this datatype, continue
                    continue
                cached = dtype_cache.get_many(region_overlaps)
                cached_values.update({dtype: cached})
        return cached_values

    def cache(self, data_storage: dict):
        """
        Top-level modules think in terms of datatypes, but the cache thinks in terms
        of regions so we have to do a translation

        """
        with self._cache_lock:
            for dtype, data in data_storage.items():
                if (data is None) or not isinstance(data, dict):
                    continue
                try:
                    dtype_cache = self._cache[dtype]
                except KeyError:
                    dtype_cache = LRUCache(maxsize=0)
                    self._cache.update({dtype: dtype_cache})
                dtype_cache.add_many(
                    {reg_name: d_obj for reg_name, d_obj in data.items()}
                )
                self._cache.update({dtype: dtype_cache})

    @abstractmethod
    def clear_all_data(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_handler(self, dtype: str, *args, **kwargs):
        pass
