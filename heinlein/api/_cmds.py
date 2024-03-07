from pathlib import Path

from heinlein.manager.manager import DataManager, initialize_dataset
from heinlein.utilities import warning_prompt_tf

"""
Backend API functions
"""


def add(name, dtype, path, force=False, *args, **kwargs) -> bool:
    """
    Add a location on disk to a dataset
    """
    cwd = Path.cwd()

    if path != "cwd":
        path = cwd / path
    else:
        path = cwd
    if not path.exists():
        print(f"Error: {path} not found!")
        return

    try:
        data_manager = DataManager(name)
    except FileNotFoundError:
        if not force:
            write_new = warning_prompt_tf(
                f"Survey {name} not found, would you like to initialize it? "
            )
            if not write_new:
                print("Aborting...")
                return
        initialize_dataset(name, path)
        data_manager = DataManager(name)

    data_manager.add_data(dtype, path)
    return True


def remove(name: str, dtype: str):
    """
    Remove a datatype from a dataset
    """
    try:
        manager = DataManager(name)
    except FileNotFoundError:
        print(f"Error: dataset {name} does not exist!")
        return True

    manager.remove_data(dtype)
    return True
