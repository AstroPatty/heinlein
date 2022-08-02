import json
import pathlib
import logging
from abc import abstractmethod
from pkgutil import get_data
import sys
from importlib import import_module
import numpy as np
from xml.dom.minidom import Attr
from heinlein.manager.manager import FileManager

from heinlein.region import BaseRegion, Region
from heinlein.data import get_handler
from heinlein.manager import get_manager


logger = logging.getLogger("Dataset")

class Dataset:

    def __init__(self, manager: FileManager, *args, **kwargs):
        self.manager = manager
        self.config = manager.config
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        external = self.config['implementation']
        if not external:
            return
        
        try:
            self.external = import_module(f".{self.config['slug']}", "heinlein.dataset")
        except KeyError:
            raise ModuleNotFoundError(f"Pointer to {self.config['name']} implementation not found in config!")

        try:
            setup = getattr(self.external, "setup")
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
        mask = np.array([other.intersects(r) for r in self._regions])
        return self._regions[mask]

    def get_data_from_region(self, region: BaseRegion, dtypes="catalog", *args, **kwargs):
        overlaps = self.get_region_overlaps(region, *args, **kwargs)
        handlers = {}
        data = {}
        paths = {}
        if type(dtypes) == str:
            dtypes = [dtypes]
        
        for t in dtypes:
            try: 
                p = self.manager.get_data(t)
                paths.update({t: p})
                data.update({t: []})
            except FileNotFoundError:
                logger.error(f"Path to data type {t} not found, skipping...")
                
        for t in dtypes:
            handler = get_handler(self.external, t)
            handlers.update({t: handler})
        
        for reg in overlaps:
            reg.get_data(handlers, paths, data)

        return data


def load_dataset(name: str) -> Dataset:
    manager = get_manager(name)
    return Dataset(manager)
    
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

if __name__ == "__main__":
    import astropy.units as u
    region = Region(center = (13.4349, -19.972222), radius = 120*u.arcsec)
    d = load_dataset("des")
    data = d.get_data_from_region(region, "catalog")
    print(data)