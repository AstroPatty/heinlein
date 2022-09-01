import logging
from importlib import import_module
import numpy as np
from typing import Union

from heinlein.manager.dataManger import DataManager

from heinlein.region import BaseRegion, Region
from heinlein.manager import get_manager

from shapely.strtree import STRtree


logger = logging.getLogger("Dataset")
class Dataset:

    def __init__(self, manager: DataManager, *args, **kwargs):
        self.manager = manager
        self.config = manager.config
        self.setup()

    @property
    def name(self):
        return self.manager.name

    def setup(self, *args, **kwargs) -> None:
        """
        Searches for an external implementation of the datset
        This is used for datasets with specific needs (i.e. specific surveys)
        """
        external = self.config['implementation']
        if not external:
            return
        
        self.external = self.manager.external
        if external is None:
            raise NotImplementedError(f"No implementation code found for datset {self.name}")
        try:
            setup_f = getattr(self.external, "setup")
            setup_f(self)
            self._validate_setup()
        except AttributeError:
            raise NotImplementedError(f"Dataset {self.name} does not have a setup method!")
        
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

    def get_path(self, dtype: str, *args, **kwargs):
        """
        Gets the path to where a particular item in a dataset is stored on disk
        """
        return self.manager.get_path(dtype)


    def get_region_overlaps(self, other: BaseRegion, *args, **kwargs) -> list:
        """
        Find the subregions inside a dataset that overlap with a given region
        Uses the shapely STRTree for speed.
        """
        region_overlaps = self._geo_tree.query(other.geometry)
        idxs = [id(r) for r in region_overlaps]
        overlaps = [self._regions[self._geo_idx[i]] for i in idxs]
        overlaps = [o for o in overlaps if o.intersects(other)]
        return overlaps

    def get_data_from_region(self, query_region: BaseRegion, dtypes: Union[str, list] = "catalog", *args, **kwargs) -> dict:
        """
        Get data of type dtypes from a particular region
        
        Paramaters:

        region <BaseRegion> heinlein Region object
        dtypes <str> or <list>: list of data types to return
        
        """
        overlaps = self.get_region_overlaps(query_region, *args, **kwargs)
        overlaps = [o for o in overlaps if o.intersects(query_region)]

        if len(overlaps) == 0:
            print("Error: No objects found in this region!")
            return
        data = {}
        if type(dtypes) == str:
            dtypes = [dtypes]
        

        data = self.manager.get_data(dtypes, query_region, overlaps)


        return_data = {}
        for dtype, obj_ in data.items():
            try:
                return_data.update({dtype: obj_.get_data_from_region(query_region)})
            except AttributeError:
                return_data.update({dtype: obj_})
        return return_data

    def cone_search(self, center, radius, *args, **kwargs):
        reg = Region.circle(center=center, radius=radius)
        return self.get_data_from_region(reg, *args, **kwargs)

def load_dataset(name: str) -> Dataset:
    manager = get_manager(name)
    return Dataset(manager)    

def load_current_config(name: str):
    manager = get_manager(name)
    return manager.config
