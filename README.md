# vigil

Satellite anomaly detectors raise too many false alarms. vigil measures that on real telemetry from ESA's
OPS-SAT (the public OPSSAT-AD benchmark) and implements a review layer that checks every alarm before a
person sees it. The baseline is reproduced against the published numbers; the review layer runs end to
end but has no real reviewer behind it yet, so there is no review result to report.

Made by ZERACK.

## Baseline

Six classic detectors from the OPSSAT-AD paper, re-implemented with scikit-learn only and run on the
official test split (529 segments, 113 anomalous). "Published" is Table 3 of Ruszczak et al., *Scientific
Data* 12, 710 (2025). Each cell is precision / recall / F1.

| Detector | Kind | Ours, current data | Ours, paper's data | Published | False alarms (current data) |
|---|---|---|---|---|---:|
| AdaBoost | supervised | 0.904 / 0.832 / 0.866 | 0.890 / 0.788 / 0.836 | 0.890 / 0.788 / 0.836 | 10 of 104 alarms (10%) |
| LR | supervised | 0.920 / 0.708 / 0.800 | 0.920 / 0.708 / 0.800 | 0.920 / 0.708 / 0.800 | 7 of 87 (8%) |
| LSVC | supervised | 0.911 / 0.726 / 0.808 | 0.911 / 0.726 / 0.808 | 0.911 / 0.726 / 0.808 | 8 of 90 (9%) |
| IForest | unsupervised | 0.304 / 0.301 / 0.302 | 0.297 / 0.292 / 0.295 | 0.297 / 0.292 / 0.295 | 78 of 112 (70%) |
| KNN | unsupervised | 0.596 / 0.549 / 0.571 | 0.596 / 0.549 / 0.571 | 0.594 / 0.558 / 0.575 | 42 of 104 (40%) |
| PCA | unsupervised | 0.364 / 0.354 / 0.359 | 0.367 / 0.354 / 0.360 | 0.360 / 0.354 / 0.357 | 70 of 110 (64%) |

All seven metrics of the paper (AUC PR, AUC ROC, accuracy, F1, precision, recall, MCC) and the confusion
counts are in [`results/baseline.md`](results/baseline.md).

**What matches and what does not**

- On the paper's data (the first Zenodo upload), AdaBoost, LR, LSVC and IForest are **identical** to the
  published values on all seven metrics.
- On the current data (the version the DOI resolves to today, and the one vigil uses), AdaBoost is 0.030
  higher in F1 and 0.044 in recall, and IForest 0.007 and 0.009. Verified cause: Zenodo changed three
  features (`duration`, `gaps_squared`, `var_div_duration`) between versions and the paper's table was not
  recomputed.
- KNN and PCA do not fully match on either version: KNN gives 62 detections and 42 false alarms against a
  published 63 and 43 (F1 0.571 against 0.575); PCA gives 1 or 2 fewer false alarms (F1 0.359 or 0.360
  against 0.357). The AUCs do match, so the scores are the same and what moves is one segment next to the
  threshold. Our replica gives exactly the same output as PyOD 1.1.2, the library the paper used
  (threshold and predictions compared one by one), so the likely cause is a different PyOD or data version
  behind those two rows. We could not verify that.
- LSVC does not converge with default parameters. It is left that way because that is how the paper's
  number is reproduced.

## Why it matters

The detectors that need no labels are the ones an operator can actually deploy on a new satellite, and
they are noisy: of the three reproduced here, between 4 and 7 out of every 10 alarms are false (70% for
Isolation Forest, 64% for PCA, 40% for KNN), while they still miss between 45% and 70% of the real
anomalies. An operator who gets seven false alarms out of ten stops trusting the alarm.

That gap is where a review layer comes in: agents that take each alarm, look at the signal, explain what
they see, propose what to do, and hand it to a person who signs off. Nothing here shows yet that such a
layer works. What vigil fixes is the starting line and the ruler, so that any reviewer can be measured
honestly: fewer false positives, no extra missed anomalies, same test split, same scorer.

## Run it

```sh
./run.sh
```

One command: it creates a virtual environment, downloads OPSSAT-AD from Zenodo with checksum verification
(about 20 MB), runs the tests, reproduces the baseline, rebuilds the examples and runs the review circuit
on them. It takes about a minute and a half and under 300 MB of memory on a laptop. It needs Python 3.9 to
3.12 (choose one with `PYTHON=/path/to/python ./run.sh`); the pinned versions are the ones the dataset
itself pins.

To score any set of predictions against the test split:

```sh
.venv/bin/python measure.py my_predictions.csv   # columns: segment, prediction (0/1), optional score
```

## Review layer

The circuit that reviews alarms is implemented and tested end to end, under `review/`:

- **Blind packets** (`packet.py`). For every alarm an unsupervised detector raises on the test split (162
  distinct segments across IForest, KNN and PCA) it writes a folder with the plot, the samples, a numeric
  summary (channel, sensor, samples, duration, minimum, maximum, jumps, gaps) and a reference sheet of
  nominal segments from the same channel, taken only from the training split. A packet never carries the
  label, the dataset's segment number or absolute timestamps; a guard refuses to write one that does, and
  a test fails if any of them slips in. The packet-to-segment key lives outside the packets.
- **Pluggable reviewers** (`reviewer.py`). A reviewer takes a packet and returns validated JSON: `verdict`
  (`anomaly`, `nominal` or `unsure`), `confidence` between 0 and 1, `reason` (one sentence citing something
  visible: where and how much) and `next_check`. Two exist: a fixed rule, and an external command set with
  `VIGIL_REVIEWER_CMD`, which receives the packet folder as its last argument and prints the JSON. That
  socket is where our own agent system plugs in. Malformed output is rejected and recorded as `unsure`; it
  is never repaired or guessed.
- **A two-review panel** (`panel.py`). Each alarm gets two independent reviews; each reviewer works on its
  own copy of the packet and cannot see the other's answer. The rule: **dismissed** only if both say
  nominal with confidence of at least 0.8; **confirmed** if both say anomaly; anything else (disagreement,
  any `unsure`, a rejected review) is **escalated** to a person.
- **An append-only ledger** (`ledger.py`). Every packet, review and decision goes to a JSONL file with a
  UTC time, the reviewer's version and a hash chain, so a rewritten line is detected. It is the evidence
  needed before any kind of case is allowed to go automatic.
- **A scorer** (`score.py`), the only place the labels enter. Per detector: alarms before and after, false
  alarms removed, real anomalies lost to a wrong dismissal, alarms escalated to a person, and precision /
  recall / F1 before and after, computed with `measure.py`.

```sh
./review.sh --examples              # the whole circuit on the 12 example segments, with the fixed rule
./review.sh --test --packets-only   # build the 162 test packets, review nothing
./review.sh --test --external       # review the test alarms with the program in VIGIL_REVIEWER_CMD
```

**The fixed-rule reviewer is a test double.** It compares the largest jump in the segment with the
channel's nominal jumps and exists only to check that the circuit works. Its output in
[`results/review_examples.md`](results/review_examples.md) is **not a result**: it covers the 12
hand-picked example segments, and it wrongly dismisses 2 of the 6 real anomalies there, which is exactly
the kind of loss the scorer is there to expose. The program refuses to run it on the test split.

One known limit of the blinding: the samples are real, so a reviewer holding a copy of the dataset could
match them and recover the label. Reviewers must run without the dataset.

## Examples

[`examples/`](examples/README.md) holds twelve real segments, six anomalous and six nominal, as plots and
CSV files, with a sheet of nominal references and the labels kept apart in `answers.json`. They show by
eye what the problem looks like, and they are what `./review.sh --examples` runs on.

## What is in the repository

| Path | What it is |
|---|---|
| `run.sh` | The single command |
| `download.py` | Fetches OPSSAT-AD from Zenodo and checks the md5 (the data is not committed) |
| `opssat.py` | Single loader: official split, the 18 features, raw series |
| `baseline.py` | Six classic detectors from the paper, scikit-learn only |
| `measure.py` | The single scorer |
| `review/`, `review.sh` | The review layer: packets, reviewers, panel, ledger, scorer |
| `tests/` | Tests for the scorer and for every part of the review layer |
| `published.json` | The figures of the paper's Table 3, with their source |
| `results/` | `baseline.md`, `baseline.json`, each detector's predictions, `review_examples.md` |
| `examples/`, `build_examples.py`, `examples_selection.json` | The twelve example segments and how they are built |
| `SOURCES.md` | Licences and citations for OPSSAT-AD and ESA-ADB |

## Not done

- **No real reviewer has been run.** The only reviewer exercised so far is the fixed-rule test double, and
  nothing has been reviewed on the test split. There is no evidence here that review reduces false alarms.
- **The paper's neural network** (FCNN, the best published model, F1 0.946) is not reproduced; vigil
  avoids deep-learning dependencies. Of the 30 algorithms in the paper, 6 are reproduced.
- **ESA-ADB**, the larger ESA benchmark (11.6 GB compressed), is documented in `SOURCES.md` but not
  downloaded or used. Its metric is event-wise F0.5; `measure.py` reports segment-wise F0.5 only.
- OPSSAT-AD is small and comes from a single CubeSat. It is good for tuning a method, not for broad claims.

## Data, citation and licences

- **Code:** MIT, see [`LICENSE`](LICENSE). Copyright (c) 2026 ZERACK.
- **Data:** OPSSAT-AD is **not redistributed** in this repository; `download.py` fetches it from Zenodo
  (DOI [10.5281/zenodo.15108715](https://doi.org/10.5281/zenodo.15108715)). The Zenodo record declares
  CC BY 4.0 and the licence file inside the dataset is MIT, (c) 2024 KP Labs. The only excerpts committed
  are the 22 segments of [`examples/`](examples/README.md) (about 1% of the dataset), which carry their
  own attribution, a statement of changes and the upstream licence text, and are shared under the
  dataset's terms rather than this repository's code licence.
- **Cite the dataset authors** if you use any of this:
  Ruszczak, B., Kotowski, K., Evans, D. and Nalepa, J. "The OPS-SAT benchmark for detecting anomalies in
  satellite telemetry". *Scientific Data* 12, 710 (2025). <https://doi.org/10.1038/s41597-025-05035-3>
- Details, including ESA-ADB (CC BY 3.0 IGO), are in [`SOURCES.md`](SOURCES.md).

vigil is independent work and is not affiliated with or endorsed by ESA, KP Labs or the dataset authors.

Versión en español: [`README.es.md`](README.es.md).
