from importlib.resources import path
import pathlib
from sys import implementation
import pymongo
import json
from heinlein.locations import MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR

class Manager:

    def __init__(self, name, *args, **kwargs):
        """
        The datamanger keeps track of where files are located on disk.
        It also keeps a manifest, so it knows when files have been moved or changed.
        
        """
        self.name = name
    
    def warning_prompt(self, warning: str, options: list) -> str:
        print(warning)
        keys = [l[0].upper() for l in options]
        while True:
            for index, option in enumerate(options):
                print(f"{option} ({keys[index]})")
            i = input("?: ")
            if i.upper() in keys:
                return i.upper()
            else:
                print("Invalid option")


    def warning_prompt_tf(self, warning: str) -> bool:
        options = ["Yes", "No"]
        if self.warning_prompt(warning, options) == "Y":
            return True
        return False



class FileManager(Manager):

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.setup()

    def setup(self, *args, **kwargs):
        with open(MAIN_DATASET_CONFIG, "r") as f:
            surveys = json.load(f)
        if self.name not in surveys.keys():
            write_new = self.warning_prompt_tf(f"Survey {self.name} not found, would you like to initialize it? ")
            if write_new:
                self.config_location = self.initialize_survey()
            else:
                self.ready = False
        else:
            cp = surveys[self.name]['config_path']
            self.config_location = DATASET_CONFIG_DIR / cp
            self.ready = True
    
    def add_data(self, dtype: str, path: pathlib.Path) -> bool:
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
            choice = self.warning_prompt(msg, options)        
            if choice == "A":
                return False
            elif choice == "M":
                raise NotImplementedError
        
        data.update({dtype: str(path)})
        config_data.update({'data': data})
        with open(self.config_location, 'w') as f:
            json.dump(config_data, f, indent=4)
        return True

    def initialize_survey(self, *args, **kwargs):
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
        
        return output_location
