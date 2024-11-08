from functools import singledispatchmethod

import astropy.units as u
from shapely import GeometryCollection, STRtree, union_all

from .region import BaseRegion
from .sampling import Sampler


def build_tree(regions: list[BaseRegion]) -> STRtree:
    """
    Builds an STRtree from a list of regions
    """
    geos = [r.geometry for r in regions]
    tree = STRtree(geos)
    return tree


def build_footprint(regions: list[BaseRegion]) -> GeometryCollection:
    """
    Stitch together a list of regions into a single footprint
    """
    shapely_geos = [r._flat_sky_geometry for r in regions]
    collection = union_all(shapely_geos)
    return collection


class Footprint:
    """
    The footprint class is a container for a set of regions. It is used to represent
    the geometry of the survey, which is used to accelerate queries.

    The initial querying for regions is done using Healpix. When a footprint is created,
    it determines which healpix pixels overlap with each of its regions. The first step
    in querying is then to determine which healpix pixels overlap with the region being
    queried, and return
    the regions that overlap with those pixels.
    """

    def __init__(self, regions: dict[str, BaseRegion], *args, **kwargs):
        self._regnames = list(regions.keys())
        self._regions = list(regions.values())
        self._tree = build_tree(self._regions)
        self._footprint = build_footprint(self._regions)
        self._sampler = Sampler(self._footprint)

    @singledispatchmethod
    def get_overlapping_regions(self, region: BaseRegion) -> list[BaseRegion]:
        """
        Returns a list of regions that overlap with the given region
        """
        overlap_idx = self._tree.query(region.geometry)
        overlaps = [self._regions[i] for i in overlap_idx]
        overlaps = filter(lambda x: x.intersects(region), overlaps)
        return list(overlaps)

    @get_overlapping_regions.register
    def _(self, region: list) -> list[list[BaseRegion]]:
        region_overlaps = [self._tree.query(other.geometry) for other in region]
        overlaps = [
            [self._regions[i] for i in overlaps] for overlaps in region_overlaps
        ]
        overlaps = [
            [o for o in overlap if o.intersects(region[i])]
            for i, overlap in enumerate(overlaps)
        ]
        return overlaps

    def get_overlapping_region_names(
        self, region: BaseRegion | list[BaseRegion]
    ) -> list[str]:
        """
        Returns a list of region names that overlap with the given region
        """
        overlaps = self.get_overlapping_regions(region)
        if isinstance(region, list):
            return [[r.name for r in o] for o in overlaps]
        return [r.name for r in overlaps]

    def sample(self, n: int = 1, tolerance: u.Quantity = None, *args, **kwargs) -> list:
        """
        Return n random points from the footprint
        """
        if n == 1:
            return self._sampler.sample(tolerance=tolerance)
        else:
            return [self._sampler.sample(tolerance=tolerance) for _ in range(n)]

    def partition_by_region(
        self, samples: list[BaseRegion]
    ) -> dict[str, list[BaseRegion]]:
        """
        Given a list of regions, partition based on the regions they overlap
        with in this footprint. Returns a dictionary by region name. Samples
        that overlap with multiple regions are placed in a key that is a
        concatenation of the regions they overlap with.
        """
        overlaps = self.get_overlapping_region_names(samples)
        partitions = {}

        for i, sample in enumerate(samples):
            overlap = overlaps[i]
            if len(overlap) == 1:
                okey = overlap[0]
            else:
                overlap.sort()
                okey = "/".join(overlap)
            try:
                partitions[okey].append(sample)
            except KeyError:
                partitions[okey] = [sample]
        return partitions
