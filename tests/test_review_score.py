"""Scoring a review run: counts by hand, and the whole circuit on synthetic alarms."""
import json

import pytest

from review.ledger import Ledger
from review.packet import build_packets
from review.panel import review_alarm
from review.reviewer import RuleReviewer
from review.score import report, score_run
from review_fixtures import SECRET_SEGMENT, alarm_set, pool


def write_run(tmp_path, decisions):
    """A run with 5 alarms out of 8 segments; `decisions` maps packet -> decision."""
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "key.json").write_text(json.dumps({
        "source": "test",
        "packets": {f"p{i}": f"test:{i}" for i in range(1, 6)},
        "alarms": {"Det": ["p1", "p2", "p3", "p4", "p5"]},
        "universe": [f"test:{i}" for i in range(1, 9)],
    }))
    ledger = Ledger(tmp_path / "ledger.jsonl")
    for packet_id, decision in decisions.items():
        ledger.append("review", {"packet_id": packet_id, "slot": 1, "reviewer": "fake", "reviewer_version": "1",
                                 "test_double": True, "review": {}, "rejection": None})
        ledger.append("decision", {"packet_id": packet_id, "decision": decision})


# Segments 1 and 2 are real anomalies that were flagged, 6 is a real anomaly nobody flagged.
TRUTH = {"test:1": 1, "test:2": 1, "test:3": 0, "test:4": 0, "test:5": 0, "test:6": 1, "test:7": 0, "test:8": 0}


def test_counts_by_hand(tmp_path):
    write_run(tmp_path, {"p1": "confirmed", "p2": "dismissed", "p3": "dismissed", "p4": "dismissed",
                         "p5": "escalated"})
    row = score_run(tmp_path, TRUTH)["per_detector"]["Det"]
    assert (row["alarms_before"], row["false_alarms_before"]) == (5, 3)
    assert (row["dismissed"], row["confirmed"], row["escalated"]) == (3, 1, 1)
    assert row["false_alarms_removed"] == 2     # p3, p4
    assert row["real_anomalies_lost"] == 1      # p2 was a real anomaly
    assert row["alarms_after"] == 2
    assert row["before"]["precision"] == pytest.approx(2 / 5) and row["before"]["recall"] == pytest.approx(2 / 3)
    assert row["after"]["precision"] == pytest.approx(1 / 2) and row["after"]["recall"] == pytest.approx(1 / 3)


def test_an_alarm_without_decision_is_an_error(tmp_path):
    write_run(tmp_path, {"p1": "confirmed"})
    with pytest.raises(ValueError, match="4 alarms have no decision"):
        score_run(tmp_path, TRUTH)


def test_a_packet_decided_twice_is_an_error(tmp_path):
    write_run(tmp_path, {f"p{i}": "escalated" for i in range(1, 6)})
    Ledger(tmp_path / "ledger.jsonl").append("decision", {"packet_id": "p1", "decision": "dismissed"})
    with pytest.raises(ValueError, match="more than once"):
        score_run(tmp_path, TRUTH)


def test_whole_circuit_on_synthetic_alarms(tmp_path):
    alarms = alarm_set()
    folders = build_packets(alarms, pool(), tmp_path)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    reviewers = [RuleReviewer("fixed_rule_a", 2.0), RuleReviewer("fixed_rule_b", 3.0)]
    for packet_id, folder in folders.items():
        review_alarm(packet_id, folder, reviewers, ledger)
    # test:2 is the spiky one and the only real anomaly among the flagged.
    truth = {handle: int(handle == "test:2") for handle in alarms.universe}
    scored = score_run(tmp_path, truth)
    assert scored["packets"] == 3 and scored["ledger_records"] == 12
    a, b = scored["per_detector"]["DetA"], scored["per_detector"]["DetB"]
    assert (a["alarms_before"], a["dismissed"], a["confirmed"], a["real_anomalies_lost"]) == (2, 1, 1, 0)
    assert (b["alarms_before"], b["false_alarms_removed"], b["alarms_after"]) == (2, 1, 1)
    text = report(scored)
    assert "not a result" in text and "test double" in text
    assert str(SECRET_SEGMENT) not in (tmp_path / "ledger.jsonl").read_text()
