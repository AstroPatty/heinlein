import json
import pathlib
import logging
from abc import abstractmethod
from pkgutil import get_data
from sys import implementation
from importlib import import_module
import numpy as np
from xml.dom.minidom import Attr

from heinlein.region import BaseRegion, Region
from heinlein.data import get_handler


logger = logging.getLogger("Dataset")

class Dataset:

    def __init__(self, config, *args, **kwargs):
        self.__dict__.update(config)

    def setup(self, *args, **kwargs) -> None:
        try:
            setup = getattr(self._ext, "setup")
            setup(self)
            self._validate_setup()
        except AttributeError:
            raise NotImplementedError("Dataset {self.name} does not have a setup method!")

    def _validate_setup(self, *args, **kwargs):
        try:
            regions = self._regions
        except AttributeError:
            logging.error(f"No region found for surve {self.name}")

    def get_region_overlaps(self, other: BaseRegion, *args, **kwargs):
        """
        Find the subregions inside a dataset that overlap with a given region
        """
        mask = np.array([other.overlaps(r) for r in self._regions])
        return self._regions[mask]

    def get_data_from_region(self, region: BaseRegion, dtypes="catalog", *args, **kwargs):
        overlaps = self.get_region_overlaps(region, *args, **kwargs)
        data = {}
        if type(dtypes) == str:
            dtypes = [dtypes]
        for t in dtypes:
            handler = get_handler(self._ext, overlaps, t)
            data.update({t: handler()})
        return data


def load_dataset(name: str) -> Dataset:
    config = load_dataset_config(name)
    s = Dataset(config)
    return update_dataset_object(s)

def load_dataset_config(name: str) -> dict:
    self_path = pathlib.Path(__file__)
    config_path = self_path.parents[0] / "configs"
    registered_datasets_path = config_path / "datasets.json"
    with open(registered_datasets_path) as rsf:
        try:
            data = json.load(rsf)
            path = data[name]['config_path']
        except KeyError:
            logger.error(f"Unable to find a config for dataset {name}")
            return None
    
    with open(config_path / path) as scf:
        dataset_config = json.load(scf)
        if validate_dataset_config(dataset_config, config_path):
            dataset_config.update({'slug': name})
            return dataset_config
        else:
            return None        

def validate_dataset_config(config: dict, config_path: pathlib.Path) -> bool:
    default_config_path = config_path / "default.json"
    with open(default_config_path) as f:
        default_config = json.load(f)

    default_keys = set(default_config.keys())
    passed_keys = set(config.keys())

    if passed_keys != default_keys:
        missing = default_keys.difference(passed_keys)
        logger.error("The config file did not contain some required keys!")
        logger.error(f"Missing keys: {list(missing)}")
        return False
    
    return True

def update_dataset_object(obj, *args, **kwargs):
    mod = import_module(obj.slug)
    obj._ext = mod
    obj.setup()
    return obj
    