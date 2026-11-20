"""Scorer tests: a perfect case, null cases and a known case worked out by hand."""
import math

import pandas as pd
import pytest

from measure import measure, measure_file

# Known case: 10 segments, 4 anomalous.
TRUTH = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]
SCORE = [0.9, 0.8, 0.7, 0.3, 0.6, 0.5, 0.4, 0.2, 0.1, 0.05]
PREDICTION = [1, 1, 1, 0, 1, 1, 0, 0, 0, 0]  # score > 0.45


def test_perfect_case():
    m = measure(TRUTH, TRUTH, score=TRUTH)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (4, 0, 0, 6)
    for key in ("accuracy", "precision", "recall", "f1", "f0_5", "mcc", "auc_pr", "auc_roc"):
        assert m[key] == pytest.approx(1.0), key
    assert m["false_alarm_share"] == 0.0


def test_null_case_never_alarms():
    m = measure(TRUTH, [0] * 10)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (0, 0, 4, 6)
    assert m["accuracy"] == pytest.approx(0.6)  # gets the 6 nominal ones right, detects nothing
    for key in ("precision", "recall", "f1", "f0_5", "mcc", "false_alarm_share"):
        assert m[key] == 0.0, key
    assert m["auc_pr"] is None and m["auc_roc"] is None


def test_null_case_always_alarms():
    m = measure(TRUTH, [1] * 10)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (4, 6, 0, 0)
    assert m["precision"] == pytest.approx(0.4)
    assert m["recall"] == 1.0
    assert m["mcc"] == 0.0


def test_known_case_by_hand():
    m = measure(TRUTH, PREDICTION, SCORE)
    # Confusion matrix: 3 hits, 2 false alarms, 1 missed anomaly, 4 nominal ones left alone.
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (3, 2, 1, 4)
    assert m["accuracy"] == pytest.approx(7 / 10)
    assert m["precision"] == pytest.approx(3 / 5)
    assert m["recall"] == pytest.approx(3 / 4)
    assert m["f1"] == pytest.approx(2 * 0.6 * 0.75 / 1.35)            # 0.6667
    assert m["f0_5"] == pytest.approx(1.25 * 0.45 / (0.15 + 0.75))    # 0.6250
    assert m["mcc"] == pytest.approx((3 * 4 - 2 * 1) / math.sqrt(5 * 4 * 6 * 5))  # 0.4082
    assert m["false_alarm_share"] == pytest.approx(2 / 5)
    # ROC AUC: correctly ordered (anomalous, nominal) pairs = 6 + 6 + 6 + 3 = 21 of 24.
    assert m["auc_roc"] == pytest.approx(21 / 24)
    # PR AUC (average precision): the anomalous ones land in ranks 1, 2, 3 and 7.
    assert m["auc_pr"] == pytest.approx((1 + 1 + 1 + 4 / 7) / 4)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        measure(TRUTH, [0] * 9)
    with pytest.raises(ValueError):
        measure(TRUTH, [2] * 10)
    with pytest.raises(ValueError):
        measure([], [])
    with pytest.raises(ValueError):
        measure(TRUTH, PREDICTION, [float("nan")] * 10)


def test_file_requires_the_same_segments(tmp_path):
    truth = tmp_path / "truth.csv"
    pd.DataFrame({"segment": range(1, 11), "anomaly": TRUTH,
                  "train": [0] * 8 + [1] * 2}).to_csv(truth, index=False)
    complete = tmp_path / "complete.csv"
    # Shuffled on purpose: the scorer aligns on `segment`, not on position.
    pd.DataFrame({"segment": range(8, 0, -1), "prediction": PREDICTION[:8][::-1],
                  "score": SCORE[:8][::-1]}).to_csv(complete, index=False)
    m = measure_file(complete, truth)
    assert (m["n"], m["tp"], m["fp"], m["fn"], m["tn"]) == (8, 3, 2, 1, 2)

    incomplete = tmp_path / "incomplete.csv"
    pd.DataFrame({"segment": range(1, 8), "prediction": PREDICTION[:7]}).to_csv(incomplete, index=False)
    with pytest.raises(ValueError, match="missing segments: 1"):
        measure_file(incomplete, truth)
