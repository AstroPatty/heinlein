from importlib.resources import path
import pathlib
from sys import implementation
import pymongo
import json
from heinlein.locations import MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR
from heinlein.cmds import warning_prompt, warning_prompt_tf

class Manager:

    def __init__(self, name, *args, **kwargs):
        """
        The datamanger keeps track of where files are located on disk.
        It also keeps a manifest, so it knows when files have been moved or changed.
        
        """
        self.name = name


class FileManager(Manager):

    def __init__(self, name: str, *args, **kwargs) -> None:
        """
        A file manager manages files on local disk.
        This is in contrast to data stored in the cloud
        Or data in a database

        Params:

        name: the name of the dataset
        """
        super().__init__(name, *args, **kwargs)
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """
        Performs basic setup of the file manager
        Loads datset if it exists, or prompts
        user if dataset does not exist.
        """
        with open(MAIN_DATASET_CONFIG, "r") as f:
            surveys = json.load(f)
        if self.name not in surveys.keys():
            write_new = warning_prompt_tf(f"Survey {self.name} not found, would you like to initialize it? ")
            if write_new:
                self.config_location = self.initialize_dataset()
            else:
                self.ready = False
        else:
            cp = surveys[self.name]['config_path']
            self.config_location = DATASET_CONFIG_DIR / cp
            self.ready = True
    
    def add_data(self, dtype: str, path: pathlib.Path) -> bool:
        """
        Add data to a datset. Note that this only gives the manager
        a path to the data. The manager itself does not know what kind
        of data it is or how to use it. Usually this will be invoked
        by a command line script.

        Params:

        dtype <str>: Type of data being added (i.e. "catalog")
        path <pathlib.Path>: Path to the data

        Returns:

        bool: Whether or not the file was sucessfully added
        """
        if not self.ready:
            return False
        with open(self.config_location, "r") as f:
            config_data = json.load(f)
        try:
            data = config_data['data']
        except KeyError:
            data = {}

        if dtype in data.keys():
            msg = f"Datatype {dtype} already found for survey {self.name}."
            options = ["Overwrite", "Merge", "Abort"]
            choice = warning_prompt(msg, options)        
            if choice == "A":
                return False
            elif choice == "M":
                raise NotImplementedError
        
        data.update({dtype: str(path)})
        config_data.update({'data': data})
        with open(self.config_location, 'w') as f:
            json.dump(config_data, f, indent=4)
        return True

    def initialize_dataset(self, *args, **kwargs) -> pathlib.Path:
        """
        Initialize a new dataset by name.
        Creates a default configuration file.

        Returns:

        pathlib.Path: The path to the new configuration file.
        """

        default_survey_config_location = DATASET_CONFIG_DIR / "default.json"
        with open(default_survey_config_location, "r") as f:
            default_survey_config = json.load(f)
        
        default_survey_config.update({'name': self.name, "survey_region": "None", "implementation": False})
        output_location = DATASET_CONFIG_DIR / f"{self.name}.json"
        with open(output_location, "w") as f:
            json.dump(default_survey_config, f, indent=4)

        all_survey_config_location = DATASET_CONFIG_DIR / "surveys.json"
        with open(all_survey_config_location, "r+") as f:
            data = json.load(f)
            f.seek(0)
            f.truncate(0)
            data.update({self.name: {'config_path': f"{self.name}.json"}})
            json.dump(data, f, indent=4)
        
        self.ready = True
        return output_location
