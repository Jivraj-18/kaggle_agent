import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("KAGGLE_AGENT_STATE_DIR", PROJECT_ROOT / "state"))
COMPETITIONS_DIR = PROJECT_ROOT / "competitions"
