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

def load_config(*args, **kwargs):
    """
    Loads the region config.
    """
    config_location = MAIN_CONFIG_DIR / "region" / "region.json"
    with open(config_location, "r") as f:
        config = json.load(f)
        return config

current_config = load_config()
class BaseRegion(ABC):
    _config = current_config
    def __init__(self, geometry, type, name = None, *args, **kwargs):
        """
        Base region object.
        Regions should always be initialized with heinlein.Region

        parameters:

        geometry: <spherical_geometry.SingleSphericalPolygon> The sky region
        type: <str> The type of the region
        name: <str> The name of the region (optional) 
        """
        self._spherical_geometry = geometry
        self._type = type
        self.name = name
        self.setup()

    def setup(self, *args, **kwargs):
        """
        Perform setup for the region
        """
        self._subregions = np.array([], dtype=object)
        self._covered = False
        points = self._spherical_geometry.points
        self._flat_geometry = Polygon(points)

    def __setstate__(self, state):
        """
        Fixes reading pickled regions
        """
        self.__dict__.update(state)
        self._config = current_config

    def __getattr__(self, __name: str) -> Any:
        """
        Implements geometry relations for regions. Delegates unknown methods to the
        underlying spherical geometry object, IF that method is explicitly permitted
        in heinlein/config/region/region.json
        """
        try:
            cmd_name = self._config['allowed_predicates'][__name]
            attr = getattr(self.spherical_geometry, cmd_name)
            func = lambda x: attr(x.spherical_geometry)
            return func
        except KeyError:
            raise AttributeError(f"{self._type} has no attribute \'{__name}\'")


    def _delegate_relationship(self, other: BaseRegion, method_name: str, *args, **kwargs) -> Any:
        attr = getattr(self._geometry, method_name)
        return attr(other)


    @property
    def geometry(self, *args, **kwargs):
        """
        Returns the flattened geometry for the object
        """
        return self._flat_geometry
    
    @property
    def spherical_geometry(self):
        """
        Returns the correct spherical geometry for the object
        """
        return self._spherical_geometry

    @property
    def type(self) -> str:
        """
        Returns the type of the region
        """
        return self._type

    def center(self, *args, **kwargs):
        pass

        
