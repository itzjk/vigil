"""Baseline: classic detectors from the OPSSAT-AD paper on the official split.

Follows the protocol of the dataset's modeling_examples.ipynb notebook: 18 features per
segment, a scaler fitted only on the nominal training segments, seed 2137 and default
parameters. The unsupervised detectors are fitted on the whole training split without looking
at labels and raise an alarm above the 80th percentile of their training scores
(contamination 0.2, as in the paper); that is what PyOD does, replicated here with scikit-learn.

It runs twice: on the feature table currently on Zenodo ("current", the one this project uses)
and on the first upload ("paper"), which is the one the published numbers come from.

Writes results/baseline.json, results/baseline.md and, for the current version, each
detector's predictions under results/predictions/.
"""
import json
import warnings

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA
from sklearn.ensemble import AdaBoostClassifier, IsolationForest
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

from measure import measure
from opssat import FEATURES, ROOT, load_split

SEED = 2137
CONTAMINATION = 0.2
RESULTS = ROOT / "results"
PUBLISHED = json.loads((ROOT / "published.json").read_text())
COLUMNS = PUBLISHED["columns"]


def isolation_forest(x_train, x_test):
    forest = IsolationForest(n_estimators=100, random_state=SEED).fit(x_train)
    return -forest.score_samples(x_train), -forest.score_samples(x_test)


def k_nearest_neighbours(x_train, x_test, k=5):
    """Score = distance to the k-th training neighbour (PyOD's KNN, "largest" method)."""
    neighbours = NearestNeighbors(n_neighbors=k).fit(x_train)
    # Called without arguments, kneighbors() leaves the point itself out, as PyOD does on fit.
    return neighbours.kneighbors()[0][:, -1], neighbours.kneighbors(x_test)[0][:, -1]


def principal_components(x_train, x_test):
    """Sum of distances to each principal axis, weighted by 1/explained variance (PyOD's PCA)."""
    scaler = StandardScaler().fit(x_train)
    pca = PCA(random_state=SEED).fit(scaler.transform(x_train))

    def score(x):
        return (cdist(scaler.transform(x), pca.components_) / pca.explained_variance_ratio_).sum(axis=1)

    return score(x_train), score(x_test)


SUPERVISED = {
    "AdaBoost": lambda: AdaBoostClassifier(random_state=SEED),
    "LR": lambda: LogisticRegression(random_state=SEED),
    "LSVC": lambda: LinearSVC(dual=True, random_state=SEED),
}
UNSUPERVISED = {
    "IForest": isolation_forest,
    "KNN": k_nearest_neighbours,
    "PCA": principal_components,
}


def predict_all(version):
    """Return the test split and, per detector, (prediction, score) on it."""
    train, test = load_split(version)
    scaler = StandardScaler().fit(train.loc[train.anomaly == 0, FEATURES])
    x_train = scaler.transform(train[FEATURES])
    x_test = scaler.transform(test[FEATURES])

    outputs = {}
    for name, build in SUPERVISED.items():
        with warnings.catch_warnings():
            # LSVC does not converge within the default 1,000 iterations. Left as is on
            # purpose: the paper uses default parameters and only so is its number reproduced.
            warnings.simplefilter("ignore", ConvergenceWarning)
            model = build().fit(x_train, train.anomaly)
        outputs[name] = (model.predict(x_test), model.decision_function(x_test))
    for name, score in UNSUPERVISED.items():
        on_train, on_test = score(x_train, x_test)
        threshold = np.percentile(on_train, 100 * (1 - CONTAMINATION))
        outputs[name] = ((on_test > threshold).astype(int), on_test)
    return test, outputs


ORIGINS = {"current": "ours, current data", "paper": "ours, paper's data"}
TITLES = {"auc_pr": "AUC PR", "auc_roc": "AUC ROC", "accuracy": "Accuracy", "f1": "F1",
          "precision": "Precision", "recall": "Recall", "mcc": "MCC"}


def results_table(results):
    lines = ["| Detector | Origin | " + " | ".join(TITLES[c] for c in COLUMNS) + " | TP | FP | FN | TN |",
             "|---|---|" + "---:|" * (len(COLUMNS) + 4)]
    for name, row in results.items():
        for version, origin in ORIGINS.items():
            ours = row[version]
            lines.append(f"| {name} | {origin} | " + " | ".join(f"{ours[c]:.3f}" for c in COLUMNS)
                         + f" | {ours['tp']} | {ours['fp']} | {ours['fn']} | {ours['tn']} |")
        lines.append(f"| {name} | published | "
                     + " | ".join(f"{row['published'][c]:.3f}" for c in COLUMNS) + " | | | | |")
    return "\n".join(lines) + "\n"


def differences_table(results):
    """Largest absolute gap to the published value, per detector and data version."""
    lines = ["| Detector | Largest gap, current data | Largest gap, paper's data |",
             "|---|---:|---:|"]
    for name, row in results.items():
        cells = []
        for version in ORIGINS:
            column = max(COLUMNS, key=lambda c: abs(row["difference"][version][c]))
            cells.append(f"{row['difference'][version][column]:+.3f} ({TITLES[column]})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main():
    (RESULTS / "predictions").mkdir(parents=True, exist_ok=True)
    results = {name: {"published": dict(zip(COLUMNS, PUBLISHED["detectors"][name])),
                      "difference": {}}
               for name in [*SUPERVISED, *UNSUPERVISED]}
    for version in ORIGINS:
        test, outputs = predict_all(version)
        for name, (prediction, score) in outputs.items():
            if version == "current":
                pd.DataFrame({"segment": test.index, "prediction": prediction, "score": score}
                             ).to_csv(RESULTS / "predictions" / f"{name}.csv", index=False)
            ours = measure(test.anomaly, prediction, score)
            row = results[name]
            row[version] = ours
            # Compared at 3 decimals, the precision the paper publishes with.
            row["difference"][version] = {c: round(round(ours[c], 3) - row["published"][c], 3)
                                          for c in COLUMNS}
    (RESULTS / "baseline.json").write_text(json.dumps(results, indent=2) + "\n")
    report = results_table(results) + "\n" + differences_table(results)
    (RESULTS / "baseline.md").write_text(report)
    print(f"Test split: {len(test)} segments, {int(test.anomaly.sum())} anomalous\n")
    print(report)


if __name__ == "__main__":
    main()
