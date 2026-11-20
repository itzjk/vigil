"""Blind review packets: everything a reviewer may see about one alarm, and nothing else.

A packet is a folder with the plot of the alarmed segment, its samples (`series.csv`), a numeric
summary (`summary.json`) and a reference sheet of nominal segments from the SAME channel, taken
only from the training split. It never carries the label, the dataset's segment number (which
would let anyone look the label up) or absolute timestamps. Packets are named with a random id;
the id-to-segment key is written outside the packets, under `private/`, and only the scorer
reads it.

Limit worth knowing: the samples themselves are real, so a reviewer with a copy of the dataset
could match them and recover the label. Reviewers must run without access to the dataset.
"""
import json
import random
import secrets
import shutil
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from opssat import ROOT, SENSORS, load_series, load_table

PACKET_FILES = ("plot.png", "series.csv", "summary.json", "reference.png")
SERIES_HEADER = "t_s,value"
# The complete set of keys a summary may contain, at any depth. Anything else is a leak.
SUMMARY_KEYS = frozenset({
    "packet_id", "channel", "sensor", "samples", "duration_s", "sampling_s", "min", "max", "mean",
    "largest_jump", "size", "at_s", "median_step",
    "gaps", "count", "longest_s", "longest_at_s",
    "zero_runs", "longest_samples", "runs",
    "channel_reference", "nominal_examples", "max_p05", "max_p95", "max_highest", "min_lowest",
    "min_p05", "min_p95", "largest_jump_p50", "largest_jump_p95",
})
REFERENCE_EXAMPLES = 6
ZERO_RUN_MIN_SAMPLES = 3
DETECTORS = ("IForest", "KNN", "PCA")


class BlindnessError(Exception):
    """A packet contains something a reviewer must not see."""


@dataclass(frozen=True)
class Alarm:
    """One alarmed segment. `handle` is private: it goes into the key, never into the packet."""
    handle: str
    channel: str
    sampling_s: int
    seconds: np.ndarray
    values: np.ndarray


@dataclass(frozen=True)
class AlarmSet:
    source: str                 # "test" or "examples"
    alarms: dict                # handle -> Alarm
    flagged: dict               # detector name -> list of handles it raised
    universe: list              # every handle the detectors were run on, alarmed or not


def summarise(seconds, values, sampling_s):
    """Label-free numbers describing one segment."""
    steps = np.abs(np.diff(values))
    intervals = np.diff(seconds)
    jump = int(steps.argmax())
    gaps = np.flatnonzero(intervals > 1.5 * sampling_s)
    longest_gap = int(gaps[intervals[gaps].argmax()]) if gaps.size else None

    runs, start = [], None
    for index, is_zero in enumerate(np.append(values == 0, False)):
        if is_zero and start is None:
            start = index
        elif not is_zero and start is not None:
            if index - start >= ZERO_RUN_MIN_SAMPLES:
                runs.append((start, index - 1))
            start = None

    return {
        "samples": int(values.size),
        "duration_s": float(seconds[-1] - seconds[0]),
        "sampling_s": int(sampling_s),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "largest_jump": {"size": float(steps[jump]), "at_s": float(seconds[jump + 1])},
        "median_step": float(np.median(steps)),
        "gaps": {
            "count": int(gaps.size),
            "longest_s": float(intervals[longest_gap]) if gaps.size else 0.0,
            "longest_at_s": float(seconds[longest_gap]) if gaps.size else None,
        },
        "zero_runs": {
            "count": len(runs),
            "longest_samples": max((end - begin + 1 for begin, end in runs), default=0),
            "runs": [[float(seconds[begin]), float(seconds[end])] for begin, end in runs[:5]],
        },
    }


class ReferencePool:
    """Nominal training segments per channel: the only labelled data a packet draws on."""

    def __init__(self, nominal_by_channel):
        # channel -> list of (seconds, values, sampling_s), nominal training segments only
        self._nominal = nominal_by_channel
        self._stats = {}

    def stats(self, channel):
        if channel not in self._stats:
            summaries = [summarise(*example) for example in self._nominal[channel]]
            maxima = [s["max"] for s in summaries]
            minima = [s["min"] for s in summaries]
            jumps = [s["largest_jump"]["size"] for s in summaries]
            self._stats[channel] = {
                "nominal_examples": len(summaries),
                "max_p05": float(np.percentile(maxima, 5)),
                "max_p95": float(np.percentile(maxima, 95)),
                "max_highest": float(max(maxima)),
                "min_lowest": float(min(minima)),
                "min_p05": float(np.percentile(minima, 5)),
                "min_p95": float(np.percentile(minima, 95)),
                "largest_jump_p50": float(np.percentile(jumps, 50)),
                "largest_jump_p95": float(np.percentile(jumps, 95)),
            }
        return self._stats[channel]

    def draw_sheet(self, channel, path):
        examples = self._nominal[channel]
        # Seeded by the channel name, so every run shows the same examples.
        shown = random.Random(channel).sample(examples, min(REFERENCE_EXAMPLES, len(examples)))
        figure, axes = plt.subplots(2, 3, figsize=(13, 6))
        for axis, example in zip(axes.ravel(), shown):
            _draw(axis, example[0], example[1])
            axis.set_title(f"NOMINAL · every {example[2]} s", fontsize=9)
        for axis in axes.ravel()[len(shown):]:
            axis.set_axis_off()
        figure.suptitle(f"Reference: nominal training segments of channel {channel} ({SENSORS[channel]})")
        figure.tight_layout(rect=(0, 0.02, 1, 1))
        _credit(figure)
        figure.savefig(path, dpi=80)
        plt.close(figure)


def _draw(axis, seconds, values):
    axis.plot(seconds, values, marker=".", markersize=4, linewidth=0.9, color="#1f4e79")
    axis.grid(alpha=0.3)


def _credit(figure):
    figure.text(0.995, 0.005, "Data: OPSSAT-AD, Ruszczak et al. 2025, CC BY 4.0",
                ha="right", va="bottom", fontsize=7, color="#555555")


def _keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


def assert_blind(summary, series_header, file_names):
    """Refuse a packet whose contents go beyond the allowed, label-free schema."""
    unexpected = sorted(set(_keys(summary)) - SUMMARY_KEYS)
    if unexpected:
        raise BlindnessError(f"summary carries fields outside the blind schema: {unexpected}")
    if series_header != SERIES_HEADER:
        raise BlindnessError(f"series columns must be exactly '{SERIES_HEADER}', got '{series_header}'")
    if sorted(file_names) != sorted(PACKET_FILES):
        raise BlindnessError(f"packet files must be exactly {sorted(PACKET_FILES)}, got {sorted(file_names)}")


def write_packet(directory, packet_id, alarm, pool, sheet_path):
    """Write one packet folder and return its summary."""
    seconds = alarm.seconds - alarm.seconds[0]
    summary = {"packet_id": packet_id, "channel": alarm.channel, "sensor": SENSORS[alarm.channel],
               **summarise(seconds, alarm.values, alarm.sampling_s),
               "channel_reference": pool.stats(alarm.channel)}
    assert_blind(summary, SERIES_HEADER, PACKET_FILES)

    directory.mkdir(parents=True)
    with open(directory / "series.csv", "w") as file:
        file.write(SERIES_HEADER + "\n")
        file.writelines(f"{t:.0f},{v!r}\n" for t, v in zip(seconds, alarm.values.tolist()))
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    shutil.copyfile(sheet_path, directory / "reference.png")

    figure, axis = plt.subplots(figsize=(9, 4.2))
    _draw(axis, seconds, alarm.values)
    axis.set_title(f"{packet_id} · channel {alarm.channel} ({SENSORS[alarm.channel]}) · "
                   f"one sample every {alarm.sampling_s} s")
    axis.set_xlabel("seconds from the start of the segment")
    axis.set_ylabel("value")
    figure.tight_layout(rect=(0, 0.02, 1, 1))
    _credit(figure)
    figure.savefig(directory / "plot.png", dpi=100)
    plt.close(figure)
    return summary


def build_packets(alarm_set, pool, run_dir):
    """Write a packet per alarmed segment plus the private key; return {packet_id: folder}."""
    packets_dir, private_dir, sheets_dir = run_dir / "packets", run_dir / "private", run_dir / "private" / "sheets"
    sheets_dir.mkdir(parents=True)
    handles = list(alarm_set.alarms)
    random.SystemRandom().shuffle(handles)   # packet order must not mirror the dataset's order
    key, folders = {}, {}
    for handle in handles:
        alarm = alarm_set.alarms[handle]
        packet_id = f"pkt_{secrets.token_hex(5)}"
        sheet = sheets_dir / f"{alarm.channel}.png"
        if not sheet.exists():
            pool.draw_sheet(alarm.channel, sheet)
        write_packet(packets_dir / packet_id, packet_id, alarm, pool, sheet)
        key[packet_id] = handle
        folders[packet_id] = packets_dir / packet_id
    by_handle = {handle: packet_id for packet_id, handle in key.items()}
    (private_dir / "key.json").write_text(json.dumps({
        "warning": "Private. Maps packets back to the dataset; reviewers must never see this file.",
        "source": alarm_set.source,
        "packets": key,
        "alarms": {detector: sorted(by_handle[h] for h in raised)
                   for detector, raised in alarm_set.flagged.items()},
        "universe": alarm_set.universe,
    }, indent=2) + "\n")
    return folders


def _series_by_segment(series):
    grouped = {}
    for segment, samples in series.groupby("segment", sort=False):
        seconds = (samples.timestamp - samples.timestamp.iloc[0]).dt.total_seconds().to_numpy()
        grouped[segment] = (seconds, samples.value.to_numpy())
    return grouped


def _pool(table, series, excluded=()):
    """Reference pool from nominal TRAINING segments; this is the one place a label is read."""
    nominal = table[(table.train == 1) & (table.anomaly == 0) & ~table.index.isin(list(excluded))]
    return ReferencePool({
        channel: [(*series[segment], int(rows.sampling[segment])) for segment in rows.index]
        for channel, rows in nominal.groupby("channel")
    })


def alarms_on_test_split(detectors=DETECTORS):
    """Alarms raised by the unsupervised detectors on the official test split."""
    table, series = load_table(), _series_by_segment(load_series())
    test = table.loc[table.train == 0, ["channel", "sampling"]]   # no label column from here on
    flagged = {}
    for detector in detectors:
        predictions = pd.read_csv(ROOT / "results" / "predictions" / f"{detector}.csv")
        flagged[detector] = [f"test:{s}" for s in predictions.loc[predictions.prediction == 1, "segment"]]
    alarms = {}
    for handle in sorted({h for raised in flagged.values() for h in raised}):
        segment = int(handle.split(":")[1])
        alarms[handle] = Alarm(handle, test.channel[segment], int(test.sampling[segment]), *series[segment])
    universe = [f"test:{segment}" for segment in test.index]
    return AlarmSet("test", alarms, flagged, universe), _pool(table, series)


def alarms_from_examples():
    """The 12 example segments, all treated as alarms, to run the circuit end to end."""
    folder = ROOT / "examples"
    alarms = {}
    for case in json.loads((folder / "cases.json").read_text()):
        samples = pd.read_csv(folder / f"{case['case']}.csv")
        handle = f"examples:{case['case']}"
        alarms[handle] = Alarm(handle, case["channel"], case["sampling_s"],
                               samples.t_s.to_numpy(dtype=float), samples.value.to_numpy())
    # The examples are training segments: keep them out of their own reference pool.
    selection = json.loads((ROOT / "examples_selection.json").read_text())
    excluded = [case["segment"] for case in selection["cases"]]
    table, series = load_table(), _series_by_segment(load_series())
    alarm_set = AlarmSet("examples", alarms, {"all_flagged": list(alarms)}, list(alarms))
    return alarm_set, _pool(table, series, excluded)
