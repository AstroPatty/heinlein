from __future__ import annotations
from abc import ABC, abstractmethod
import logging
from reprlib import recursive_repr
from typing import Any, Tuple, Union
from shapely.affinity import translate
from shapely.strtree import STRtree
import numpy as np
from functools import partial
import json

from heinlein.locations import MAIN_CONFIG_DIR
from heinlein.manager.dataFactory import DataFactory
logger = logging.getLogger("region")
class BaseRegion(ABC):

    def __init__(self, geometry, type, *args, **kwargs):
        """
        Base region object. Placed in its own file to get around
        circular imports
        """
        self._geometry = geometry
        self._type = type
        self._validate_geometry()
        self.check_for_edges()
        self.setup()

    def setup(self, *args, **kwargs):
        self._cache = {}
        self._subregions = np.array([], dtype=object)
        self._covered = False
        config_location = MAIN_CONFIG_DIR / "region.json"
        with open(config_location, "r") as f:
            self._config = json.load(f)

    def __getattr__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions
        """
        if __name in self._config['allowed_predicates']:
            return partial(self._delegate_relationship, method_name = __name)
        else:
            raise AttributeError(f"{self._type} has no attribute \'{__name}\'")
        
    def _delegate_relationship(self, other: BaseRegion, method_name: str, *args, **kwargs) -> Any:
        for geo in self.geometry:
            for other_geo in other.geometry:
                f = getattr(geo, method_name)
                if f(other_geo, *args, **kwargs):
                    return True
        return False
    
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
        subregion_overlaps = self._subregions[idxs]

        if not recursive:
            return {sr: None for sr in subregion_overlaps}

        overlaps = {reg: reg.get_subregion_overlaps(other) for reg in subregion_overlaps}
        #Note setting recursive=False here ensures our subdivision is never more than two layers deep
        return overlaps



    @property
    def geometry(self, *args, **kwargs) -> list:
        return self._geometries

    @property
    def type(self) -> str:
        return self._type

    def center(self, *args, **kwargs):
        pass

    def cache(self, ref: Any, dtype: str) -> None:
        self._cache.update({dtype: ref})

    def get_data(self, factory: DataFactory, dtypes: list, query_region: BaseRegion, *args, **kwargs) -> None:
        if len(self._subregions) == 0:
            return self._get_data(factory, dtypes, query_region, *args, **kwargs)

        overlaps = self.get_subregion_overlaps(query_region, recursive=True)
        
        subregion_storage = {}
        for region, subregions in overlaps.items():
            storage = {dtype: [] for dtype in dtypes}

            if subregions is None:
                d = region._get_data(factory, dtypes, query_region, *args, **kwargs)
                for key, d_ in d.items():
                    storage[key] = d_
                    subregion_storage.update({region.name: storage})
            else:
                for sr in subregions:
                    storage_ = {}
                    d = sr._get_data(factory, dtypes, query_region, parent_region = region)
                    for key, d_ in d.items():
                        storage_.update({key: d_})
                    subregion_storage.update({sr.name: storage_})
        
        return_data = {}
        for dtype in dtypes:
            values = [v[dtype] for v in subregion_storage.values()]
            return_data.update({dtype: values})

        return return_data


    def _get_data(self, factory: DataFactory, dtypes: list, query_region: BaseRegion, *args, **kwargs) -> dict:
        data_storage = {}
        for dtype in dtypes:

            try:
                data_storage.update({dtype: self._cache[dtype]})
            except KeyError:
                data = factory.get_data(dtype, self, *args, **kwargs)
                self.cache(data, dtype)
                data_storage.update({dtype: data})
        return data_storage

    def check_for_edges(self, *args, **kwargs) -> None:
        """
        Shapely is a 2D geometry package, meaning it doesn't
        understand that RA 359.9 is right next to RA 0.1. This
        function checks if the region falls near that boundary
        (or the equivalent for DEC)
        """

        bounds = self._geometry.bounds
        x_min, y_min, x_max, y_max = bounds

        x_edge = BaseRegion.check_x_edge(x_min, x_max)
        y_edge = BaseRegion.chcek_y_edge(y_min, y_max)
        cycle = (x_edge[0], y_edge[0])
        overlap = (x_edge[1], y_edge[1])
        if any(overlap):
            self.build_overlap_regions()
        elif any(cycle):
            self.build_cycle_regions(cycle)
        else:
            self._geometries = [self._geometry]

    @abstractmethod
    def build_cycle_regions(self, *args, **kwargs) -> None:
        """
        Shapely is a 2D geometry package, meaning it doesnt understand
        spherical geometry. This function handles a region that goes over
        the longitude/latitude line. 
        """
        pass
    
    def _validate_geometry(self, *args, **kwargs):
        x_min, y_min, x_max, y_max = self._geometry.bounds
        x_bounds = np.array([x_min, x_max])
        y_bounds = np.array([y_min, y_max])
        if np.all(x_bounds > 360):
            x_shift = -360 * (x_bounds[0] // 360)
        elif np.all(x_bounds < 0):
            x_shift = - 360*(x_bounds[1] // 360)
        else:
            x_shift = 0

        if np.all(y_bounds > 90):
            y_shift = -90 * (y_bounds[0] // 90)
        elif np.all(y_bounds < -90):
            y_shift = 90 + 90*(y_bounds[1] // 90)
        else:
            y_shift = 0
        geo = translate(self._geometry, x_shift, y_shift)
        self._geometry = geo

    def build_overlap_regions(self, *args, **kwargs):
        """
        This function handles cases when the region is at least partially out of bounds
        """
        x_min, y_min, x_max, y_max = self._geometry.bounds
        if x_min < 0:
            x_geometries = [self._geometry, translate(self._geometry, 360)]
        elif x_max > 360:
            x_geometries = [self._geometry, translate(self._geometry, -360)]
        else:
            x_geometries = [self._geometry]
        
        if y_min < -90:
            y_geometries = [translate(g, 0, 90) for g in x_geometries]
        elif y_max > 90:
            y_geometries = [translate(g, 0, -90) for g in x_geometries]
        else:
            y_geometries = []
        
        self._geometries = x_geometries + y_geometries




    @staticmethod
    def check_x_edge(minx: float, maxx: float) -> bool:
        dx = maxx - minx

        maxx_r = (maxx + 90) % 360
        minx_r = (minx + 90) % 360

        dx_r = maxx_r - minx_r
        cycle = (dx_r < 0) and (abs(dx_r) < abs(dx))
        overlap = maxx > 360 or minx < 0
        return (cycle, overlap)


    @staticmethod
    def chcek_y_edge(miny: float, maxy: float) -> bool:
        dy = maxy - miny

        maxy_r = (maxy - 45) % 90
        miny_r = (miny - 45) % 90

        dy_r = maxy_r - miny_r
        cycle = (dy_r < 0) and (abs(dy_r) < abs(dy))
        overlap = miny < -90 or maxy > 90
        return (cycle, overlap)
