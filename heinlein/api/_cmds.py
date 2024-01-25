from pathlib import Path

from godata import load_project
from godata.project import GodataProjectError

from heinlein.manager.dataManger import initialize_dataset
from heinlein.utilities import warning_prompt_tf

"""
Backend API functions
"""


def add(name, dtype, path, overwrite=False, *args, **kwargs) -> bool:
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
        project = load_project(name, ".heinlein")
    except GodataProjectError:
        write_new = warning_prompt_tf(
            f"Survey {name} not found, would you like to initialize it? "
        )
        if not write_new:
            print("Aborting...")
            return
        initialize_dataset(name, path)
        project = load_project(name, ".heinlein")

    project.link(path, "data/" + dtype, overwrite=overwrite)
    return True


def remove(name: str, dtype: str):
    """
    Remove a datatype from a dataset
    """
    try:
        project = load_project(name, ".heinlein")
    except GodataProjectError:
        print(f"Error: dataset {name} does not exist!")
        return True

    project.remove("data/" + dtype)
    return True
