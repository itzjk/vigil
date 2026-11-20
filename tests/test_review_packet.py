"""Packets: built as specified, and blind to the label and to anything that leads to it."""
import json
import re

import numpy as np
import pytest

from review import packet
from review.packet import PACKET_FILES, BlindnessError, assert_blind, build_packets, summarise
from review_fixtures import SECRET_SEGMENT, alarm_set, pool

FORBIDDEN_FIELDS = re.compile(r"\b(anomaly|label|segment|train|timestamp)\b", re.IGNORECASE)


def test_packet_has_plot_numbers_summary_and_reference(tmp_path):
    folders = build_packets(alarm_set(), pool(), tmp_path)
    assert len(folders) == 3
    for packet_id, folder in folders.items():
        assert sorted(p.name for p in folder.iterdir()) == sorted(PACKET_FILES)
        summary = json.loads((folder / "summary.json").read_text())
        assert summary["packet_id"] == packet_id == folder.name
        assert summary["channel"] == "CADC0872" and summary["sensor"].startswith("magnetometer")
        assert summary["samples"] == len((folder / "series.csv").read_text().splitlines()) - 1
        assert summary["channel_reference"]["nominal_examples"] == 8
        assert (folder / "plot.png").read_bytes().startswith(b"\x89PNG")
        assert (folder / "reference.png").read_bytes().startswith(b"\x89PNG")


def test_summary_numbers_by_hand():
    seconds = np.array([0, 1, 2, 3, 4, 10, 11, 12], dtype=float)
    values = np.array([1.0, 0.0, 0.0, 0.0, 5.0, 5.5, 5.0, 4.0])
    s = summarise(seconds, values, sampling_s=1)
    assert (s["samples"], s["duration_s"], s["min"], s["max"]) == (8, 12.0, 0.0, 5.5)
    assert s["largest_jump"] == {"size": 5.0, "at_s": 4.0}
    assert s["gaps"] == {"count": 1, "longest_s": 6.0, "longest_at_s": 4.0}
    assert s["zero_runs"] == {"count": 1, "longest_samples": 3, "runs": [[1.0, 3.0]]}


def test_no_label_and_no_segment_number_anywhere_in_a_packet(tmp_path):
    folders = build_packets(alarm_set(), pool(), tmp_path)
    secret = str(SECRET_SEGMENT)
    for folder in folders.values():
        assert secret not in folder.name
        for file in folder.iterdir():
            content = file.read_bytes()
            assert secret.encode() not in content, f"{file.name} carries the dataset segment number"
            if file.suffix != ".png":
                leaked = FORBIDDEN_FIELDS.findall(content.decode())
                assert not leaked, f"{file.name} carries forbidden fields: {leaked}"
    # The way back to the dataset exists only in the private key, outside every packet.
    key = json.loads((tmp_path / "private" / "key.json").read_text())
    assert f"test:{secret}" in key["packets"].values()
    assert not (tmp_path / "packets" / "key.json").exists()


@pytest.mark.parametrize("leak", ["anomaly", "label", "segment", "train", "timestamp"])
def test_guard_fails_when_a_forbidden_field_slips_in(tmp_path, monkeypatch, leak):
    real_summarise = packet.summarise
    monkeypatch.setattr(packet, "summarise", lambda *a: {**real_summarise(*a), leak: 1})
    with pytest.raises(BlindnessError, match=leak):
        build_packets(alarm_set(), pool(), tmp_path)
    assert not list((tmp_path / "packets").glob("*")), "nothing may be written once a leak is detected"


def test_guard_rejects_extra_columns_and_extra_files():
    with pytest.raises(BlindnessError, match="series columns"):
        assert_blind({"channel": "x"}, "t_s,value,anomaly", PACKET_FILES)
    with pytest.raises(BlindnessError, match="packet files"):
        assert_blind({"channel": "x"}, "t_s,value", [*PACKET_FILES, "answers.json"])
    with pytest.raises(BlindnessError, match="nested_segment"):
        assert_blind({"gaps": {"nested_segment": 3}}, "t_s,value", PACKET_FILES)
