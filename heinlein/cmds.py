import sys
import json
from heinlein.locations import INSTALL_DIR
from heinlein.manager import FileManager
from heinlein.utilities import warning_prompt_tf
import numpy as np
from pathlib import Path

def main(*args, **kwargs):
    """
    Entrypoint for "heinlein" command
    """
    cmd_config_location = INSTALL_DIR / "cmds.json"
    with open(cmd_config_location) as f:
        cmds = json.load(f) 
    try:
        cmd = sys.argv[1]
    except IndexError:
        raise NotImplementedError
    
    if cmd in cmds.keys():
        info = cmds[cmd]
        options = sys.argv[2:]
        option_required = np.array([o['required'] for o in info['options'].values()])
        n_required = np.count_nonzero(option_required)

        if len(options) < n_required:
            print(f"Error: command requires a minimum of {n_required} options but only recieved {len(options)}")
            print()
            print_help(cmd, info)
            return False
        elif sys.argv[2] == "help":
            print_help(cmd, cmds[cmd])
            return
        
        try:
            this = sys.modules[__name__]
            f = getattr(this, cmd)
            run = f(sys.argv[2:], cmd, cmds[cmd], *args, **kwargs)
            if not run:
                print_help(cmd, cmds[cmd])
        except AttributeError:
            raise NotImplementedError(cmd)

def print_help(name, info):
    desc = info['description']
    options = info['options']
    substr = " ".join(list(options.keys()))
    example = f"heinlein {name} {substr}"
    print(f"{name}: {desc}\n")

    print("OPTIONS:")
    for n, details in options.items():
        print(f"{n}: {details['description']}")
    print()
    print("EXAMPLE USAGE:")
    print(example)


def add(options: list, info: dict, *args, **kwargs) -> bool:
    """
    Add a location on disk to a dataset
    """
    cwd = Path.cwd()
    name = options[0]
    dtype = options[1]
    try:
        path = Path(options[2])
        path = cwd / path
    except IndexError:
        path = cwd
    if not path.exists():
        print("Error: f{path} not found!")
        return
    manager = FileManager(name)
    manager.add_data(dtype, path)
    return True

def remove(options: dict, info: dict, *args, **kwargs):
    name = options[0]
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    dtype = options[1]
    mgr = FileManager(name)
    mgr.remove_data(dtype)
    return True

def clear(options: dict, info: dict, *args, **kwargs) -> bool:
    """
    Clear all data from a dataset
    """
    name = options[0]
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

def get(options: dict, info: dict, *args, **kwargs) -> bool:
    """
    Get the path to a specific data type in a specific datset
    """
    name = options[0]
    if not FileManager.exists(name):
        print(f"Error: dataset {name} does not exist!")
        return True
    dtype = options[1]
    mgr = FileManager(name)
    path = mgr.get_data(dtype)
    if path:
        print(str(path))
    return True