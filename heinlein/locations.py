from pathlib import Path
import appdirs

base = Path(__file__).parents[0]

data_dir = Path(appdirs.user_data_dir("heinlein"))
 
INSTALL_DIR = base
BASE_DATASET_CONFIG_DIR = INSTALL_DIR / "dataset" / "configs"
BASE_DATASET_CONFIG = BASE_DATASET_CONFIG_DIR / "surveys.json"

DATASET_CONFIG_DIR = data_dir / "datasets"
DATASET_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
MAIN_DATASET_CONFIG = DATASET_CONFIG_DIR / "surveys.json"
__all__ = ["BASE_DATASET_CONFIG_DIR", "MAIN_DATASET_CONFIG", "DATASET_CONFIG_DIR", "MAIN_DATASET_CONFIG"]