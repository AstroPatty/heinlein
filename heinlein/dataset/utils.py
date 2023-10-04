from importlib import import_module
from types import ModuleType

known_datasets = ["des", "cfht", "hsc", "ms"]


def get_external_implementation(name: str) -> ModuleType:
    """
    Checks to see if a custom implementation exists for a given dataset. These have
    to be installed separately from the main package. Prompts the user to install
    the package if it is not found, but is known.
    """
    if name in known_datasets:
        # try to import it
        module_name = "heinlein_" + name
        try:
            module = import_module(module_name)
        except ImportError:
            print(
                f"Dataset `{name}` is a known dataset, but needs to be installed"
                f" separately. You can install it with `heinlein install {name}`."
            )
            return None
    return getattr(module, name)
