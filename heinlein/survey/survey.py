import json
import pathlib
import logging
from abc import abstractmethod
from sys import implementation
from importlib import import_module
import numpy as np
from xml.dom.minidom import Attr

from heinlein.region import BaseRegion, Region

logger = logging.getLogger("Survey")

class Survey:

    def __init__(self, config, *args, **kwargs):
        self.__dict__.update(config)

    def setup(self, *args, **kwargs) -> None:
        try:
            setup = getattr(self._ext, "setup")
            setup(self)
            self._validate_setup()
        except AttributeError:
            raise NotImplementedError("Survey {self.name} does not have a setup method!")

    def _validate_setup(self, *args, **kwargs):
        try:
            regions = self._regions
        except AttributeError:
            logging.error(f"No region found for surve {self.name}")

    def get_region_overlaps(self, other: BaseRegion, *args, **kwargs):
        """
        Find the subregions inside a survey that overlap with a given region
        """
        mask = np.array([other.overlaps(r) for r in self._regions])
        return self._regions[mask]


def load_survey(name: str) -> Survey:
    config = load_survey_config(name)
    s = Survey(config)
    return update_survey_object(s)

def load_survey_config(name: str) -> dict:
    self_path = pathlib.Path(__file__)
    config_path = self_path.parents[0] / "configs"
    registered_surveys_path = config_path / "surveys.json"
    with open(registered_surveys_path) as rsf:
        try:
            data = json.load(rsf)
            path = data[name]['config_path']
        except KeyError:
            logger.error(f"Unable to find a config for survey {name}")
            return None
    
    with open(config_path / path) as scf:
        survey_config = json.load(scf)
        if validate_survey_config(survey_config, config_path):
            survey_config.update({'slug': name})
            return survey_config
        else:
            return None        

def validate_survey_config(config: dict, config_path: pathlib.Path) -> bool:
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

def update_survey_object(obj, *args, **kwargs):
    mod = import_module(obj.slug)
    obj._ext = mod
    obj.setup()
    return obj
    