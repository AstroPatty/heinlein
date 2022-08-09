from __future__ import annotations
from abc import ABC, abstractmethod
from heinlein.locations import BUILTIN_DTYPES
from heinlein.manager.manager import Manager
from typing import Any
import json

class DataFactory(ABC):

    def __init__(self, manager: Manager, handlers: dict, *args, **kwargs):
        """
        A data factory is responsible for retrieving data and returning it 
        to the calling proceess. It contains handlers, which are capable of reading
        in a specific data type (e.g. "catalog" or "mask") from a particular storage 
        type (i.e. "csv" or "mongodb")
        """
        self.valid = False
        self.manager = manager
        self.handlers = handlers
        self.verify(*args, **kwargs)

    @abstractmethod
    def get_data(self, dtype, query_region, *args, **kwargs) -> Any:
        pass

    def verify(self, *args, **kwargs):
        with open(BUILTIN_DTYPES, "r") as f:
            self.config = json.load(f)
        
        passed_handlers = set(self.handlers.keys())
        minimum_handlers = set(self.config.keys())
        if not minimum_handlers.issubset(passed_handlers):
            missing = minimum_handlers.difference(passed_handlers)
            raise TypeError(f"Handler object missing handlers for built in dtypes {missing}")
        self.valid = True



