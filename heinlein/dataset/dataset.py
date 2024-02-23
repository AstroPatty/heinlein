import logging
from functools import partial
from inspect import getmembers
from typing import Union

import astropy.units as u

from heinlein.manager import get_manager
from heinlein.manager.manager import DataManager
from heinlein.region import BaseRegion, Region
from heinlein.region.footprint import Footprint

logger = logging.getLogger("Dataset")


def check_overload(f):
    def wrapper(self, *args, **kwargs):
        overload = self.manager.get_external(f.__name__)
        bypass = kwargs.get("bypass", False)
        if bypass or overload is None:
            return f(self, *args, **kwargs)
        else:
            return overload(self, *args, **kwargs)

    return wrapper


class dataset_extension:
    def __init__(self, function):
        self.function = function
        self.extension = True
        self.name = function.__name__

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)


class Dataset:
    """
    The Dataset class is the core of heinlein's user interface. It contains routines
    for querying data from the underlying dataset.

    The dataset class should not be created directly. Instead use "load_dataset."

    """

    def __init__(self, manager: DataManager, *args, **kwargs):
        self.manager = manager
        self.config = manager.get_config()
        self._extensions = {}
        self._parameters = {}
        self._setup()

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
            f = self._extensions[key__]
            return partial(f, self)
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__} object has no attribute '{key__}'"
            )

    @property
    def name(self):
        return self.manager.name

    def _setup(self, *args, **kwargs) -> None:
        """
        Searches for an external implementation of the datset
        This is used for datasets with specific needs (i.e. specific surveys)
        """
        external = self.config["implementation"]

        if external and self.manager.external is None:
            raise NotImplementedError(
                f"No implementation code found for datset {self.name}"
            )

        try:
            get_regions = self.manager.get_external("load_regions")
        except KeyError:
            raise NotImplementedError(
                f"Dataset {self.name} does not have a setup method!"
            )

        regions = get_regions()
        self.footprint = Footprint(regions)
        self._load_extensions()

    def set_parameter(self, name, value):
        """
        Parameters are used to store metadata that may be useful to plugins etc.
        """
        self._parameters.update({name: value})

    def get_parameter(self, name):
        return self._parameters.get(name, None)

    def _load_extensions(self, *args, **kwargs):
        """
        Loads extensions for the particular dataset. These are defined externally
        """
        ext_objs = list(
            filter(
                lambda f: type(f[1]) == dataset_extension,
                getmembers(self.manager.external),
            )
        )
        self._extensions.update({f[0]: f[1] for f in ext_objs})

    def get_path(self, dtype: str, *args, **kwargs):
        """
        Gets the path to where a particular item in a dataset is stored on disk
        """
        return self.manager.get_path(dtype)

    def sample_generator(
        self,
        samples,
        sample_type="cone",
        sample_dimensions=45 * u.arcsec,
        dtypes=["catalog"],
        *args,
        **kwargs,
    ):
        """
        Often, we want to get many many samples in a row. The problem here
        is that the cache will very quickly blow up if the samples cover may
        of the survey's subregions. This methord returns a generator that
        yields samples from the survey. It orders them such that it can
        only load a few subregions at a time, then dumps them from the cache when
        they are done.
        """
        if sample_type != "cone":
            raise NotImplementedError("Only cone sampling is currently supported")

        samples = [Region.circle(center=s, radius=sample_dimensions) for s in samples]

        overlaps = self.footprint.get_overlapping_region_names(samples)
        partitions = {}

        for i, sample in enumerate(samples):
            overlap = overlaps[i]
            if len(overlap) == 1:
                okey = overlap[0]
            else:
                overlap.sort()
                okey = "/".join(overlap)

            if okey in partitions.keys():
                partitions[okey].append(sample)
            else:
                partitions[okey] = [sample]

        samples = partitions
        counts = [p.count("/") + 1 for p in samples.keys()]
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
            self.dump_all()
        # Now we go through all the samples that fall in a single survey region
        # that were NOT covered before
        for i, (reg, s) in enumerate(samples.items()):
            if counts[i] != 1 or reg in singles:
                continue
            else:
                for s_ in s:
                    yield (s_, self.get_data_from_region(s_, dtypes))
                self.dump_all()

    @check_overload
    def get_data_from_named_region(
        self, name: str, dtypes: Union[str, list] = "catalog"
    ):
        """
        Given a region name, returns the data of type dtypes in that region.
        """
        if name not in self._region_names:
            print(f"Unable to find region named {name} in dataset {self.name}")
            return

        regs_ = self._regions[self._region_names == name]
        return self.manager.get_from(dtypes, regs_)

    def load(self, regions, dtypes, *args, **kwargs):
        """
        Pre-loads some regions into the cache.
        """
        if isinstance(regions, str):
            regions = [regions]
        if not all([r in self._region_names for r in regions]):
            logging.error("Regions not found!")
            return
        self.manager.load(regions, dtypes)

    def dump(self, regions, *args, **kwargs):
        """
        Dumps some regions from the cache.
        """
        if isinstance(regions, str):
            regions = [regions]
        self.manager.dump(regions)

    def dump_all(self):
        self.manager.dump_all()

    def get_data_from_region(
        self,
        query_region: BaseRegion,
        dtypes: Union[str, list] = "catalog",
        *args,
        **kwargs,
    ) -> dict:
        """
        Get data of type dtypes from a particular region

        Paramaters:

        region <BaseRegion> heinlein Region object
        dtypes <str> or <list>: list of data types to return

        """
        method = self.manager.get_external("get_overlapping_regions")
        if method is not None:
            overlaps = method(self, query_region)
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

        for dtype, d_ in return_data.items():
            if len(d_) == 0:
                continue
            try:
                aliases = self._aliases
            except AttributeError:
                aliases = {}
                self._aliases = aliases
            try:
                alias = aliases[dtype]
                d_.add_aliases(alias)
            except KeyError:
                continue

        return return_data

    def cone_search(self, center, radius, *args, **kwargs):
        """
        A convinience method for doing a cone search. Basically just
        constructs a circular region and calls get_data_from_region.
        """
        reg = Region.circle(center=center, radius=radius)
        return self.get_data_from_region(reg, *args, **kwargs)


def load_dataset(name: str) -> Dataset:
    manager = get_manager(name)
    ds = Dataset(manager)
    return ds


def load_current_config(name: str):
    manager = get_manager(name)
    return manager.config
