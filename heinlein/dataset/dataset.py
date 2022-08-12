import logging
from importlib import import_module
import numpy as np
from typing import Union
from heinlein import region

from heinlein.manager.dataManger import DataManager

from heinlein.region import BaseRegion
from heinlein.dtypes import get_data_object
from heinlein.manager import get_manager

from shapely.strtree import STRtree


logger = logging.getLogger("Dataset")

class Dataset:

    def __init__(self, manager: DataManager, *args, **kwargs):
        self.manager = manager
        self.config = manager.config
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """
        Searches for an external implementation of the datset
        This is used for datasets with specific needs (i.e. specific surveys)
        """
        external = self.config['implementation']
        if not external:
            return
        
        try:
            self.external = import_module(f".{self.config['slug']}", "heinlein.dataset")
        except KeyError:
            raise ModuleNotFoundError(f"Pointer to {self.config['name']} implementation not found in config!")

        try:
            setup_f = getattr(self.external, "setup")
            setup_f(self)
            self._validate_setup()
        except AttributeError:
            raise NotImplementedError("Dataset {self.name} does not have a setup method!")
        
        self._build_region_tree()

    def _validate_setup(self, *args, **kwargs) -> None:
        try:
            regions = self._regions
            self._regions = np.array(self._regions, dtype=object)
        except AttributeError:
            logging.error(f"No region found for survey {self.name}")
    
    def _build_region_tree(self, *args, **kwargs) -> None:
        """
        For larger surveys, we subidivide into smaller regions for easier
        querying. Shapely implements a tree-based searching algorithm for 
        finding region overlaps, so we create that tree here.
        """
        geo_list = np.array([reg.geometry for reg in self._regions])
        indices = {id(geo): i for i, geo in enumerate(geo_list)}
        
        self._geo_idx = indices
        self._geo_tree = STRtree(geo_list)


    def get_region_overlaps(self, other: BaseRegion, *args, **kwargs) -> list:
        """
        Find the subregions inside a dataset that overlap with a given region
        Uses the shapely STRTree for speed.
        """
        region_overlaps = self._geo_tree.query(other.geometry)
        idxs = [id(r) for r in region_overlaps]
        return [self._regions[self._geo_idx[i]] for i in idxs]


    def get_data_from_region(self, query_region: BaseRegion, dtypes: Union[str, list] = "catalog", *args, **kwargs) -> dict:
        """
        Get data of type dtypes from a particular region
        
        Paramaters:

        region <BaseRegion> heinlein Region object
        dtypes <str> or <list>: list of data types to return
        
        """
        overlaps = self.get_region_overlaps(query_region, *args, **kwargs)
        data = {}
        if type(dtypes) == str:
            dtypes = [dtypes]
        
        data = self.manager.get_data(dtypes, query_region, overlaps)
        return_data = {}
        for dtype, values in data.items():
            #Now, we process into useful objects and filter further
            if data is None:
                logger.error(f"Unable to find data of type{dtype}")
                continue
            obj_ = get_data_object(dtype, values)
            return_data.update({dtype: obj_.get_data_from_region(query_region)})
        return return_data


def load_dataset(name: str) -> Dataset:
    manager = get_manager(name)
    return Dataset(manager)


