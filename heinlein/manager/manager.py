import json
import logging
import multiprocessing as mp
from functools import cache
from importlib import import_module
from inspect import getmembers, isclass, isfunction
from pathlib import Path
from types import ModuleType

import appdirs
from cacheout import LRUCache

from heinlein.config.config import globalConfig
from heinlein.region.base import BaseRegion
from heinlein.utilities import warning_prompt

logger = logging.getLogger("manager")
known_datasets = ["des", "cfht", "hsc", "ms"]
active_managers = {}


def get_manager(name):
    try:
        am = active_managers[name]
        return am
    except KeyError:
        mgr = DataManager(name)
        active_managers.update({name: mgr})
        return mgr


@cache
def get_config_location():
    return Path(appdirs.user_config_dir("heinlein"))


def get_dataset_config_dir(dataset_name: str) -> Path:
    return get_config_location() / dataset_name


def initialize_dataset(name: str, *args, **kwargs):
    """
    Initializes a new dataset. Checks to see if a custom implementation exists for a
    given dataset. These have to be installed separately from the main package.
    """
    print(f"Initializing dataset {name}...")
    ext = get_external_implementation(name)
    config_data = ext.load_config()
    config_location = get_dataset_config_dir(name)
    config_location.mkdir(parents=True, exist_ok=True)
    config_data.update({"data": {}})
    with open(config_location / "config.json", "w") as f:
        json.dump(config_data, f)


def get_external_implementation(name: str) -> ModuleType:
    """
    Checks to see if a custom implementation exists for a given dataset. These have
    to be installed separately from the main package. Prompts the user to install
    the package if it is not found, but is known.
    """
    if name not in known_datasets:
        raise ValueError(f"Dataset {name} is not supported!")
    else:
        # try to import it
        module_name = "heinlein_" + name
        try:
            module = import_module(module_name)
        except ImportError:
            print(
                f"Dataset `{name}` is a known dataset, but needs to be installed"
                f" separately. You can install it with `pip install heinlein[{name}]`."
            )
            exit()
        return getattr(module, name)


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


def get_dataset_config(dataset_name: str) -> dict:
    config_location = get_dataset_config_dir(dataset_name)
    if not config_location.exists():
        raise FileNotFoundError(f"Dataset {dataset_name} has not been initialized!")
    with open(config_location / "config.json", "r") as f:
        config_data = json.load(f)
    return config_data


def write_dataset_config(dataset_name: str, config_data: dict) -> None:
    config_location = get_dataset_config_dir(dataset_name)
    if not config_location.exists():
        raise FileNotFoundError(f"Dataset {dataset_name} has not been initialized!")
    with open(config_location / "config.json", "w") as f:
        json.dump(config_data, f)


logger = logging.getLogger("manager")


class DataManager:
    def __init__(self, name, *args, **kwargs):
        """
        The datamanger is a fairly thin wrapper around godata to track where data is
        and store configuration.

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
        try:
            # Find the external implementation for this dataset, if it exists.
            self.external = get_external_implementation(self.name)
        except KeyError:
            self.external = None
        self._initialize_external_implementation()

        self.config = get_dataset_config(self.name)

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
        data = self.config.get("data", {})
        if dtype not in data:
            raise KeyError(f"Datatype {dtype} not found for dataset {self.name}!")
        return Path(data[dtype])

    def load_handlers(self, *args, **kwargs):
        from heinlein.dtypes import handlers

        if not hasattr(self, "_handlers"):
            data = self.config.get("data", {})
            known_dtypes = list(data.keys())
            self._handlers = handlers.get_file_handlers(
                known_dtypes, self.config, self._external_definitions
            )

    @staticmethod
    def exists(name: str) -> bool:
        """
        Checks if a datset exists
        """
        try:
            get_dataset_config(name)
            return True
        except FileNotFoundError:
            return False

    def add_data(self, dtype: str, path: Path, overwrite=False) -> bool:
        """
        Add data to a datset. Note that this only gives the manager
        a path to the data. The manager itself does not know what kind
        of data it is or how to use it. Usually this will be invoked
        by a command line script.

        Params:

        dtype <str>: Type of data being added (i.e. "catalog")
        path <pathlib.Path>: Path to the data

        Returns:

        bool: Whether or not the file was sucessfully added
        """
        data = self.config.get("data", {})
        if dtype in data and not overwrite:
            msg = f"Datatype {dtype} already found for survey {self.name}."
            options = ["Overwrite", "Merge", "Abort"]
            choice = warning_prompt(msg, options)
            if choice == "A":
                return False
            elif choice == "M":
                raise NotImplementedError
        if not path.exists():
            print(f"Error: File {path} does not exist!")
            return False

        data.update({dtype: str(path)})
        self.config.update({"data": data})
        write_dataset_config(self.name, self.config)
        return True

    def remove_data(self, dtype: str) -> bool:
        """
        Remove data from a datset. Usually this will be invoked
        by a command line script.

        Params:

        dtype <str>: Type of data being added (i.e. "catalog")

        Returns:

        bool: Whether or not the file was sucessfully removed
        """
        data = self.config.get("data", {})
        if dtype not in data:
            print(f"Error: Datatype {dtype} not found for survey {self.name}.")
            return False
        del data[dtype]
        self.config.update({"data": data})
        write_dataset_config(self.name, self.config)
        return True

    @check_overload
    def get_from(self, dtypes: list, region_overlaps: list, *args, **kwargs):
        return_types = []
        new_data = {}
        if not isinstance(region_overlaps[0], str):
            regnames = [r.name for r in region_overlaps]
        else:
            regnames = region_overlaps

        self.load_handlers()
        data = self.config.get("data", {})
        for dtype in dtypes:
            try:
                path = data[dtype]
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

    def get_handler(self, dtype: str, *args, **kwargs):
        pass

    def clear_all_data(self, *args, **kwargs) -> None:
        self.config.data = {}
        write_dataset_config(self.name, self.config)
        return
