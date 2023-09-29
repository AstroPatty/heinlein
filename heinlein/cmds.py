import multiprocessing
from pathlib import Path

from godata import list_projects, load_project
from godata.project import GodataProjectError

from heinlein import api
from heinlein.config import globalConfig
from heinlein.manager.managers import FileManager
from heinlein.utilities import split_catalog, warning_prompt_tf


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
    msg = (
        f"This will delete all references to data for the {name} dataset."
        " Are you sure you want to do this?"
    )
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


def list(args) -> None:
    if args.dataset_name is None:
        try:
            project_names = list_projects(".heinlein")
            print("KNOWN DATASETS")
            print("-" * 20)
            for name in project_names:
                print(name)
        except GodataProjectError:
            print("No datasets found!")
    else:
        try:
            project = load_project(args.dataset_name, ".heinlein")
            print(f"DATASET: {args.dataset_name}")
            print("-" * 20)
            for dtype in project:
                print(dtype)
        except GodataProjectError:
            print(f"Error: dataset {args.dataset_name} does not exist!")


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
                    print(
                        f"Error: Maximum number of threads available "
                        f"on this machine is {max_threads}"
                    )
                    continue
                elif nthreads < 1:
                    print("Error: I need at least one thread!")
                    continue

                break
            except ValueError:
                print("Number of threads must be an integer")
        args.threads = nthreads

    if args.output is None:
        if path.is_file():
            output_path = path.parents[0]
        else:
            output_path = path
        args.output = output_path
    split_catalog(args)
