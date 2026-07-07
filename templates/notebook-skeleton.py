"""Kaggle notebook skeleton.

Generated notebooks should remain outside Git. This file is a reviewable
template for coding agents to copy into the artifact location or Google
Drive-backed workspace, then fill in per the approved plan.

SUMMARY (fill in before push, keep at the top so a human/Reviewer/Summarizer
can read intent in 10 seconds without re-deriving it from code):
    experiment_key:  <from `experiments add`>
    hypothesis:      <one sentence>
    what_changed:    <vs. the last experiment in this family>
"""

import random
from pathlib import Path

import numpy as np
import pandas as pd

# Verified live (2026-07-07, titanic): a kernel linked to a competition via
# `competition_sources` in kernel-metadata.json (i.e. pushed via this repo's
# `notebooks push`, not created from the competition page's "New Notebook"
# button) mounts data under /kaggle/input/competitions/<slug>/, NOT
# /kaggle/input/<slug>/. See state/dev_pitfalls.md.
INPUT_DIR = Path("/kaggle/input/competitions/<competition-slug>")
WORKING_DIR = Path("/kaggle/working")
SUBMISSION_PATH = WORKING_DIR / "submission.csv"
TARGET_COLUMN = "<target>"
ID_COLUMN = "<id>"
SEED = 42
N_FOLDS = 5


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(INPUT_DIR / "train.csv")
    test = pd.read_csv(INPUT_DIR / "test.csv")
    print(f"train shape: {train.shape}, test shape: {test.shape}")
    return train, test


def engineer_features(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Fit any encoder/scaler/imputer inside the CV loop in train_and_validate, not
    # here, unless it is provably leakage-free (e.g. a stateless row-wise transform).
    raise NotImplementedError("Developer persona: implement the approved feature plan.")


def train_and_validate(train: pd.DataFrame) -> tuple[list, float]:
    """Return (fitted models per fold, mean CV score). Print each fold's score
    as it completes — pulled logs are how Reviewer/Summarizer see CV evidence
    without re-running the notebook."""
    raise NotImplementedError("Developer persona: implement the approved model plan.")


def predict(models: list, test: pd.DataFrame) -> np.ndarray:
    raise NotImplementedError("Developer persona: average/ensemble fold predictions.")


def write_submission(test: pd.DataFrame, predictions: np.ndarray) -> None:
    submission = pd.DataFrame({ID_COLUMN: test[ID_COLUMN], TARGET_COLUMN: predictions})
    submission.to_csv(SUBMISSION_PATH, index=False)
    print(f"wrote {SUBMISSION_PATH}, shape={submission.shape}")


def main() -> None:
    set_seed()
    train, test = load_data()
    train, test = engineer_features(train, test)
    models, cv_score = train_and_validate(train)
    print(f"mean CV score: {cv_score:.5f}")
    predictions = predict(models, test)
    write_submission(test, predictions)


if __name__ == "__main__":
    main()
