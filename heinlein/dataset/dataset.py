import logging
from functools import partial, singledispatchmethod
from inspect import getmembers
from typing import List, Union

import astropy.units as u
import numpy as np
from shapely.strtree import STRtree

from heinlein.manager import get_manager
from heinlein.manager.dataManger import DataManager
from heinlein.region import BaseRegion, Region

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
    def __init__(self, manager: DataManager, *args, **kwargs):
        self.manager = manager
        self.config = manager.get_config()
        self._extensions = {}
        self._parameters = {}
        self._setup()

    def __getattr__(self, key__):
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
            setup_f = self.manager.get_external("setup")
            setup_f(self)
            self._validate_setup()
        except KeyError:
            raise NotImplementedError(
                f"Dataset {self.name} does not have a setup method!"
            )

        self._load_extensions()
        self._build_region_tree()

    def set_parameter(self, name, value):
        self._parameters.update({name: value})

    def get_parameter(self, name):
        return self._parameters.get(name, None)

    def _validate_setup(self, *args, **kwargs) -> None:
        try:
            self._regions = np.array(self._regions, dtype=object)
            self._region_names = np.array(
                [reg.name for reg in self._regions], dtype=str
            )
        except AttributeError:
            logging.error(f"No region found for survey {self.name}")

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

    def _build_region_tree(self, *args, **kwargs) -> None:
        """
        For larger surveys, we subidivide into smaller regions for easier
        querying. Shapely implements a tree-based searching algorithm for
        finding region overlaps, so we create that tree here.
        """
        geo_list = np.array([reg.geometry for reg in self._regions])
        indices = {id(geo): i for i, geo in enumerate(geo_list)}
        self._geo_idx = indices
        self._geo_tree = STRtree(geo_list)

    def get_path(self, dtype: str, *args, **kwargs):
        """
        Gets the path to where a particular item in a dataset is stored on disk
        """
        return self.manager.get_path(dtype)

    def add_aliases(self, dtype: str, aliases, *args, **kwargs):
        """
        Adds an alias for the current interpreter
        """
        try:
            self._aliases.update({dtype: aliases})
        except AttributeError:
            self._aliases = {dtype: aliases}

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

        overlaps = self.get_overlapping_region_names(samples)
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
    def get_region_overlaps(self, other: BaseRegion, *args, **kwargs) -> list:
        """
        Find the subregions inside a dataset that overlap with a given region
        Uses the shapely STRTree for speed.
        """
        region_overlaps = self._geo_tree.query(other.geometry)
        overlaps = [self._regions[i] for i in region_overlaps]
        overlaps = [o for o in overlaps if o.intersects(other)]
        return overlaps

    def _get_many_region_overlaps(self, others: list, *args, **kwargs):
        region_overlaps = [self._geo_tree.query(other.geometry) for other in others]
        overlaps = [
            [self._regions[i] for i in overlaps] for overlaps in region_overlaps
        ]
        overlaps = [
            [o for o in overlap if o.intersects(others[i])]
            for i, overlap in enumerate(overlaps)
        ]
        return overlaps

    @check_overload
    def get_data_from_named_region(
        self, name: str, dtypes: Union[str, list] = "catalog"
    ):
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
        overlaps = self.get_region_overlaps(query_region, *args, **kwargs)
        overlaps = [o for o in overlaps if o.intersects(query_region)]
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
        reg = Region.circle(center=center, radius=radius)
        return self.get_data_from_region(reg, *args, **kwargs)

    @check_overload
    def get_overlapping_region_names(self, query_region: BaseRegion):
        if isinstance(query_region, BaseRegion):
            return [r.name for r in self.get_region_overlaps(query_region)]
        elif isinstance(query_region, list):
            overlaps = self._get_many_region_overlaps(query_region)
            return [[r.name for r in o] for o in overlaps]

    def get_many_overlapping_region_names(self, query_regions: list):
        pass

    @check_overload
    def get_region_by_name(self, name: str, override=False):
        matches = self._regions[self._region_names == name]
        if len(matches) == 0:
            print(f"No regions with name {name} found in survey {self.name}")
        if len(matches) > 1 and not override:
            print("Error: multiple regions found with this name")
            print(
                'Call with "override = True" to silence this message and'
                " return the regions"
            )
        elif override:
            return matches
        else:
            return matches[0]

    @check_overload
    def get_regions_by_name(self, names: List[str]):
        matches = self._regions[np.in1d(self._region_names, names)]
        if len(matches) == 0:
            print(f"No matches were found in dataset {self.name}")
        else:
            return matches

    @singledispatchmethod
    def mask_fraction(self, region_name: str, *args, **kwargs):
        """
        Returns the fraction of the named region covered by some sort of mask.
        Initializes a grid of points, then masks them to get an approximate

        """
        if region_name not in self._region_names:
            print(f"Unable to find region named {region_name} for dataset {self.name}")
        reg = self._regions[self._region_names == region_name]
        mask = self.get_data_from_named_region(region_name, dtypes=["mask"])["mask"][
            region_name
        ]
        grid = reg[0].get_grid(density=10000)
        return self._mask_fraction(mask, grid)

    @mask_fraction.register
    def _(self, region: BaseRegion, *args, **kwargs):
        mask = self.get_data_from_region(region, dtypes=["mask"])["mask"]
        grid = region.get_grid(density=200000)
        return self._mask_fraction(mask, grid)

    @staticmethod
    def _mask_fraction(mask, grid):
        masked_grid = mask.mask(grid)
        return round(1 - len(masked_grid) / len(grid), 3)


def load_dataset(name: str) -> Dataset:
    manager = get_manager(name)
    ds = Dataset(manager)
    return ds


def load_current_config(name: str):
    manager = get_manager(name)
    return manager.config
