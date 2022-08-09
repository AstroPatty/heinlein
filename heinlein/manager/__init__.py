from .managers import get_manager
import shutil

from heinlein.locations import MAIN_DATASET_CONFIG, BASE_DATASET_CONFIG

if not MAIN_DATASET_CONFIG.exists():
    shutil.copy(BASE_DATASET_CONFIG, MAIN_DATASET_CONFIG)


__all__ = ["get_manager"]