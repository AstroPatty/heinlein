from abc import abstractmethod
from glob import glob
import json
from os import stat
from heinlein.locations import BASE_DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, BUILTIN_DTYPES
from abc import ABC
from heinlein.region.base import BaseRegion
from heinlein.utilities import warning_prompt, warning_prompt_tf
from heinlein.config.config import globalConfig
import numpy as np
from typing import Any
import logging
import pathlib
import shutil
import atexit

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
        
        """
        self.name = name
        self.globalConfig = globalConfig
        self._setup()
        write_atexit = lambda x=self.config_data, y = self.config_location: write_config_atexit(x, y)
        self._cache = {}
        atexit.register(write_atexit)

    
    def _setup(self, *args, **kwargs) -> None:
        """
        Performs basic setup of the manager
        Loads datset config if it exists, or prompts
        user if dataset does not exist.
        """

        with open(MAIN_DATASET_CONFIG, "r") as f:
            surveys = json.load(f)

        if self.name not in surveys.keys():
            if self.globalConfig.interactive:
                write_new = warning_prompt_tf(f"Survey {self.name} not found, would you like to initialize it? ")
                if write_new:
                    self.config_location = self.initialize_dataset()
                else:
                    self.ready = False
            else: raise OSError(f"Dataset {self.name} does not exist!")
        else:
            cp = surveys[self.name]['config_path']
            self.config_location = DATASET_CONFIG_DIR / cp
            base_config = BASE_DATASET_CONFIG_DIR / cp
            self.config_data = self.reconcile_configs(base_config, self.config_location)
            try:
                self._data = self.config_data['data']
            except KeyError:
                self._data = {}
                self.config_data['data'] = self._data

        self.load_handlers()
        self.validate_data()

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
            return stored_config
        with open(BUILTIN_DTYPES, "r") as f:
            self._builtin_types = json.load(f)
        output = {}
        for dtype, dconfig in data.items():
            if type(dconfig) != dict:
                output.update({dtype: self._fix_dconfig(dtype, stored_config, base_config)})
            else:
                expected = set(self._builtin_types[dtype]['required_attributes'].keys())
                found = set(dconfig.keys())
                if not expected.issubset(found):
                    output.update({dtype: self._fix_dconfig(dtype, dconfig, base_config)})
                else:
                    output.update({dtype: dconfig})
        return output

    def _fix_dconfig(self, dtype: str, stored_survey_config: dict, base_survey_config: dict):
        base_config = self._builtin_types[dtype]
        return_values = {}
        dconfig = stored_survey_config['data'][dtype]
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
        from heinlein.dtypes import get_file_handlers
        self._handlers =  get_file_handlers(self.data)

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

    def get_data(self, dtypes: list, query_region: BaseRegion, region_overlaps: list, *args, **kwargs) -> dict:
        """
        Get data of a specificed type
        The manager is responsible for finding the path, and the giving it to the handlers
        """

        return_types = []
        new_data = {}
        
        cached = self.get_cached_values(dtypes, region_overlaps)


        for dtype in dtypes:
            try:
                path = self._data[dtype]
                return_types.append(dtype)
            except KeyError:
                new_data.update({dtype: None})

        for dtype in return_types:
            if dtype in cached.keys():
                dtype_cache = cached[dtype]
                regions_to_get = [r.name for r in region_overlaps if r.name not in dtype_cache.keys()]
            else:
                regions_to_get = region_overlaps

            if len(regions_to_get) != 0:
                data_ = self._handlers[dtype].get_data(regions_to_get)
                new_data.update({dtype: data_})

        if len(new_data) != 0:
            self.cache(new_data)

        storage = {}
        keys = set(new_data.keys()).union(set(cached.keys()))

        for k in keys:
            data = cached.get(k, {})
            new_d = new_data.get(k, {})
            data.update(new_d)
            storage.update({k: data})

        return storage
    
    def get_cached_values(self, dtypes: list, region_overlaps: list):
        cached_values = {}
        for dtype in dtypes:
            try:
                dtype_cache = self._cache[dtype]
            except KeyError:
                #No cache for this datatype, continue
                continue
            storage = {}
            for reg in region_overlaps:
                try:
                    data = dtype_cache[reg.name]
                    storage.update({reg.name: data})
                except KeyError:
                    continue
            cached_values.update({dtype: storage})
        return cached_values

    def cache(self, data_storage: dict):
        for dtype, data in data_storage.items():
            dtype_cache = self._cache.get(dtype, {})
            dtype_cache.update({reg_name: d_obj for reg_name, d_obj in data.items()})
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