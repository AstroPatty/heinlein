from math import ceil

import numpy as np
from astropy.coordinates import SkyCoord


def warning_prompt(warning: str, options: list) -> str:
    print(warning)
    keys = [opt[0].upper() for opt in options]
    while True:
        for index, option in enumerate(options):
            print(f"{option} ({keys[index]})")
        i = input("?: ")
        if i.upper() in keys:
            return i.upper()
        else:
            print("Invalid option")


def warning_prompt_tf(warning: str) -> bool:
    options = ["Yes", "No"]
    if warning_prompt(warning, options) == "Y":
        return True
    return False


def initialize_grid(bounds, area, density):
    ra1, ra2 = bounds[0], bounds[2]
    dec1, dec2 = bounds[1], bounds[3]
    dra = ra2 - ra1
    ddec = dec2 - dec1
    npoints = round(density * area)
    ratio = ddec / dra
    nra = np.sqrt(npoints / ratio)
    ndec = nra * ratio
    nra = ceil(nra) + 1
    ndec = ceil(ndec) + 1
    dra_ = dra / (nra + 1)
    ddec_ = ddec / (ndec + 1)
    gra = [ra1 + i * dra_ for i in range(1, nra + 1)]
    gdec = [dec1 + i * ddec_ for i in range(1, ndec + 1)]
    x_, y_ = np.meshgrid(gra, gdec)
    cpoints = np.vstack([x_.ravel(), y_.ravel()])
    coords = SkyCoord(cpoints[0], cpoints[1], unit="deg")
    return coords
