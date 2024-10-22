from __future__ import annotations

import logging
from functools import partial
from typing import Any, Optional, Union

import astropy.units as u
from astropy.coordinates import SkyCoord

from heinlein.dataset.extension import get_extension, load_extensions
from heinlein.manager import get_manager
from heinlein.manager.cache import clear_cache
from heinlein.manager.manager import DataManager
from heinlein.region import BaseRegion, Region
from heinlein.region.footprint import Footprint

logger = logging.getLogger("Dataset")


def load_dataset(name: str) -> Dataset:
    """
    Load a dataset by name. This method shold always be used. Do
    not instantiate the dataset class directly.
    """
    manager = get_manager(name)
    ds = Dataset(manager)
    ds = setup_dataset(ds)
    return ds


def load_current_config(name: str):
    manager = get_manager(name)
    return manager.config


def setup_dataset(dataset: Dataset):
    """
    Searches for an external implementation of the datset
    This is used for datasets with specific needs (i.e. specific surveys)
    """
    external = dataset.manager.external

    if external and dataset.manager.external is None:
        raise NotImplementedError(
            f"No implementation code found for datset {dataset.name}"
        )

    try:
        get_regions = dataset.manager.get_external("load_regions")
    except KeyError:
        raise NotImplementedError(
            f"Dataset {dataset.name} does not have a setup method!"
        )

    regions = get_regions()
    dataset.footprint = Footprint(regions)
    load_extensions(dataset)
    return dataset


class Dataset:
    """
    The Dataset class is the core of heinlein's user interface. It contains routines
    for querying data from the underlying dataset.

    The dataset class should not be created directly. Instead use "load_dataset."

    """

    def __init__(self, manager: DataManager, *args, **kwargs):
        self.manager = manager
        self._extensions = {}
        self._parameters = {}

    @property
    def name(self):
        return self.manager.name

    def __getattr__(self, key__):
        """
        I went through a phase where I thought defining magic methods all over the place
        was really cool. I've since learned that it sometimes creates more complexity
        than it is worth, but this is one case where it makes sense.

        There are certain methods that need to be defined or overloaded for specific
        datasets. This method allows that to be largely transparent to the end user,
        without cluttering the main class with a bunch of extra methods.
        """

        try:
            f = get_extension(self.name, key__)
            return partial(f, self)
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__} object has no attribute '{key__}'"
            )

    def cone_search(
        self, center: tuple | SkyCoord, radius: u.Quantity, *args, **kwargs
    ) -> dict[str, Any]:
        """
        Perform a cone search on the dataset. Will return a dictionary of format:
        {"datta_type": data}

        The center can be passed in as a sky coordinate or a tuple of (ra, dec). If
        a tuple, it is assumed to be in degrees.
        """
        reg = Region.circle(center=center, radius=radius)
        return self.get_data_from_region(reg, *args, **kwargs)

    def box_search(
        self,
        center: tuple | SkyCoord,
        width: u.Quantity,
        height: Optional[u.Quantity] = None,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Perform a box search on the dataset. Will return a dictionary of format:
        {"datta_type": data}
        """
        if isinstance(center, tuple):
            center = SkyCoord(*center, unit="deg")
        if height is None:
            height = width
        minx = center.ra - width / 2
        maxx = center.ra + width / 2
        miny = center.dec - height / 2
        maxy = center.dec + height / 2
        reg = Region.box([minx, miny, maxx, maxy])
        return self.get_data_from_region(reg, *args, **kwargs)

    def get_data_from_region(
        self,
        query_region: BaseRegion,
        dtypes: Union[str, list] = "catalog",
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Get data of of the given types from a provided region. In general,
        it is better to use cone_search or box_search so you don't have to
        worry about constructing the region yourself.

        Paramaters:

        region <BaseRegion> heinlein Region object
        dtypes <str> or <list>: list of data types to return

        """
        get_overlaps = self.manager.get_external("get_overlapping_regions")
        if get_overlaps is not None:
            overlaps = get_overlaps(self, query_region)
        else:
            overlaps = self.footprint.get_overlapping_regions(query_region)
        if len(overlaps) == 0:
            print("Error: No objects found in this region!")
            return

        data = {}
        if isinstance(dtypes, str):
            dtypes = [dtypes]

        data = self.manager.get_data(dtypes, query_region, overlaps, *args, **kwargs)
        return_data = {}
        for dtype, obj_ in data.items():
            try:
                return_data.update({dtype: obj_.get_data_from_region(query_region)})
            except AttributeError:
                return_data.update({dtype: obj_})

        return return_data

    def get_data_from_samples(
        self,
        samples,
        sample_type="cone",
        sample_dimensions=45 * u.arcsec,
        dtypes=["catalog"],
        *args,
        **kwargs,
    ):
        """
        Often, we want to get many many samples in a row.
        is that the cache will very quickly blow up if the samples cover may
        of the survey's subregions. This methord returns a generator that
        yields samples from the survey. It orders them such that it can
        only load a few subregions at a time, then dumps them from the cache when
        they are done.
        """
        if sample_type != "cone":
            raise NotImplementedError("Only cone sampling is currently supported")

        samples = [Region.circle(center=s, radius=sample_dimensions) for s in samples]

        partitions = self.footprint.partition_by_region(samples)
        counts = [p.count("/") + 1 for p in partitions.keys()]
        singles = []

        for i, (regs, s) in enumerate(samples.items()):
            if counts[i] == 1:
                continue
            regs_to_get = regs.split("/")
            for s_ in s:
                yield (s_, self.get_data_from_region(s_, dtypes))
            for reg_ in regs_to_get:
                # Now, get the samples that fall into a single one of the regions
                if reg_ in singles:
                    continue
                try:
                    samples_in_reg = samples[reg_]
                except KeyError:
                    continue
                singles.append(reg_)
                for s_ in samples_in_reg:
                    yield (s_, self.get_data_from_region(s_, dtypes))
            # Now, we dump the data from those regions
            clear_cache(self.name)
        # Now we go through all the samples that fall in a single survey region
        # that were NOT covered before
        for i, (reg, s) in enumerate(samples.items()):
            if counts[i] != 1 or reg in singles:
                continue
            else:
                for s_ in s:
                    yield (s_, self.get_data_from_region(s_, dtypes))
                clear_cache(self.name)
