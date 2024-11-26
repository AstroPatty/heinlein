from abc import ABC, abstractmethod
from pathlib import Path

from heinlein import dtypes
from heinlein.region.base import BaseRegion


class Handler(ABC):
    def __init__(self, path: Path, dconfig: dict, type: str, *args, **kwargs):
        self._path = path
        self._type = type
        self._config = dconfig

    @abstractmethod
    def get_data_by_regions(self, survey_regions: list[list], *args, **kwargs):
        """
        Get data from a set of named regions.
        """
        pass

    @abstractmethod
    def get_data_in_region(
        self, survey_regions: list[str], query_region: BaseRegion, *args, **kwargs
    ):
        """
        Get a data from a given query region. The handler is not capable
        of determining which survey regions to use, so they must be passed
        explicitly.
        """
        pass

    def get_data_object(self, data, *args, **kwargs):
        return dtypes.get_data_object(self._type, data)
