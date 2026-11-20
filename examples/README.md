# Examples: what an anomaly looks like

Twelve real telemetry segments from ESA's OPS-SAT satellite (OPSSAT-AD dataset): six that the
mission engineers flagged as anomalies and six nominal ones, shuffled. They are here so that
anyone can see by eye what the detectors and the reviewers are up against.

Each case is a plot, `case_NN.png`, and its numbers, `case_NN.csv` (`t_s` is seconds from the
start of the segment, `value` is the reading). `reference_nominal.png` shows ten nominal segments
from the same channels. The magnetometers read around ±3e-5; the photodiodes give an angle
between 0 and 1.57 rad.

The labels are kept apart in `answers.json`, so you can judge each case before looking: anomaly
or nominal, what in the plot says so (where, how much), and what you would check next. That file
gives each case's label and our reading of why; the label comes from the dataset, the reason is
ours. `cases.json` is the same list without labels.

| Case | Channel | Sensor | Samples | Duration (s) | Every (s) |
|---|---|---|---:|---:|---:|
| case_01 | CADC0872 | magnetometer, axis 0 | 181 | 180 | 1 |
| case_02 | CADC0872 | magnetometer, axis 0 | 55 | 270 | 5 |
| case_03 | CADC0888 | photodiode 3, theta angle | 81 | 400 | 5 |
| case_04 | CADC0892 | photodiode 5, theta angle | 189 | 188 | 1 |
| case_05 | CADC0873 | magnetometer, axis 1 | 194 | 193 | 1 |
| case_06 | CADC0872 | magnetometer, axis 0 | 286 | 285 | 1 |
| case_07 | CADC0894 | photodiode 6, theta angle | 518 | 517 | 1 |
| case_08 | CADC0872 | magnetometer, axis 0 | 272 | 271 | 1 |
| case_09 | CADC0888 | photodiode 3, theta angle | 32 | 155 | 5 |
| case_10 | CADC0873 | magnetometer, axis 1 | 21 | 100 | 5 |
| case_11 | CADC0894 | photodiode 6, theta angle | 453 | 452 | 1 |
| case_12 | CADC0892 | photodiode 5, theta angle | 155 | 154 | 1 |

## Data attribution and licence

The CSV and PNG files in this folder are excerpts of **OPSSAT-AD**: 22 of its 2,123 segments
(the 12 cases plus the 10 in the reference sheet), about 1% of the dataset. The full dataset is not
redistributed here; `download.py` fetches it from Zenodo.

- Source: Ruszczak, B., Kotowski, K., Evans, D. and Nalepa, J. "The OPS-SAT benchmark for
  detecting anomalies in satellite telemetry". *Scientific Data* 12, 710 (2025).
  <https://doi.org/10.1038/s41597-025-05035-3>. Dataset: <https://doi.org/10.5281/zenodo.15108715>.
- Licence: the Zenodo record declares [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
  the licence file shipped inside the dataset is MIT, (c) 2024 KP Labs, reproduced verbatim in
  `OPSSAT_AD_LICENSE`. These excerpts are shared under those same terms, not under this
  repository's code licence.
- Changes made: segments were selected and renumbered, absolute timestamps were replaced by
  seconds from the start of the segment, the label columns were removed from the CSV files, and
  the plots were drawn by us. The original segment number of each case is in `answers.json`.
- The reasons in `answers.json` are our own reading and are not endorsed by the dataset authors.
