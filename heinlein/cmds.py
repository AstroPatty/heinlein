from genericpath import isfile
import multiprocessing
from heinlein.locations import INSTALL_DIR, MAIN_CONFIG_DIR
from heinlein.config import globalConfig
from heinlein.manager.managers import FileManager
from heinlein.utilities import warning_prompt_tf, split_catalog
from heinlein import api
import numpy as np
from pathlib import Path

def add(args) -> bool:
    """
    Add a location on disk to a dataset
    """
    name = args.dataset_name
    dtype = args.dtype
    path = args.path    
    api.add(name, dtype, path)
    return True

def remove(args):
    name = args.dataset_name
    dtype = args.dtype
    api.remove(name, dtype)
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

def get_path(args) -> bool:
    """
    Get the path to a specific data type in a specific datset
    """
    name = args.dataset_name
    dtype = args.dtype
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    path = api.get_path(name, dtype)
    if path is not None:
        print(str(path))

def list_all(args) -> None:
    data = api.list_all()
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

def split(args) -> None:
    path = Path(args.input_path)
    args.input_path = path
    if not path.exists():
        print(f"Error: path {path} does not exist!")
    else:
        args.input_path = path
    if args.threads == 1 and globalConfig.interactive:
        print("Warning: Splitting large datasets takes a long time")
        print("We recommend using more than a single thread")
        print("You can increase this number with the -t flag in the future")
        while True:
            nthreads = input("How many threads would you like to use? ")
            try:
                max_threads = multiprocessing.cpu_count()
                nthreads = int(nthreads)
                if max_threads < nthreads:
                    print(f"Error: Maximum number of threads available on this machine is {max_threads}")
                    continue
                elif nthreads < 1:
                    print(f"Error: I need at least one thread!")
                    continue

                break
            except ValueError:
                print("Number of threads must be an integer")
        args.threads = nthreads

    if args.output == None:
        if path.is_file():
            output_path = path.parents[0]
        else:
            output_path = path
        args.output = output_path
    split_catalog(args)
