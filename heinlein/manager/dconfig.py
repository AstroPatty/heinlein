import json

from numpy import single
from heinlein.locations import BASE_DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR
import portalocker
from importlib import import_module
import atexit
from functools import singledispatchmethod
from typing import Union, List

def load_datset_config(name):
    if name not in DatasetConfig.surveys.keys():
        print(f"Error: dataset {name} not found")
        return
    return DatasetConfig(name)

def initialize_dataset_config(name):
    if name in DatasetConfig.surveys.keys():
        print(f"Error: dataset {name} already exists!")
        return
    return DatasetConfig.create(name)

def get_config_paths():
    base_config_location = BASE_DATASET_CONFIG_DIR / "surveys.json"
    stored_config_location = MAIN_DATASET_CONFIG
    with open(base_config_location, "rb") as f:
        base_config = json.load(f)

    with open(stored_config_location, "r") as f2:
        stored_config = json.load(f2)

    for key, value in base_config.items():
        if key not in stored_config.keys():
            stored_config.update({key: value})

    with portalocker.Lock(stored_config_location, "w") as f:
        json.dump(stored_config, f, indent=4)


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

    def setup(self, *args, **kwargs):
        cp = self.surveys[self.name]['config_path']
        self.reconcile_configs()
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
    
    def reconcile_configs(self, *args, **kwargs):
        cp = self.surveys[self.name]["config_path"]
        base_config_path = BASE_DATASET_CONFIG_DIR / cp
        stored_config_path = DATASET_CONFIG_DIR / cp
        
        with open(base_config_path, "r") as f:
            base_config = json.load(f)
        with open(stored_config_path, "r") as f:
            stored_config = json.load(f)
        
        for key, base_values in base_config.items():
            if key == "overwrite":
                continue
            else:
                stored_config.pop(key, False)
        try:
            self.overwritten_items = stored_config["overwrite"]
        except KeyError:
            self.overwritten_items = {}
            stored_config["overwrite"] = self.overwritten_items
        self.config_data = stored_config
        self.config_path = stored_config_path
        self._base_config = base_config

    @staticmethod
    def exists(name):
        return name in DatasetConfig.surveys.keys()

    @classmethod
    def create(cls, name, *args, **kwargs):
        pass

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
    