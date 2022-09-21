import atexit
import pathlib
import json
from heinlein.locations import BASE_DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG, DATASET_CONFIG_DIR, MAIN_DATASET_CONFIG
from heinlein.utilities import warning_prompt, warning_prompt_tf
from typing import Any
import shutil
import logging
from copy import copy
from heinlein.manager.dataManger import DataManager

logger = logging.getLogger("manager")

active_managers = {}

def get_manager(name):
    try:
        am = active_managers[name]
        return am
    except KeyError:
        mgr = FileManager(name)
        active_managers.update({name: mgr})
        return mgr

class FileManager(DataManager):

    def __init__(self, name: str, *args, **kwargs) -> None:
        """
        A file manager manages files on local disk.
        This is in contrast to data stored in the cloud
        Params:

        name: the name of the dataset
        """
        super().__init__(name, *args, **kwargs)
        self.setup()
    def setup(self, *args, **kwargs):
        self.ready = True

    @staticmethod
    def update_manifest(path: pathlib.Path, *args, **kwargs) -> None:
        """
        Updates a file manifest
        """
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
        """
        Checks to ensure that a folder manifest is current.
        """
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
    @property
    def config(self):
        return self.config_data

    def write_config(self):
        output = copy(self.config_data)
        output.update({'data': self._data})
        with open(self.config_location, 'w') as f:
            json.dump(output, f, indent=4)


    def add_data(self, dtype: str, path: pathlib.Path, overwrite=False) -> bool:
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
            data = self._data
        except AttributeError:
            data = {}

        if dtype in data.keys() and not overwrite:
            msg = f"Datatype {dtype} already found for survey {self.name}."
            options = ["Overwrite", "Merge", "Abort"]
            choice = warning_prompt(msg, options)        
            if choice == "A":
                return False
            elif choice == "M":
                raise NotImplementedError
        
        self.update_manifest(path)
        self._data.update({dtype: {"path": str(path)}})
        self.write_config()
        return True

    def remove_data(self, dtype: str) -> bool:
        """
        Remove data from a datset. Usually this will be invoked
        by a command line script.

        Params:

        dtype <str>: Type of data being added (i.e. "catalog")

        Returns:

        bool: Whether or not the file was sucessfully removed
        """
        try:
            d = self._data[dtype]
            path = d['path']
        except KeyError:
            print(f"Error: dataset {self.name} has no data of type {dtype}")
            return False
        path = pathlib.Path(path)
        if not path.is_file():
            self.delete_manifest(path)
        self._data.pop(dtype)
        self.write_config()
            
    def get_handler(self, dtype: str, *args, **kwargs):
        pass
            
    def clear_all_data(self, *args, **kwargs) -> None:
        for dtype, path in self._data.items():
            self.delete_manifest(pathlib.Path(path)) 
        self._data = {}
        self.write_config()
