from pathlib import Path

from heinlein.manager.manager import get_manager, initialize_dataset
from heinlein.utilities import prep, warning_prompt_tf

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
        data_manager = get_manager(name)
    except FileNotFoundError:
        if not force:
            write_new = warning_prompt_tf(
                f"Survey {name} not found, would you like to initialize it? "
            )
            if not write_new:
                print("Aborting...")
                return
        initialize_dataset(name, path)
        data_manager = get_manager(name)

    data_manager.add_data(dtype, path)
    return True


def remove(name: str, dtype: str):
    """
    Remove a datatype from a dataset
    """
    try:
        manager = get_manager(name)
    except FileNotFoundError:
        print(f"Error: dataset {name} does not exist!")
        return True

    manager.remove_data(dtype)
    return True


def get(name: str, dtype: str) -> Path:
    """
    Get the path to a specific data type in a specific datset
    """
    try:
        manager = get_manager(name)
    except FileNotFoundError:
        print(f"Error: dataset {name} does not exist!")
    path = manager.get_path(dtype)

    return path


def prep_catalog(name: str, path: Path):
    """
    Prepare a catalog for a dataset. The path should be a directory containing
    the data as CSV files. The database will be created in the same directory.
    """
    if path.suffix == ".sqlite3":
        prep.register_database(name, path)

    csvs = list(path.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {path}")
    prep.database_from_csvs(name, csvs)
