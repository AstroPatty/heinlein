from __future__ import annotations
from abc import ABC
import logging
from typing import Any
from xml.dom.minidom import Attr
from shapely.strtree import STRtree
import numpy as np
from functools import partial
from shapely.geometry import Polygon
import json

from heinlein.locations import MAIN_CONFIG_DIR
logger = logging.getLogger("region")
class BaseRegion(ABC):

    def __init__(self, geometry, type, name, *args, **kwargs):
        """
        Base region object. Placed in its own file to get around
        circular imports
        """
        self._spherical_geometry = geometry
        self._type = type
        self.name = name
        self.setup()

    def setup(self, *args, **kwargs):
        self._cache = {}
        self._subregions = np.array([], dtype=object)
        self._covered = False
        config_location = MAIN_CONFIG_DIR / "region.json"
        with open(config_location, "r") as f:
            self._config = json.load(f)
        points = self._spherical_geometry.points
        self._flat_geometry = Polygon(points)

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getattr__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions
        """
        try:
            attr = getattr(self._flat_geometry, __name)
            return attr
        except AttributeError:
            raise AttributeError(f"{self._type} has no attribute \'{__name}\'")
        
    def _delegate_relationship(self, other: BaseRegion, method_name: str, *args, **kwargs) -> Any:
        attr = getattr(self._geometry, method_name)
        return attr(other)
    
    def add_subregions(self, subregions: dict, overwrite=False, *args, **kwargs):
        for name, region in subregions.items():
            self.add_subregion(name, region, overwrite, *args, **kwargs)
        self._build_region_tree()

    def add_subregion(self, name: str, subregion: BaseRegion, overwrite=False, ignore_warnings = False) -> None:
        """
        Adds a subregion to a region. These can be used to more finely filter a dataset,
        if necessary. The subregion must be entirely contained within the original region.

        Paramaters:
        name <str>: A name for the subregion
        subregion <heinlein.BaseRegion>: A region object
        
        """
        if not self.contains(subregion) and not ignore_warnings:
            logger.error("A subregion must be entirely contained within its superregion!")
            return False

        self._subregions = np.append(self._subregions, [subregion])
        return True


    def _build_region_tree(self, *args, **kwargs) -> None:
        """
        For larger surveys, we subidivide into smaller regions for easier
        querying. Shapely implements a tree-based searching algorithm for 
        finding region overlaps, so we create that tree here.
        """
        regions = np.empty(len(self._subregions), dtype=object)
        indices = {}
        for idx, reg in enumerate(self._subregions):
            geos = reg.geometry
            indices.update({id(geo): idx for geo in geos})
            regions[idx] = np.asarray(geos, dtype=object)
        
        geo_list = np.hstack(regions)
        self._geo_idx = indices
        self._geo_tree = STRtree(geo_list)
    
    def get_subregion_overlaps(self, other: BaseRegion, recursive = False, *args, **kwargs) -> list:
        """
        Find the subregions inside a dataset that overlap with a given region
        Uses the shapely STRTree for speed.
        """
        if len(self._subregions) == 0:
            return None
        region_overlaps = np.asarray([self._geo_tree.query(geo) for geo in other.geometry], dtype = "object")
        region_overlaps = np.hstack(region_overlaps)
        idxs = np.unique(np.asarray([self._geo_idx[id(reg)] for reg in region_overlaps]))
        if idxs.size == 0:
            return None
        subregion_overlaps = self._subregions[idxs]

        if not recursive:
            return {sr: None for sr in subregion_overlaps}

        overlaps = {reg: reg.get_subregion_overlaps(other) for reg in subregion_overlaps}
        #Note setting recursive=False here ensures our subdivision is never more than two layers deep
        return overlaps



    @property
    def geometry(self, *args, **kwargs):
        return self._flat_geometry
    
    @property
    def spherical_geometry(self):
        return self._spherical_geometry

    @property
    def type(self) -> str:
        return self._type

    def center(self, *args, **kwargs):
        pass

    def cache(self, ref: Any, dtype: str) -> None:
        self._cache.update({dtype: ref})

    def get_data(self, handlers: dict, dtypes: list, query_region: BaseRegion, *args, **kwargs) -> None:
        if len(self._subregions) == 0:
            return self._get_data(handlers, dtypes, query_region, *args, **kwargs)

        overlaps = self.get_subregion_overlaps(query_region, recursive=True)
        
        subregion_storage = {}
        for region, subregions in overlaps.items():
            storage = {dtype: [] for dtype in dtypes}

            if subregions is None:
                d = region._get_data(handlers, dtypes, query_region, *args, **kwargs)
                for key, d_ in d.items():
                    storage[key] = d_
                    subregion_storage.update({region.name: storage})
            else:
                for sr in subregions:
                    storage_ = {}
                    d = sr._get_data(handlers, dtypes, query_region, parent_region = region)
                    for key, d_ in d.items():
                        storage_.update({key: d_})
                    subregion_storage.update({sr.name: storage_})
        
        return_data = {}
        for dtype in dtypes:
            values = [v[dtype] for v in subregion_storage.values()]
            return_data.update({dtype: values})

        return return_data


    def _get_data(self, handlers: dict, dtypes: list, query_region: BaseRegion, *args, **kwargs) -> dict:
        data_storage = {}
        for dtype in dtypes:

            try:
                data_storage.update({dtype: self._cache[dtype]})
            except KeyError:
                data = handlers[dtype].get_data(self, *args, **kwargs)
                self.cache(data, dtype)
                data_storage.update({dtype: data})
        return data_storage

