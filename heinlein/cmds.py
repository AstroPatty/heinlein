import sys
import json
from heinlein.locations import INSTALL_DIR
from heinlein.manager.manager import FileManager
import numpy as np
from pathlib import Path

def main(*args, **kwargs):
    """
    Entrypoint for "heinlein" command
    """
    cmd_config_location = INSTALL_DIR / "cmds.json"
    with open(cmd_config_location) as f:
        cmds = json.load(f) 
    cmd = sys.argv[1]
    if cmd in cmds.keys():
        if sys.argv[2] == "help":
            print_help(cmd, cmds[cmd])
            return
        info = cmds[cmd]
        options = sys.argv[2:]
        option_required = np.array([o['required'] for o in info['options'].values()])
        n_required = np.count_nonzero(option_required)

        if len(options) < n_required:
            print(f"Error: command requires a minimum of {n_required} options but only recieved {len(options)}")
            print()
            print_help(cmd, info)
            return False

        
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


def add(options: dict, info: dict, *args, **kwargs) -> bool:
    """
    Add a location on disk to a dataset
    """
    name = options[0]
    dtype = options[1]
    try:
        path = Path(options[3])
    except IndexError:
        path = Path.cwd()
    if not path.exists():
        print("Error: f{path} not found!")
        return
    
    manager = FileManager(name)
    manager.add_data(dtype, path)
    return True

