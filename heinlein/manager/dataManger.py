from abc import abstractmethod
import json
from heinlein.locations import BASE_DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG
from abc import ABC
from heinlein.utilities import warning_prompt, warning_prompt_tf
from typing import Any
import logging

logger = logging.getLogger("manager")

class DataManager(ABC):

    def __init__(self, name, *args, **kwargs):
        """
        The datamanger keeps track of where data is located, either on disk or 
        otherwise.
        It also keeps a manifest, so it knows when files have been moved or changed.
        
        """
        self.name = name
    
    @staticmethod
    def exists(name: str) -> bool:
        """
        Checks if a datset exists
        """
        with open(MAIN_DATASET_CONFIG, "r") as f:
            surveys = json.load(f)
        if name in surveys.keys():
            return True
        return False

    @abstractmethod
    def add_data(self, *args, **kwargs):
        pass

    @abstractmethod
    def remove_data(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_data(self, *args, **kwargs) -> dict:
        pass

    @abstractmethod
    def initialize_dataset(self, *args, **kwargs):
        pass

    @abstractmethod
    def clear_all_data(self, *args, **kwargs): 
        pass

    @abstractmethod
    def get_handler(self, dtype: str, *args, **kwargs):
        pass

