"""Ledger: append-only, chained, and loud when someone rewrites it."""
import json

import pytest

from review.ledger import Ledger, LedgerCorrupted, read


def test_append_and_read_back(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("packet", {"packet_id": "pkt-1"})
    ledger.append("decision", {"packet_id": "pkt-1", "decision": "escalated"})
    records = read(tmp_path / "ledger.jsonl")
    assert [(x["seq"], x["kind"]) for x in records] == [(1, "packet"), (2, "decision")]
    assert records[1]["previous"] == records[0]["hash"]
    assert ledger.verify() == 2


def test_reopening_appends_and_never_rewrites(tmp_path):
    path = tmp_path / "ledger.jsonl"
    Ledger(path).append("packet", {"packet_id": "pkt-1"})
    before = path.read_bytes()
    Ledger(path).append("packet", {"packet_id": "pkt-2"})
    after = path.read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == 2
    assert [x["seq"] for x in read(path)] == [1, 2]


def test_there_is_no_way_to_edit_or_delete():
    assert {name for name in dir(Ledger) if not name.startswith("_")} == {"append", "verify"}


def test_unknown_kind_is_refused(tmp_path):
    with pytest.raises(ValueError):
        Ledger(tmp_path / "ledger.jsonl").append("note", {})


def tamper(path, change):
    lines = path.read_text().splitlines()
    change(lines)
    path.write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("change", [
    lambda lines: lines.__setitem__(1, lines[1].replace("escalated", "dismissed")),   # edited
    lambda lines: lines.pop(0),                                                        # removed
    lambda lines: lines.reverse(),                                                     # reordered
    lambda lines: lines.__setitem__(2, "not json"),
])
def test_rewriting_is_detected(tmp_path, change):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    for decision in ("confirmed", "escalated", "dismissed"):
        ledger.append("decision", {"packet_id": "pkt", "decision": decision})
    tamper(path, change)
    with pytest.raises(LedgerCorrupted):
        read(path)
    with pytest.raises(LedgerCorrupted):
        Ledger(path)   # and it refuses to keep writing on top of a tampered file


def test_recomputing_one_hash_is_not_enough(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append("decision", {"packet_id": "pkt", "decision": "escalated"})
    ledger.append("decision", {"packet_id": "pkt2", "decision": "confirmed"})

    def forge(lines):
        from review.ledger import GENESIS, _digest
        record = json.loads(lines[0])
        record["data"]["decision"] = "dismissed"
        body = {key: record[key] for key in ("seq", "time", "kind", "data")}
        record["hash"] = _digest(GENESIS, body)
        lines[0] = json.dumps(record, sort_keys=True)

    tamper(path, forge)
    with pytest.raises(LedgerCorrupted, match="record 2"):
        read(path)
