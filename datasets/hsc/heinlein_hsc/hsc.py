import json
import math
import operator
import pickle
import re
from importlib.resources import read_binary, read_text

import numpy as np
import regions as reg
from shapely import affinity, geometry
from spherical_geometry.polygon import SingleSphericalPolygon

from heinlein.dtypes.handlers.handler import Handler
from heinlein.dtypes.mask import Mask
from heinlein.region import Region


def load_regions():
    regions = read_binary("heinlein_hsc", "regions.reg")
    regions = pickle.loads(regions)
    return {r.name: r for r in regions}


def load_config():
    text = read_text("heinlein_hsc", "config.json")
    config = json.loads(text)
    return config


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
    def __init__(self, *args, **kwargs):
        kwargs.update({"type": "mask"})
        super().__init__(*args, **kwargs)

    def get_data(self, regions, *args, **kwargs):
        vals = {}

        for index, name in enumerate(regions):
            split = name.split(".")
            basename = "BrightStarMask-{}-{},{}-HSC-I"
            patch_tuple = _patch_int_to_tuple(int(split[1]))

            fname = basename.format(split[0], patch_tuple[0], patch_tuple[1])
            project_path = "/".join(["data", "mask", split[0]])

            files = self._project.list(project_path)["files"]
            file = list(filter(lambda x: fname in x, files))
            if not file:
                raise ValueError(f"Could not find mask for region {name}")
            elif len(file) > 1:
                raise ValueError(f"Found more than one mask for region {name}")

            project_path = "/".join([project_path, file[0]])

            file_path = self._project.get(project_path)
            mask = reg.Regions.read(str(file_path))
            new_masks = np.empty(len(mask), dtype=object)

            for i, r in enumerate(mask):
                if type(r) == reg.CircleSkyRegion:
                    new_reg = Region.circle(r.center, r.radius.to_value("deg"))
                elif type(r) == reg.RectangleSkyRegion:
                    center = r.center
                    x = center.ra.to_value("deg")
                    y = center.dec.to_value("deg")
                    width = r.width.to_value("deg")
                    height = r.height.to_value("deg")
                    angle = r.angle.to_value("deg")
                    box = geometry.box(
                        x - width / 2, y - height / 2, x + width / 2, y + height / 2
                    )
                    new_reg = affinity.rotate(box, angle)
                    x_coords, y_coords = new_reg.exterior.xy
                    inside = (x, y)
                    new_reg = SingleSphericalPolygon.from_lonlat(
                        x_coords, y_coords, center=inside
                    )
                    new_reg = Region.polygon(new_reg)

                new_masks[i] = new_reg

            obj = np.empty(1, dtype=object)
            obj[0] = new_masks
            vals.update({name: Mask(obj)})

        return vals

    def get_data_object(self, objs):
        objs_ = list(objs.values())
        return objs_[0].append(objs_[1:])
