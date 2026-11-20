# Sources, licences and citations

Checked on 2026-11-20 against Zenodo, GitHub and Scientific Data.

## OPSSAT-AD (downloaded; this is what the project uses)

- **What it is:** real telemetry from ESA's OPS-SAT CubeSat, 9 channels (3 magnetometers and 6
  photodiodes), 2,123 hand-labelled segments: 1,594 for training (321 anomalous) and 529 for testing
  (113 anomalous).
- **Where:** Zenodo, DOI [10.5281/zenodo.15108715](https://doi.org/10.5281/zenodo.15108715) (current
  version, uploaded 2025-03-30). Authors' code: <https://github.com/kplabs-pl/OPS-SAT-AD>.
- **Size:** `segments.csv` 19.0 MB (303,493 samples) and `dataset.csv` 0.5 MB (one row per segment).
- **Licence:** the Zenodo record declares **CC BY 4.0**; the `LICENSE` file shipped inside the dataset
  (and the GitHub repository) is **MIT**, copyright 2024 KP Labs. Both allow use and redistribution with
  attribution.
- **What this repository redistributes:** not the dataset. `download.py` fetches it and keeps the original
  `LICENSE` next to it. The only excerpts committed here are the 22 segments of the practice pack (about
  1% of the dataset), with attribution, a statement of changes and the upstream licence text in
  `practice/`. `results/predictions/` holds our detectors' outputs keyed by the dataset's segment number,
  and `published.json` quotes the figures of the paper's Table 3; neither contains telemetry.
- **Two versions of the feature table.** The first upload (DOI
  [10.5281/zenodo.12588359](https://doi.org/10.5281/zenodo.12588359), 2024-07-09) and the current one share
  the split and the labels, but `duration` and `var_div_duration` differ in 317 segments and `gaps_squared`
  in 559. The paper's numbers come from the first. It is downloaded too (0.5 MB), only to verify that.
- **Citation:** Ruszczak, B., Kotowski, K., Evans, D. and Nalepa, J. "The OPS-SAT benchmark for detecting
  anomalies in satellite telemetry". *Scientific Data* 12, 710 (2025).
  <https://doi.org/10.1038/s41597-025-05035-3> (open access, CC BY 4.0; preprint arXiv:2407.04730).

## ESA-ADB (noted, NOT downloaded)

- **What it is:** annotated real telemetry from three ESA missions; the benchmark uses two.
- **Where:** Zenodo, concept DOI [10.5281/zenodo.12528695](https://doi.org/10.5281/zenodo.12528695); today
  it resolves to the 2025-04-17 version, [zenodo.org/records/15237121](https://zenodo.org/records/15237121).
  Code: <https://github.com/kplabs-pl/ESA-ADB> (MIT).
- **Size:** 11.6 GB compressed in three files: `ESA-Mission1.zip` 3.78 GB, `ESA-Mission2.zip` 4.10 GB and
  `ESA-Mission3.zip` 3.73 GB. We have not measured the uncompressed size.
- **Licence:** **CC BY 3.0 IGO** (attribution, intergovernmental-organisation variant). It allows use and
  redistribution with attribution to ESA.
- **Citation:** Kotowski, K. et al. "European Space Agency Benchmark for Anomaly Detection in Satellite
  Telemetry". arXiv:2406.17826 (2024).
