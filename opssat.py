"""Single access point to OPSSAT-AD: paths, the official split and the raw series."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "opssat-ad"
RAW_SERIES = DATA_DIR / "segments.csv"
UPSTREAM_LICENSE = DATA_DIR / "LICENSE"
# Zenodo holds two versions of the feature table. The split and the labels are identical;
# `duration`, `gaps_squared` and `var_div_duration` differ in part of the segments.
# "current" is the one the DOI resolves to today and the one this project uses; "paper" is
# the first upload, which is the one the published numbers come from.
FEATURE_TABLES = {
    "current": DATA_DIR / "dataset.csv",
    "paper": ROOT / "data" / "opssat-ad-v1" / "dataset.csv",
}

# The 18 features and their order are those of the dataset's modeling_examples.ipynb notebook.
FEATURES = [
    "mean", "var", "std", "len", "duration", "len_weighted", "gaps_squared", "n_peaks",
    "smooth10_n_peaks", "smooth20_n_peaks", "var_div_duration", "var_div_len",
    "diff_peaks", "diff2_peaks", "diff_var", "diff2_var", "kurtosis", "skew",
]


def load_table(version="current"):
    """One row per segment: features, the `anomaly` label and the `train` split flag."""
    return pd.read_csv(FEATURE_TABLES[version], index_col="segment")


def load_split(version="current"):
    """Return (train, test) following the official `train` column (1 = train)."""
    table = load_table(version)
    return table[table.train == 1], table[table.train == 0]


def load_series():
    """Raw samples of every segment, with the timestamp already parsed."""
    return pd.read_csv(RAW_SERIES, parse_dates=["timestamp"])
