from pathlib import Path
import numpy as np
from heinlein.locations import BASE_DATASET_CONFIG_DIR
from heinlein.region import Region
import re
import math
import operator


def setup(self, *args, **kwargs):
    reg = load_regions()
    self._regions = reg

def load_regions():
    support_location = BASE_DATASET_CONFIG_DIR / "support" / "hsc_tiles"
    files = [f for f in support_location.glob("*.txt") if not f.name.startswith(".")]
    regions = _load_region_data(files=files)
    return regions
    
def _load_region_data(files, *args, **kwargs):
    """
    Loads data about the tracts and patches for the given HSC field
    Used to split up data, making it easier to manage

    """
    output = []
    for file in files:
        tracts = _parse_tractfile(file)
        tracts = _parse_tractdata(tracts, *args, **kwargs)
        output.append(tracts)
    return np.hstack(output)


def _parse_tractfile(tractfile):
    tracts = {}
    with open(tractfile) as tf:
        for line in tf:
            if line.startswith('*'):
                continue

            nums = re.findall(r"[-+]?\d*\.\d+|\d+", line)
            tract_num = int(nums[0])
            patch = re.search("Patch", line)
            if patch is None:
                if tract_num not in tracts.keys():
                    tracts.update({tract_num: {'corners': [], 'type': 'tract', 'subregions': {} } } )
                if 'Corner' in line:
                    tracts[tract_num]['corners'].append((float(nums[-2]), float(nums[-1])))
                elif 'Center' in line:
                    tracts[tract_num].update({'center': (float(nums[-2]), float(nums[-1]))})

            else:
                patch = re.findall(r'\d,\d', line)
                patch_val = tuple(map(int, patch[0].split(',')))
                if patch_val not in tracts[tract_num]['subregions'].keys():
                    tracts[tract_num]['subregions'].update({patch_val: {'corners': [], 'type': 'patch'}})
                if 'Corner' in line:
                    tracts[tract_num]['subregions'][patch_val]['corners'].append((float(nums[-2]), float(nums[-1])))
                elif 'Center' in line:
                    tracts[tract_num]['subregions'][patch_val].update({'center': (float(nums[-2]), float(nums[-1]))})
    return tracts

def _parse_tractdata(tractdata, *args, **kwargs):
    output = np.empty(len(tractdata), dtype=object)
    try:
        wanted_tracts = kwargs['tracts']
    except:
        wanted_tracts = []
    for index, (name, tract) in enumerate(tractdata.items()):
        if wanted_tracts and name not in wanted_tracts:
                continue
        corners = tract['corners']
        center = tract['center']
        points = _parse_polygon_corners(center, corners)
        region_obj = Region(points, name=name)

        for patchname, patch in tract['subregions'].items():
            patch_corners = patch['corners']
            patch_center = patch['center']
            patch_points = _parse_polygon_corners(patch_center, patch_corners)
            added = region_obj.add_subregion(name=patchname, subregion = Region(patch_points), ignore_warnings=True)
        output[index] = region_obj
    return output

def _parse_polygon_corners(center, points):
    sorted_coords = sorted(points, key=lambda coord: (-135 - math.degrees(math.atan2(*tuple(map(operator.sub, coord, center))[::-1]))) % 360)

    #This ensures the points are ordered counter-clockwsie, to avoid twisted polygons
    #Shoutout to StackOverflow
    return sorted_coords


