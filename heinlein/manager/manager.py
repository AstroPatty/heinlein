from genericpath import isfile
from importlib.resources import path
import pathlib
from sys import implementation
from tkinter import TRUE
import pymongo
import json
from heinlein.locations import BASE_DATASET_CONFIG, BASE_DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG
from heinlein.utilities import warning_prompt, warning_prompt_tf
import shutil
import os
import logging

logger = logging.getLogger("manager")

class Manager:

    def __init__(self, name, *args, **kwargs):
        """
        The datamanger keeps track of where files are located on disk.
        It also keeps a manifest, so it knows when files have been moved or changed.
        
        """
        self.name = name
    
    @staticmethod
    def exists(name: str) -> bool:
        """
        Checks if a datset exists
        """
        with open(MAIN_DATASET_CONFIG, "r") as f:
            surveys = json.load(f)
        if name in surveys.keys():
            return True
        return False



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
            base_config = BASE_DATASET_CONFIG_DIR / cp
            if base_config.exists() and not self.config_location.exists():
                shutil.copy(base_config, self.config_location)
            with open(self.config_location, "r") as f:
                self.config_data = json.load(f)
            self.ready = True

    @staticmethod
    def update_manifest(path: pathlib.Path, *args, **kwargs):
        if path.is_file():
            return
        manifest_file = path / ".heinlein"
        manifest = FileManager.build_manifest(path, recursive = False)
        if manifest_file.exists():
            with open(manifest_file, "r") as f:
                m_data = json.load(f)
            if m_data != manifest:
                with open(manifest_file, "w") as f:
                    json.dump(manifest, f, indent=4)
        else:
            with open(manifest_file, "w") as f:
                json.dump(manifest, f, indent=4)
    
    @staticmethod
    def check_manifest(path: pathlib.Path, recursive = False, modified = False, *args, **kwargs) -> bool:
        if modified:
            FileManager.update_manifest(path)
            return True
        
        if path.is_file() and path.exists():
            return True
        
        manifest_file = path / ".henlein"
        if not manifest_file.exists():
            print(f"Errror: No file maniefest found in {str(path)}")
            return
        good = True  
        with open(manifest_file, "r") as f:
            current_manifest = json.load(f)
        new_manifest = FileManager.build_manifest(path)

        current_files = set(current_manifest['files'].keys())
        new_files = set(new_manifest['files'].keys())

        if current_files != new_files:
            missing = current_files.difference(new_files)
            extra = new_files.difference(current_files)
            if len(missing) > 0:
                logging.warning(f"Warning: some files are missing from {str(path)}")
                good = False
            if len(extra) > 0:
                logging.warning(f"Warning: some extra files found in {str(path)}")
                good = False
        modified = []
        for file in current_files.intersection(new_files):
            if new_manifest['files'][file] != current_manifest['files'][file]:
                modified.append(file)
        
        if len(modified) > 0:
            logging.warning(f"Warning: some files have been modified in {str(path)}")
        if not good:
            logging.warning(f"Pass modfied = True to silence this warning and update the manifest")
        return good

    @staticmethod
    def build_manifest(path: pathlib.Path, *args, **kwargs) -> dict:
        """
        Builds a manifest of files with last-modified dates.
        """
        all = [f for f in path.glob('*') if not f.name.startswith('.')]
        files = []
        folders = []

        for f in all:
            if f.is_file():
                files.append(f)
            else:
                folders.append(str(f))
        files_mod = {str(f): f.stat().st_mtime for f in files}
        manifest = {"files": files_mod, "dirs": folders}
        return manifest

    @staticmethod
    def delete_manifest(path: pathlib.Path, *args, **kwargs) -> None:
        if path.is_file():
            return
        manifest = path / ".heinlein"
        if not path.exists():
            raise FileNotFoundError(f"Path {str(path)} was not initialized properly!")
        else:
            manifest.unlink()

    def write_config(self):
        with open(self.config_location, 'w') as f:
            json.dump(self.config_data, f, indent=4)


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
        try:
            data = self.config_data['data']
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
        self.update_manifest(path)
        self.config_data.update({'data': data})
        with open(self.config_location, 'w') as f:
            json.dump(self.config_data, f, indent=4)
        return True

    def clear_all_data(self, *args, **kwargs) -> None:
        for dtype, path in self.config_data['data'].items():
            self.delete_manifest(pathlib.Path(path)) 
        self.config_data['data'] = {}
        self.write_config()


    def initialize_dataset(self, *args, **kwargs) -> pathlib.Path:
        """
        Initialize a new dataset by name.
        Creates a default configuration file.

        Returns:

        pathlib.Path: The path to the new configuration file.
        """

        default_survey_config_location = DATASET_CONFIG_DIR / "default.json"
        if not default_survey_config_location.exists():
            shutil.copy(BASE_DATASET_CONFIG_DIR / "default.json", default_survey_config_location)
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