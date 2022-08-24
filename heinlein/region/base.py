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
        self.load_config()
        points = self._spherical_geometry.points
        self._flat_geometry = Polygon(points)

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.load_config()

    def __getattr__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions
        """
        try:
            cmd_name = self._config['allowed_predicates'][__name]
            attr = getattr(self.spherical_geometry, cmd_name)
            func = lambda x: attr(x.spherical_geometry)
            return func
        except KeyError:
            raise AttributeError(f"{self._type} has no attribute \'{__name}\'")
    def load_config(self, *args, **kwargs):
        config_location = MAIN_CONFIG_DIR / "region" / "region.json"
        with open(config_location, "r") as f:
            self._config = json.load(f)


    def _delegate_relationship(self, other: BaseRegion, method_name: str, *args, **kwargs) -> Any:
        attr = getattr(self._geometry, method_name)
        return attr(other)


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
        
    def cache_split(self, subregions, *args, **kwargs):
        pass

