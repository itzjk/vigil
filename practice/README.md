# Practice: anomaly or not?

12 real telemetry segments from ESA's OPS-SAT satellite (OPSSAT-AD dataset). Some are anomalies
flagged by the mission engineers and some are nominal; they are shuffled.

For each case look at `case-NN.png` (and `case-NN.csv` for the numbers: `t_s` is seconds from the
start of the segment and `value` is the reading) and answer:

1. Anomaly or nominal?
2. Why, in one sentence that cites what is visible (where, how much).
3. What you would check next to confirm it.

`reference-nominal.png` shows ten nominal segments from the same channels. The magnetometers read
around ±3e-5; the photodiodes give an angle between 0 and 1.57 rad.

Do not open `answers.json` before answering all 12. It holds each case's label and our reading of
why; the label comes from the dataset, the reason is ours.

| Case | Channel | Sensor | Samples | Duration (s) | Every (s) |
|---|---|---|---:|---:|---:|
| case-01 | CADC0872 | magnetometer, axis 0 | 181 | 180 | 1 |
| case-02 | CADC0872 | magnetometer, axis 0 | 55 | 270 | 5 |
| case-03 | CADC0888 | photodiode 3, theta angle | 81 | 400 | 5 |
| case-04 | CADC0892 | photodiode 5, theta angle | 189 | 188 | 1 |
| case-05 | CADC0873 | magnetometer, axis 1 | 194 | 193 | 1 |
| case-06 | CADC0872 | magnetometer, axis 0 | 286 | 285 | 1 |
| case-07 | CADC0894 | photodiode 6, theta angle | 518 | 517 | 1 |
| case-08 | CADC0872 | magnetometer, axis 0 | 272 | 271 | 1 |
| case-09 | CADC0888 | photodiode 3, theta angle | 32 | 155 | 5 |
| case-10 | CADC0873 | magnetometer, axis 1 | 21 | 100 | 5 |
| case-11 | CADC0894 | photodiode 6, theta angle | 453 | 452 | 1 |
| case-12 | CADC0892 | photodiode 5, theta angle | 155 | 154 | 1 |

## Data attribution and licence

The CSV and PNG files in this folder are excerpts of **OPSSAT-AD**: 22 of its 2,123 segments
(12 cases plus the 10 in the reference sheet), about 1% of the dataset. The full dataset is not
redistributed here; `download.py` fetches it from Zenodo.

- Source: Ruszczak, B., Kotowski, K., Evans, D. and Nalepa, J. "The OPS-SAT benchmark for
  detecting anomalies in satellite telemetry". *Scientific Data* 12, 710 (2025).
  <https://doi.org/10.1038/s41597-025-05035-3>. Dataset: <https://doi.org/10.5281/zenodo.15108715>.
- Licence: the Zenodo record declares [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
  the licence file shipped inside the dataset is MIT, (c) 2024 KP Labs, reproduced verbatim in
  `LICENSE-OPSSAT-AD`. These excerpts are shared under those same terms, not under this
  repository's code licence.
- Changes made: segments were selected and renumbered, absolute timestamps were replaced by
  seconds from the start of the segment, the label columns were removed from the CSV files, and
  the plots were drawn by us. The original segment number of each case is in `answers.json`.
- The reasons in `answers.json` are our own reading and are not endorsed by the dataset authors.
