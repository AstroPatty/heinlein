import shutil

from heinlein.locations import BASE_DATASET_CONFIG, MAIN_DATASET_CONFIG

from .managers import get_manager

if not MAIN_DATASET_CONFIG.exists():
    shutil.copy(BASE_DATASET_CONFIG, MAIN_DATASET_CONFIG)


__all__ = ["get_manager"]
