from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

DEFAULT_FEATURE_DB_PATH = DATA_DIR / "feature.db"
DEFAULT_BUY_STRENGTH_DB_PATH = DATA_DIR / "buy_strength.db"
DEFAULT_BUY_MODEL_ROOT = MODELS_DIR / "buy"
DEFAULT_BUY_REGISTRY_PATH = DEFAULT_BUY_MODEL_ROOT / "registry.json"
DEFAULT_BUY_TMP_OUTPUT_DIR = OUTPUTS_DIR / "tmp" / "buy_sub_ml"
