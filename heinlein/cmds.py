import sys
import json
import argparse

from heinlein.locations import INSTALL_DIR, MAIN_CONFIG_DIR
from heinlein.manager.managers import FileManager
from heinlein.utilities import warning_prompt_tf
from heinlein.manager.dataManger import get_all
import numpy as np
from pathlib import Path

def add(args) -> bool:
    """
    Add a location on disk to a dataset
    """
    cwd = Path.cwd()
    name = args.dataset_name
    dtype = args.dtype
    path = args.path

    if path != 'cwd':
        path = cwd / path
    else:
        path = cwd
    if not path.exists():
        print(f"Error: {path} not found!")
        return
    manager = FileManager(name)
    manager.add_data(dtype, path)
    return True

def remove(args):
    name = args.dataset_name
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    dtype = args.dtype
    mgr = FileManager(name)
    mgr.remove_data(dtype)
    return True

def clear(args) -> bool:
    """
    Clear all data from a dataset
    """
    name = args.dataset_name
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    msg = f"This will delete all references to data for the {name} dataset." \
                                " Are you sure you want to do this?"
    delete = warning_prompt_tf(msg)

    if delete:
        mgr = FileManager(name)
        mgr.clear_all_data()
    return True

def get(args) -> bool:
    """
    Get the path to a specific data type in a specific datset
    """
    name = args.dataset_name
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    dtype = args.dtype
    mgr = FileManager(name)
    path = mgr.get_path(dtype)
    if path:
        print(str(path))
    return True

def list_all(args) -> None:
    surveys = get_all()
    data = {name: d.get("data", []) for name, d in surveys.items()}
    if len(data) == 0 or all([len(d) == 0 for d in data.values()]):
        print("No data found!")
        return
    header = "DATASET".ljust(20) + "AVAILABLE DATA"
    print(header)
    print("-"*len(header))
    for name, dtypes in data.items():
        s1 = name
        s2 = ",".join(list(dtypes.keys()))
        print(s1.ljust(20) + s2)
