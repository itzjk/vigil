"""Build practice/: 12 real segments (6 anomalous, 6 nominal) with the label out of sight.

Reads the selection from practice_selection.json. Each case is written as a PNG and a CSV; the
label and the reason go only into practice/answers.json. It also draws a sheet of nominal
segments from the same channels so that whoever practises knows what "nominal" looks like.

The excerpts come from OPSSAT-AD, so the pack carries the dataset's attribution and licence.
"""
import json
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from opssat import ROOT, UPSTREAM_LICENSE, load_series, load_table

PRACTICE = ROOT / "practice"
SELECTION = json.loads((ROOT / "practice_selection.json").read_text())
# Names from the paper's channel list ("Data Records" section).
SENSORS = {
    "CADC0872": "magnetometer, axis 0", "CADC0873": "magnetometer, axis 1",
    "CADC0874": "magnetometer, axis 2", "CADC0888": "photodiode 3, theta angle",
    "CADC0892": "photodiode 5, theta angle", "CADC0894": "photodiode 6, theta angle",
}
LABELS = {1: "anomaly", 0: "nominal"}
ATTRIBUTION = ("Data excerpted from OPSSAT-AD (Ruszczak, Kotowski, Evans and Nalepa, Scientific "
               "Data 12, 710, 2025; https://doi.org/10.5281/zenodo.15108715), CC BY 4.0 / MIT, "
               "(c) 2024 KP Labs. Timestamps were converted to seconds from segment start.")

INSTRUCTIONS = """# Practice: anomaly or not?

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
"""

DATA_NOTICE = """
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
"""


def series_of(series, segment):
    samples = series[series.segment == segment]
    seconds = (samples.timestamp - samples.timestamp.iloc[0]).dt.total_seconds()
    return seconds.to_numpy(), samples.value.to_numpy()


def draw(axis, seconds, values):
    axis.plot(seconds, values, marker=".", markersize=4, linewidth=0.9, color="#1f4e79")
    axis.grid(alpha=0.3)


def credit(figure):
    figure.text(0.995, 0.005, "Data: OPSSAT-AD, Ruszczak et al. 2025, CC BY 4.0",
                ha="right", va="bottom", fontsize=7, color="#555555")


def main():
    table, series = load_table(), load_series()
    segments = [case["segment"] for case in SELECTION["cases"]]
    chosen = table.loc[segments]
    if not (chosen.train == 1).all():
        raise SystemExit("the practice pack may only use training segments")
    if len(segments) != 12 or len(set(segments)) != 12 or chosen.anomaly.sum() != 6:
        raise SystemExit("the selection needs 12 distinct segments: 6 anomalous and 6 nominal")
    if set(segments) & set(SELECTION["nominal_reference"]):
        raise SystemExit("a practice case cannot also appear in the reference sheet")

    PRACTICE.mkdir(exist_ok=True)
    instructions, answers = INSTRUCTIONS, []
    for number, case in enumerate(SELECTION["cases"], start=1):
        name, row = f"case-{number:02d}", table.loc[case["segment"]]
        seconds, values = series_of(series, case["segment"])
        with open(PRACTICE / f"{name}.csv", "w") as file:
            file.write("t_s,value\n")
            file.writelines(f"{t:.0f},{v!r}\n" for t, v in zip(seconds, values.tolist()))

        figure, axis = plt.subplots(figsize=(9, 4.2))
        draw(axis, seconds, values)
        axis.set_title(f"{name} · channel {row.channel} ({SENSORS[row.channel]}) · one sample every {row.sampling} s")
        axis.set_xlabel("seconds from the start of the segment")
        axis.set_ylabel("value")
        figure.tight_layout(rect=(0, 0.02, 1, 1))
        credit(figure)
        figure.savefig(PRACTICE / f"{name}.png", dpi=110)
        plt.close(figure)

        instructions += (f"| {name} | {row.channel} | {SENSORS[row.channel]} | {len(values)} "
                         f"| {seconds[-1]:.0f} | {row.sampling} |\n")
        answers.append({"case": name, "label": LABELS[int(row.anomaly)], "why": case["why"],
                        "opssat_segment": int(case["segment"]), "channel": row.channel})

    reference = SELECTION["nominal_reference"]
    if table.loc[reference, "anomaly"].any() or not (table.loc[reference, "train"] == 1).all():
        raise SystemExit("the reference sheet only accepts nominal training segments")
    figure, axes = plt.subplots(2, 5, figsize=(17, 6))
    for column, axis_pair in enumerate(axes.T):
        for axis, segment in zip(axis_pair, reference[2 * column: 2 * column + 2]):
            draw(axis, *series_of(series, segment))
            channel = table.channel[segment]
            axis.set_title(f"NOMINAL · {channel} ({SENSORS[channel]})", fontsize=9)
    figure.suptitle("Reference: nominal segments from the channels used in the practice")
    figure.tight_layout(rect=(0, 0.02, 1, 1))
    credit(figure)
    figure.savefig(PRACTICE / "reference-nominal.png", dpi=90)
    plt.close(figure)

    (PRACTICE / "README.md").write_text(instructions + DATA_NOTICE)
    shutil.copyfile(UPSTREAM_LICENSE, PRACTICE / "LICENSE-OPSSAT-AD")
    (PRACTICE / "answers.json").write_text(json.dumps({
        "notice": "Do not open before answering. The label comes from OPSSAT-AD (ESA and KP Labs "
                  "engineers); the reason is our own reading of the plot, the dataset publishes no causes.",
        "attribution": ATTRIBUTION,
        "answers": answers,
    }, indent=2) + "\n")
    print(f"practice/: {len(answers)} cases, "
          f"{sum(a['label'] == 'anomaly' for a in answers)} anomalous, "
          f"{sum(a['label'] == 'nominal' for a in answers)} nominal")


if __name__ == "__main__":
    main()
