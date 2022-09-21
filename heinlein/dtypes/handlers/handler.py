from pathlib import Path
from abc import ABC, abstractmethod
from heinlein import dtypes
from heinlein.dtypes import mask
from heinlein.dtypes.handlers import catalog



class Handler(ABC):

    def __init__(self, path: Path, dconfig: dict, type: str, *args, **kwargs):
        self._type = type
        self._path = path
        self._config = dconfig

    @abstractmethod
    def get_data(self, regions: list, *args, **kwargs):
        pass

    def get_data_object(self, data, *args, **kwargs):
        return dtypes.get_data_object(self._type, data)
