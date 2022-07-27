from pathlib import Path

base = Path(__file__).parents[0]

INSTALL_DIR = base
DATASET_CONFIG_DIR = INSTALL_DIR / "dataset" / "configs"
MAIN_DATASET_CONFIG = DATASET_CONFIG_DIR / "surveys.json"

__all__ = ["SURVEY_CONFIG_DIR", "MAIN_SURVEY_CONFIG"]