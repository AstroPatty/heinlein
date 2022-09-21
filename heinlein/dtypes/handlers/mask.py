from pathlib import Path
from .handler import Handler
import numpy as np
from astropy.io import fits
import logging
from heinlein.dtypes import mask

def get_mask_handler(path: Path, dconfig: dict):
    try:
        mask_type = dconfig['mask_type']
    except KeyError:
        raise KeyError("Tried to load this mask but no mask type is specificed in the config file!")

    if mask_type == "fits":
        return FitsMaskHandler(path, dconfig)


class FitsMaskHandler(Handler):
    def __init__(self, path: Path, config: dict, *args ,**kwargs):
        super().__init__(path, config, "mask")


    def get_data(self, regions, *args, **kwargs):
        files = [f for f in self._path.glob("*.fits") if not f.name.startswith(".")]
        names = [r.name for r in regions]
        output = {}
        for name in names:
            matches = list(filter(lambda x: name in x.name, files))
            if len(matches) > 1:
                logging.error(f"Error: Found more than one mask for region {name}")
                continue


            data = fits.open(matches[0])
            out = np.empty(1, dtype="object")
            out[0] = data
            output.update({name: out})
        

        return output

    def get_data_object(self, data, *args, **kwargs):
        storage = np.empty(len(data), dtype=object)
        for index, value in enumerate(data.values()):
            storage[index] = value[0]
        return mask.Mask(storage, **self._config)
