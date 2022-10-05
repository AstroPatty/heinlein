from abc import abstractmethod
from importlib import import_module
import json

import portalocker
from heinlein.locations import BASE_DATASET_CONFIG_DIR, DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, BUILTIN_DTYPES
from abc import ABC
from heinlein.region.base import BaseRegion
from heinlein.utilities import warning_prompt_tf
from heinlein.config.config import globalConfig
import multiprocessing as mp
import logging
import pathlib
import shutil
import atexit
from cacheout import LRUCache

logger = logging.getLogger("manager")


def write_config_atexit(config, path):
    with open(path, 'w') as f:
        json.dump(config, f, indent=4)


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

        write_atexit = lambda x=self.config_data, y = self.config_location: write_config_atexit(x, y)
        atexit.register(write_atexit)

    
    def _setup(self, *args, **kwargs) -> None:
        """
        Performs basic setup of the manager
        Loads datset config if it exists, or prompts
        user if dataset does not exist.
        """

        surveys = self.get_config_paths()

        if self.name not in surveys.keys(): #If this dataset does not exist
            if self.globalConfig.interactive:
                write_new = warning_prompt_tf(f"Survey {self.name} not found, would you like to initialize it? ")
                if write_new:
                    self.config_location = self.initialize_dataset()
                else:
                    self.ready = False
            else: raise OSError(f"Dataset {self.name} does not exist!")
        else: #If it DOES exist, get the config data
            cp = surveys[self.name]['config_path']
            self.config_location = DATASET_CONFIG_DIR / cp
            base_config = BASE_DATASET_CONFIG_DIR / cp
            self.config_data = self.reconcile_configs(base_config, self.config_location)
            try:
                self._data = self.config_data['data']
            except KeyError:
                self._data = {}
                self.config_data['data'] = self._data
        try:
            #Find the external implementation for this dataset, if it exists.
            self.external = import_module(f".{self.config['slug']}", "heinlein.dataset")
        except KeyError:
            self.external = None
        self.validate_data()
    
    def get_config_paths(self):
        base_config_location = BASE_DATASET_CONFIG_DIR / "surveys.json"
        stored_config_location = MAIN_DATASET_CONFIG
        with open(base_config_location, "rb") as f:
            base_config = json.load(f)

        with open(stored_config_location, "r") as f2:
            stored_config = json.load(f2)

        with open(stored_config_location, "r") as f2:
            stored_config = json.load(f2)
        for key, value in base_config.items():
            if key not in stored_config.keys():
                stored_config.update({key: value})

        with portalocker.Lock(stored_config_location, "w") as f:
            json.dump(stored_config, f, indent=4)
        return stored_config


    def get_path(self, dtype: str, *args, **kwargs):
        return pathlib.Path(self._data[dtype]['path'])


    def validate_data(self, * gargs, **kwargs):
        with open(BUILTIN_DTYPES, "r") as f:
            self._dtype_config = json.load(f)
        
        for dtype, dconfig in self._data.items():
            if dtype not in self._dtype_config.keys():
                continue
            if type(dconfig) != dict:
                self._update_dconfig(dtype)
            else:
                required_values = set(self._dtype_config[dtype]['required_attributes'].keys())
                found_values = set(dconfig.keys())
                if not required_values.issubset(found_values):
                    self._update_dconfig(dtype)
        

    def reconcile_configs(self, base_path, config_path) -> dict:
        """
        Reconciles the base config file with the current version stored outside the package
        Ensures new config entries added by developors are propogated correctly
        Returns the reconciled version
        """
        with open(base_path, "r") as f:
            base_config_data = json.load(f)
        if base_path.exists() and not config_path.exists():
            shutil.copy(base_path, config_path)
            return base_config_data
        
        with open(config_path, "r") as f:
            stored_config_data = json.load(f)
        update = {k: v for k, v in base_config_data.items() if k not in ["data", "dconfig"]}
        stored_config_data.update(update)
        if 'data' in stored_config_data.keys():
            data_config = self.reconcile_dconfig(stored_config_data, base_config_data)
            stored_config_data.update({'data': data_config})

        return stored_config_data

    def reconcile_dconfig(self, stored_config: dict, base_config: dict, *args, **kwargs):
        data = stored_config['data']
        if len(data) == 0:
            return data
        with open(BUILTIN_DTYPES, "r") as f:
            self._builtin_types = json.load(f)
        output = {}
        stored_data_config = stored_config['data']
        for dtype, dconfig in base_config['dconfig'].items():
            if dtype not in stored_data_config.keys():
                #Case: No data of this type has been added
                continue
            if type(stored_data_config[dtype]) != dict:
                #Provided for backward compatability
                output.update({dtype: self._fix_dconfig(dtype, stored_config, base_config)})
            elif dtype not in self._builtin_types.keys():
                #This is not a built_in type
                output.update({dtype: data[dtype]})
            
            else:
                for key, value in dconfig.items():
                    if key not in stored_data_config[dtype]:
                        stored_data_config[dtype].update({key: value})
                output.update({dtype: stored_data_config[dtype]})

            expected = set(self._builtin_types[dtype]['required_attributes'].keys())
            found = set(stored_data_config[dtype].keys())
            if not expected.issubset(found):
                output.update({dtype: self._fix_dconfig(dtype, stored_data_config[dtype], base_config)})

        unconfigured = {k:v for k, v in stored_data_config.items() if k not in output.keys()}
        output.update(unconfigured)

        return output

    def _fix_dconfig(self, dtype: str, dconfig: dict, base_survey_config: dict):
        try: 
            base_config = self._builtin_types[dtype]
        except KeyError:
            base_config = {'required_attributes': {}}
        return_values = {}
        if type(dconfig) != dict:
            p = dconfig
            return_values.update({"path" : p})
        for dkey, dc in base_config['required_attributes'].items():
            if dkey in dconfig:
                return_values.update({dkey: dconfig[dkey]})
            elif dkey == 'path': 
                continue
            else:
                try:
                    survey_dtype_config = base_survey_config['dconfig'][dtype]
                    return_values.update(survey_dtype_config)
                except KeyError:
                    return_values.update({dkey: None})

        return return_values
                

        

    def load_handlers(self, *args, **kwargs):
        from heinlein.dtypes import handlers
        if not hasattr(self, "_handlers"):
            self._handlers =  handlers.get_file_handlers(self.data, self.external)

    @property
    def data(self):
        return self._data

    @abstractmethod
    def setup(self, *args, **kwargs):
        pass

    def validate_data(self, *args, **kwargs):
        pass
    
    def initialize_dataset(self, *args, **kwargs) -> pathlib.Path:
        """
        Initialize a new dataset by name.
        Creates a default configuration file.

        Returns:

        pathlib.Path: The path to the new configuration file.
        """

        default_survey_config_location = DATASET_CONFIG_DIR / "default.json"
        if not default_survey_config_location.exists():
            shutil.copy(BASE_DATASET_CONFIG_DIR / "default.json", default_survey_config_location)
        with open(default_survey_config_location, "r") as f:
            default_survey_config = json.load(f)
        
        default_survey_config.update({'name': self.name, "survey_region": "None", "implementation": False})
        output_location = DATASET_CONFIG_DIR / f"{self.name}.json"
        with open(output_location, "w") as f:
            json.dump(default_survey_config, f, indent=4)

        all_survey_config_location = DATASET_CONFIG_DIR / "surveys.json"
        with open(all_survey_config_location, "r+") as f:
            data = json.load(f)
            f.seek(0)
            f.truncate(0)
            data.update({self.name: {'config_path': f"{self.name}.json"}})
            json.dump(data, f, indent=4)
        
        self.config_data = default_survey_config
        self._data = {}
        self.ready = True
        return output_location

    @staticmethod
    def exists(name: str) -> bool:
        """
        Checks if a datset exists
        """
        with open(MAIN_DATASET_CONFIG, "r") as f:
            surveys = json.load(f)
        if name in surveys.keys():
            return True
        return False

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

def get_all():
    default_survey_config_location = DATASET_CONFIG_DIR / "surveys.json"
    with open(default_survey_config_location, "r") as f:
        surveys = json.load(f)
    missing = []
    storage = {}
    for name, vals in surveys.items():
        survey_config = DATASET_CONFIG_DIR / vals['config_path']
        try:
            with open(survey_config, "r") as f:
                    survey_data = json.load(f)
        except FileNotFoundError:
            missing.append(name)
        storage.update({name: survey_data})
    return storage  

