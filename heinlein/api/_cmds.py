from genericpath import isfile
import pathlib
from heinlein import manager
from heinlein.manager.dataManger import get_all
import numpy as np
from pathlib import Path

"""
Backend API functions
"""

def add(name, dtype, path, *args, **kwargs) -> bool:
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
    
    mgr = manager.get_manager(name)
    mgr.add_data(dtype, path, *args, **kwargs)
    return True

def remove(name: str, dtype: str):
    """
    Remove a datatype from a dataset
    """
    if not manager.managers.FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    mgr = manager.get_manager(name)
    mgr.remove_data(dtype)
    return True

def get_path(name: str, dtype:str) -> pathlib.Path:
    """
    Get the path to a specific data type in a specific datset
    """
    if not manager.managers.FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    mgr = manager.get_manager(name)
    try:
        path = mgr.get_path(dtype)
        return path
    except KeyError:
        print(f"No data of dtype {dtype} found for dataset {name}")

def list_all():
    """
    List all available data
    """
    surveys = get_all()
    data = {name: d.get("data", []) for name, d in surveys.items()}
    return data

