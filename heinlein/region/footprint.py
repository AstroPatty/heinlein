from functools import singledispatchmethod

import astropy.units as u
import healpy

from .region import BaseRegion


def partition_regions(
    regions: list[BaseRegion], nside: int
) -> dict[str, list[BaseRegion]]:
    output = {}
    for region in regions:
        pixels = query_healpix(region, nside)
        for pixel in pixels:
            pixel_output = output.get(pixel, [])
            pixel_output.append(region)
            output[pixel] = pixel_output
    return output


def query_healpix(region: BaseRegion, nside: int):
    lon, lat = region.bounding_box.to_lonlat()
    lon, lat = lon[:-1], lat[:-1]
    vecs = healpy.ang2vec(lon, lat, lonlat=True)
    return healpy.query_polygon(nside, vecs, inclusive=True)


def get_healpix_nside(region: BaseRegion):
    """
    Dynamically decide on the nside for a given footprint based on
    the size of a region

    We want something that gives us several regions but not too
    many
    """
    area = 8 * region.bounding_box.area()  # in steradians
    n = 1
    while True:
        pixsize = healpy.nside2pixarea(n**2)
        if pixsize < area:
            break
        n += 1
    return 2 ** (n - 1)


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

    def __init__(self, regions: list[BaseRegion], nside=256, *args, **kwargs):
        self._nside = get_healpix_nside(regions[0])
        self._regions = partition_regions(regions, self._nside)

    @singledispatchmethod
    def get_overlapping_regions(self, query_region: BaseRegion) -> list[BaseRegion]:
        """
        Returns a list of regions that overlap with the given region
        """
        pixels = query_healpix(query_region, self._nside)
        output = []
        for pixel in pixels:
            overlap = self._regions.get(pixel, [])
            overlap = filter(lambda region: region.intersects(query_region), overlap)
            output.extend(overlap)
        return output

    @get_overlapping_regions.register
    def _(self, region: list) -> list[list[BaseRegion]]:
        return [self.get_overlapping_regions(r) for r in region]

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
