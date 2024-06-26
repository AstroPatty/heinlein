from inspect import getmembers


class dataset_extension:
    def __init__(self, function):
        self.function = function
        self.extension = True
        self.name = function.__name__

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)


KNOWN_EXTENSIONS = {}


def load_extensions(dataset, *args, **kwargs):
    """
    Loads extensions for the particular dataset. These are defined externally
    """
    if dataset.name in KNOWN_EXTENSIONS:
        return

    ext_objs = list(
        filter(
            lambda f: isinstance(f[1], dataset_extension),
            getmembers(dataset.manager.external),
        )
    )

    extensions = {f[0]: f[1] for f in ext_objs}
    KNOWN_EXTENSIONS[dataset.name] = extensions


def get_extension(dataset, name):
    """
    Get the extension object for the dataset
    """
    return KNOWN_EXTENSIONS[dataset][name]
