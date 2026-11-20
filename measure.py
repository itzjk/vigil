"""The project's single scorer: takes predictions and returns the metrics.

Usage:
    python measure.py predictions.csv [--truth data/opssat_ad/dataset.csv] [--all]

`predictions.csv` has the columns `segment` and `prediction` (1 = anomaly, 0 = nominal) and,
if AUC is wanted, `score` (higher = more anomalous). By default it scores against the official
OPSSAT-AD test split; with --all, against every segment in the truth file.

Convention when a ratio is undefined (no predicted or no real positives): the metric is 0, as
scikit-learn does with zero_division=0. The AUCs are None when the truth has a single class.
"""
import argparse
import json
import math
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _binary(values, name):
    vector = np.asarray(values)
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional list")
    if not np.isin(vector, (0, 1)).all():
        raise ValueError(f"{name} only accepts 0 and 1")
    return vector.astype(int)


def measure(truth, prediction, score=None):
    """Binary classification metrics; the positive class (1) is "anomaly"."""
    truth = _binary(truth, "truth")
    prediction = _binary(prediction, "prediction")
    if truth.size != prediction.size:
        raise ValueError("truth and prediction differ in length")

    tp = int(((truth == 1) & (prediction == 1)).sum())
    fp = int(((truth == 0) & (prediction == 1)).sum())
    fn = int(((truth == 1) & (prediction == 0)).sum())
    tn = int(((truth == 0) & (prediction == 0)).sum())

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    metrics = {
        "n": int(truth.size),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": (tp + tn) / truth.size,
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
        # F0.5 weighs precision twice as much as recall; it is the ESA-ADB metric.
        "f0_5": _ratio(1.25 * precision * recall, 0.25 * precision + recall),
        "mcc": _ratio(tp * tn - fp * fn,
                      math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))),
        # Share of the raised alarms that were false: what the review layer has to bring down.
        "false_alarm_share": _ratio(fp, tp + fp),
        "auc_pr": None,
        "auc_roc": None,
    }
    if score is not None:
        score = np.asarray(score, dtype=float)
        if score.shape != truth.shape or not np.isfinite(score).all():
            raise ValueError("score must be finite and as long as truth")
        if 0 < truth.sum() < truth.size:
            metrics["auc_pr"] = float(average_precision_score(truth, score))
            metrics["auc_roc"] = float(roc_auc_score(truth, score))
    return metrics


def measure_file(predictions_path, truth_path, test_only=True):
    """Score a predictions CSV against the truth; it must cover exactly the same segments."""
    truth = pd.read_csv(truth_path, index_col="segment")
    if test_only:
        truth = truth[truth.train == 0]
    predictions = pd.read_csv(predictions_path)
    if predictions.segment.duplicated().any():
        raise ValueError("the predictions contain repeated segments")
    predictions = predictions.set_index("segment")
    extra = predictions.index.difference(truth.index)
    missing = truth.index.difference(predictions.index)
    if len(extra) or len(missing):
        raise ValueError(f"unexpected segments: {len(extra)}; missing segments: {len(missing)}")
    predictions = predictions.loc[truth.index]
    score = predictions.score if "score" in predictions else None
    return measure(truth.anomaly, predictions.prediction, score)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("predictions")
    parser.add_argument("--truth", default="data/opssat_ad/dataset.csv")
    parser.add_argument("--all", action="store_true",
                        help="score against every segment, not only the test split")
    options = parser.parse_args()
    try:
        metrics = measure_file(options.predictions, options.truth, not options.all)
    except ValueError as error:
        sys.exit(f"measure.py: {error}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
