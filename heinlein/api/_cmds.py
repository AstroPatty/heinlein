from genericpath import isfile
import multiprocessing
import pathlib
from heinlein.locations import INSTALL_DIR, MAIN_CONFIG_DIR
from heinlein.config import globalConfig
from heinlein.manager.managers import FileManager
from heinlein.utilities import warning_prompt_tf, split_catalog
from heinlein.manager.dataManger import get_all
import numpy as np
from pathlib import Path

def add(name, dtype, path) -> bool:
    """
    Add a location on disk to a dataset
    """
    cwd = Path.cwd()

    if path != 'cwd':
        path = cwd / path
    else:
        path = cwd
    if not path.exists():
        print(f"Error: {path} not found!")
        return
    manager = FileManager(name)
    manager.add_data(dtype, path) 
    print(f"Sucessfully added datatype {dtype} to dataset {name}")
    return True

def remove(name: str, dtype: str):
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    mgr = FileManager(name)
    mgr.remove_data(dtype)
    return True

def get_path(name: str, dtype:str) -> pathlib.Path:
    """
    Get the path to a specific data type in a specific datset
    """
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    mgr = FileManager(name)
    try:
        path = mgr.get_path(dtype)
        return path
    except KeyError:
        print(f"No data of dtype {dtype} found for dataset {name}")

def list_all():
    surveys = get_all()
    data = {name: d.get("data", []) for name, d in surveys.items()}
    return data

