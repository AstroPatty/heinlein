from abc import ABC, abstractmethod
from pathlib import Path

from heinlein import dtypes
from heinlein.region import BaseRegion


class Handler(ABC):
    def __init__(self, path: Path, dconfig: dict, type: str, *args, **kwargs):
        self._path = path
        self._type = type
        self._config = dconfig

    @abstractmethod
    def get_data_from_named_regions(self, regions: list, *args, **kwargs):
        pass

    @abstractmethod
    def get_data_from_region(
        self, region: BaseRegion, overlapping_regions: list[str], *args, **kwargs
    ):
        pass

    def get_data_object(self, data, *args, **kwargs):
        return dtypes.get_data_object(self._type, data)
