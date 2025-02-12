import json
import math
import operator
import pickle
import re
import warnings
from importlib.resources import files
from pathlib import Path

import numpy as np
import regions as reg
from shapely import affinity, geometry
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.mask import Mask
from heinlein.region import Region


def load_regions():
    resources = files("heinlein_hsc")
    with open(resources / "regions.reg", "rb") as f:
        regions = pickle.load(f)
    return regions


def load_config():
    resources = files("heinlein_hsc")
    with open(resources / "config.json") as f:
        config = json.load(f)
    return config


def region_to_shapely(region):
    """
    Parses an astropy region object into a shapely object
    Shapely doesn't work in curved space, but bright star
    masks are on the scale of arcseconds, so working with
    a flat sky is safe.
    """
    if isinstance(region, reg.CircleSkyRegion):
        new_region = geometry.Point(
            region.center.ra.to_value("deg"), region.center.dec.to_value("deg")
        ).buffer(region.radius.to_value("deg"))
    elif isinstance(region, reg.RectangleSkyRegion):
        center = region.center
        x = center.ra.to_value("deg")
        y = center.dec.to_value("deg")
        width = region.width.to_value("deg")
        height = region.height.to_value("deg")
        angle = region.angle.to_value("deg")
        box = geometry.box(x - width / 2, y - height / 2, x + width / 2, y + height / 2)
        new_region = affinity.rotate(box, angle)
    return new_region


def _load_region_data(files, *args, **kwargs):
    """
    Loads data about the tracts and patches for the given HSC field
    Used to split up data, making it easier to manage

    """
    output = np.empty(len(files), dtype=object)
    for i, file in enumerate(files):
        tracts = _parse_tractfile(file)
        tracts = _parse_tractdata(tracts, *args, **kwargs)
        field = np.hstack(np.array([np.array(t) for t in tracts.values()]))
        output[i] = field
    return np.hstack(output)


def _parse_tractfile(tractfile):
    tracts = {}
    with open(tractfile) as tf:
        for line in tf:
            if line.startswith("*"):
                continue

            nums = re.findall(r"[-+]?\d*\.\d+|\d+", line)
            tract_num = int(nums[0])
            patch = re.search("Patch", line)
            if patch is None:
                if tract_num not in tracts.keys():
                    tracts.update(
                        {tract_num: {"corners": [], "type": "tract", "subregions": {}}}
                    )
                if "Corner" in line:
                    tracts[tract_num]["corners"].append(
                        (float(nums[-2]), float(nums[-1]))
                    )
                elif "Center" in line:
                    tracts[tract_num].update(
                        {"center": (float(nums[-2]), float(nums[-1]))}
                    )

            else:
                patch = re.findall(r"\d,\d", line)
                patch_val = tuple(map(int, patch[0].split(",")))
                if patch_val not in tracts[tract_num]["subregions"].keys():
                    tracts[tract_num]["subregions"].update(
                        {patch_val: {"corners": [], "type": "patch"}}
                    )
                if "Corner" in line:
                    tracts[tract_num]["subregions"][patch_val]["corners"].append(
                        (float(nums[-2]), float(nums[-1]))
                    )
                elif "Center" in line:
                    tracts[tract_num]["subregions"][patch_val].update(
                        {"center": (float(nums[-2]), float(nums[-1]))}
                    )
    return tracts


def _parse_tractdata(tractdata, *args, **kwargs):
    output = {}
    try:
        wanted_tracts = kwargs["tracts"]
    except KeyError:
        wanted_tracts = []
    for index, (name, tract) in enumerate(tractdata.items()):
        if wanted_tracts and name not in wanted_tracts:
            continue
        corners = tract["corners"]
        center = tract["center"]

        points = _parse_polygon_corners(center, corners)
        tract_ra = [p[0] for p in points]
        tract_dec = [p[1] for p in points]
        poly = SingleSphericalPolygon.from_radec(tract_ra, tract_dec, center)
        Region(poly, name=name)

        patches = {}
        for patchname, patch in tract["subregions"].items():
            patch_corners = patch["corners"]
            patch_center = patch["center"]
            patch_name_parsed = _patch_tuple_to_int(patchname)
            ras = [p[0] for p in patch_corners]
            decs = [p[1] for p in patch_corners]
            final_name = f"{name}.{patch_name_parsed}"

            if final_name == "10049.402":
                import pickle

                with open("bad_points.p", "wb") as f:
                    out = {"points": points, "center": patch_center}
                    pickle.dump(out, f)

            patch_poly = SingleSphericalPolygon.from_radec(ras, decs, patch_center)
            patches.update({final_name: Region(patch_poly, name=final_name)})

        output.update(patches)
    return output


def _parse_polygon_corners(center, points):
    sorted_coords = sorted(
        points,
        key=lambda coord: (
            -135
            - math.degrees(math.atan2(*tuple(map(operator.sub, coord, center))[::-1]))
        )
        % 360,
    )

    # This ensures the points are ordered counter-clockwsie, to avoid twisted polygons
    # Shoutout to StackOverflow
    return sorted_coords


def _patch_tuple_to_int(patch_tuple):
    """
    Takes in a patch ID as a tuple and turns it into an int.
    This int can be used to look up objects in the catalof
    """
    if patch_tuple[0] == 0:
        return patch_tuple[1]
    else:
        return 100 * patch_tuple[0] + patch_tuple[1]


def _patch_int_to_tuple(patch_int):
    if patch_int < 0:
        return (0, patch_int)
    else:
        return (patch_int // 100, patch_int % 100)


class MaskHandler(Handler):
    def __init__(self, path: Path, *args, **kwargs):
        kwargs.update({"type": "mask"})
        super().__init__(path, *args, **kwargs)
        self.known_patches = [f.stem for f in self._path.glob("*") if f.is_dir()]

    def get_data(self, regions, *args, **kwargs):
        masks = {}

        for name in regions:
            name_split = name.split(".")
            tract_name = name_split[0]
            patch_number = name_split[1]

            basename = "BrightStarMask-{}-{},{}-HSC-I.reg"
            patch_tuple = _patch_int_to_tuple(int(patch_number))

            if tract_name not in self.known_patches:
                raise ValueError(f"Could not find masks for HSC tract {tract_name}")

            filename = basename.format(tract_name, patch_tuple[0], patch_tuple[1])
            patch_path = self._path / tract_name / filename

            if not patch_path.exists():
                raise ValueError(f"Could not find mask for region {name}")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                mask = reg.Regions.read(str(patch_path))

            shapely_regions = [region_to_shapely(r) for r in mask]
            masks.update({name: Mask(shapely_regions)})

        return masks

    def get_data_object(self, objs):
        objs_ = list(objs.values())
        return objs_[0].append(objs_[1:])
