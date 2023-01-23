import json

from heinlein.locations import BASE_DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR, BUILTIN_DTYPES
import portalocker
from importlib import import_module
import atexit
from functools import singledispatchmethod
from typing import Union, List
import shutil
from copy import copy


def get_config_paths():
    base_config_location = BASE_DATASET_CONFIG_DIR / "surveys.json"
    stored_config_location = MAIN_DATASET_CONFIG
    with open(stored_config_location, "r") as f2:
        stored_config = json.load(f2)


    return stored_config


def write_config(config, path):
    with open(path, 'w') as f:
        json.dump(config, f, indent=4)


class DatasetConfig:
    surveys = get_config_paths()
    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        self.setup()
        write_atexit = lambda x=self.config, y = self.config_path: write_config(x, y)
        atexit.register(write_atexit)

    @classmethod
    def reload_datasets(cls, *args, **kwargs):
        cls.surveys = get_config_paths()

    @classmethod
    def load(cls, name, *args, **kwargs):
        if name not in DatasetConfig.surveys.keys():
            print(f"Error: dataset {name} not found")
            return
        return cls(name)
    
    @classmethod
    def create(cls, name):
        if name in DatasetConfig.surveys.keys():
            print(f"Error: dataset {name} already exists!")
            return

        default_survey_config_location = DATASET_CONFIG_DIR / "default.json"
        if not default_survey_config_location.exists():
            shutil.copy(BASE_DATASET_CONFIG_DIR / "default.json", default_survey_config_location)
        with open(default_survey_config_location, "r") as f:
            default_survey_config = json.load(f)
        
        default_survey_config.update({'name': name, "survey_region": "None", "implementation": False})
        output_location = DATASET_CONFIG_DIR / f"{name}.json"
        with open(output_location, "w") as f:
            json.dump(default_survey_config, f, indent=4)

        all_survey_config_location = DATASET_CONFIG_DIR / "surveys.json"
        with open(all_survey_config_location, "r+") as f:
            data = json.load(f)
            f.seek(0)
            f.truncate(0)
            data.update({name: {'config_path': f"{name}.json"}})
            json.dump(data, f, indent=4)

        cls.reload_datasets()
        return cls.load(name)

    @property
    def data(self):
        """
        Warning, returns a copy
        """
        d = copy(self._data)
        for k in self._data.keys():
            try:
                df = self._base_config['dconfig'][k]
                d[k].update({"config": df})
            except KeyError:
                continue
        return d

    def add_data(self, dtype, path):
        data_ = self._data.get(dtype, False)
        if not data_:
            self._data.update({dtype: {"path": path}})
        else:
            self._data[dtype].update({"path": path})
        return self.data

    def validate_data(self, *args, **kwargs):
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
        
    def setup(self, *args, **kwargs):
        self.reconcile_configs()
        try:
            self._data = self.config_data['data']
        except KeyError:
            self._data = {}
            self.config_data['data'] = self._data
        try:
            #Find the external implementation for this dataset, if it exists.
            self.external = import_module(f".{self['slug']}", "heinlein.dataset")
        except KeyError:
            self.external = None
    
    def reconcile_configs(self, *args, **kwargs):
        cp = self.surveys[self.name]["config_path"]
        base_config_path = BASE_DATASET_CONFIG_DIR / cp
        stored_config_path = DATASET_CONFIG_DIR / cp
        
        try:
            with open(base_config_path, "r") as f:
                base_config = json.load(f)
        except FileNotFoundError:
            base_config = {}

        with open(stored_config_path, "r") as f:
            stored_config = json.load(f)

        for key in base_config.keys():
            if key in ["overwrite", "data"]:
                continue
            else:
                stored_config.pop(key, False)
        try:
            self.overwritten_items = stored_config["overwrite"]
        except KeyError:
            self.overwritten_items = {}
            stored_config["overwrite"] = self.overwritten_items
        try:
            dconfig = stored_config["dconfig"]
        except KeyError:
            stored_config["dconfig"] = {}

        self.config_data = stored_config
        self.config_path = stored_config_path
        self._base_config = base_config

    @staticmethod
    def exists(name):
        return name in DatasetConfig.surveys.keys()

    @property
    def config(self, *args, **kwargs):
        return self.config_data

    @singledispatchmethod
    def __getitem__(self, __name: str):
        try:
            return self.overwritten_items[__name]
        except KeyError:
            try:
                return self._base_config[__name]
            except KeyError:
                return self.config[__name]

    @__getitem__.register
    def _(self, __name: list):
        item = self.overwritten_items
        try:
            for n in __name:
                item = item[n]
            return item
        except KeyError:
            item = self.config
            try:
                for n in __name:
                    item = item[n]
                return item
            except KeyError:
                item = self._base_config
                for n in __name:
                    item = item[n]
                return item

    @singledispatchmethod
    def set_overwrite(self, key: str, value: str):
        new_key = ["dconfig", key]
        self._set_overwrite(new_key, value)

    @set_overwrite.register
    def _(self, key: list, value: str):
        new_key = ["dconfig", *key]
        self._set_overwrite(new_key, value)
    
    @singledispatchmethod
    def check_overwrite(self, key: str):
        new_key = ["dconfig", key]
        return self._check_overwrite(new_key)

    @check_overwrite.register
    def _(self, key: list):
        new_key = ["dconfig", *key]
        return self._check_overwrite(new_key)
 
    def _check_overwrite(self, key: List[str]):
        item = self['overwrite']
        try:
            for key_ in key[:-1]:
                item = item[key_]
            return item.get(key[-1], None)
        except KeyError:
            return None        

    @singledispatchmethod
    def remove_overwrite(self, key: str):
        new_key = ["dconfig", key]
        self._remove_overwrite(new_key)

    @remove_overwrite.register
    def _(self, key: list):
        new_key = ["dconfig", *key]
        self._remove_overwrite(new_key)
    
    def _remove_overwrite(self, key: str):
        if self._check_overwrite(key) is None:
            print(f"Error: key {key} is not overwritten!")
            return
        item = self['overwrite']
        for key_ in key[:-1]:
            item = item[key_]
        item.pop(key[-1], None)
        

    def _set_overwrite(self, key, value):
        try:
            current_value = self[key]
        except KeyError:
            print(f"set_overwrite currently only supports values defined in the data config, but got {key[1:]}")

        try:
            overwrite_dconfig = self.overwritten_items['dconfig']
        except KeyError:
            overwrite_dconfig = {}
            self.overwritten_items['dconfig'] = overwrite_dconfig

        for key_ in key[1:-1]:
            try:
                overwrite_dconfig = overwrite_dconfig[key_]
            except KeyError:
                overwrite_dconfig[key_] = {}
                overwrite_dconfig = overwrite_dconfig[key_]
        
        overwrite_dconfig.update({key[-1]: value})
                  