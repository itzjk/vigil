"""Panel: the decision rule, independence of the two reviews, and what gets logged."""
import pytest

from review.ledger import Ledger, read
from review.packet import PACKET_FILES, build_packets
from review.panel import decide, review_alarm
from review.reviewer import Outcome, rejected
from review_fixtures import alarm_set, pool


def r(verdict, confidence=0.9):
    return {"verdict": verdict, "confidence": confidence, "reason": "x 1", "next_check": "y"}


@pytest.mark.parametrize("first, second, expected", [
    (r("nominal"), r("nominal"), "dismissed"),
    (r("nominal", 0.8), r("nominal", 0.8), "dismissed"),
    (r("nominal", 0.79), r("nominal", 0.99), "escalated"),   # one of them is not sure enough
    (r("anomaly"), r("anomaly", 0.3), "confirmed"),
    (r("anomaly"), r("nominal"), "escalated"),               # disagreement
    (r("nominal"), r("anomaly"), "escalated"),
    (r("unsure"), r("nominal"), "escalated"),
    (r("anomaly"), r("unsure"), "escalated"),
    (r("unsure"), r("unsure"), "escalated"),
])
def test_decision_rule(first, second, expected):
    assert decide(first, second) == expected


class Recorder:
    """Fake reviewer that notes what it was shown and leaves a note behind."""
    version, is_test_double = "t", True

    def __init__(self, name, verdict):
        self.name, self.verdict, self.seen_dir, self.seen_files = name, verdict, None, None

    def review(self, packet_dir):
        self.seen_dir = packet_dir
        self.seen_files = sorted(p.name for p in packet_dir.iterdir())
        (packet_dir / "note-for-the-other-reviewer.txt").write_text(self.verdict)
        return Outcome(r(self.verdict))


def one_packet(tmp_path):
    return next(iter(build_packets(alarm_set(), pool(), tmp_path).items()))


def test_second_reviewer_cannot_see_the_first(tmp_path):
    packet_id, folder = one_packet(tmp_path)
    first, second = Recorder("a", "nominal"), Recorder("b", "anomaly")
    decision = review_alarm(packet_id, folder, [first, second], Ledger(tmp_path / "ledger.jsonl"))
    assert decision == "escalated"
    assert first.seen_dir != second.seen_dir and folder not in (first.seen_dir, second.seen_dir)
    assert first.seen_files == second.seen_files == sorted(PACKET_FILES)
    assert sorted(p.name for p in folder.iterdir()) == sorted(PACKET_FILES)   # original untouched
    assert not first.seen_dir.exists() and not second.seen_dir.exists()       # copies are discarded


def test_everything_is_logged_with_reviewer_version(tmp_path):
    packet_id, folder = one_packet(tmp_path)
    review_alarm(packet_id, folder, [Recorder("a", "nominal"), Recorder("b", "nominal")],
                 Ledger(tmp_path / "ledger.jsonl"))
    records = read(tmp_path / "ledger.jsonl")
    assert [x["kind"] for x in records] == ["packet", "review", "review", "decision"]
    assert all(x["data"]["packet_id"] == packet_id for x in records)
    assert [(x["data"]["slot"], x["data"]["reviewer"], x["data"]["reviewer_version"])
            for x in records[1:3]] == [(1, "a", "t"), (2, "b", "t")]
    assert records[3]["data"]["decision"] == "dismissed"
    assert all(x["time"].endswith("+00:00") for x in records)


def test_rejected_review_escalates(tmp_path):
    class Broken(Recorder):
        def review(self, packet_dir):
            return rejected("the output is not a single JSON object")

    packet_id, folder = one_packet(tmp_path)
    ledger_path = tmp_path / "ledger.jsonl"
    assert review_alarm(packet_id, folder, [Recorder("a", "nominal"), Broken("b", "")],
                        Ledger(ledger_path)) == "escalated"
    assert read(ledger_path)[2]["data"]["rejection"] == "the output is not a single JSON object"


def test_panel_needs_two_reviewers(tmp_path):
    packet_id, folder = one_packet(tmp_path)
    with pytest.raises(ValueError):
        review_alarm(packet_id, folder, [Recorder("a", "nominal")], Ledger(tmp_path / "ledger.jsonl"))
