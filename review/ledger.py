"""Append-only JSONL ledger of every packet, review and decision.

Each record carries a sequence number, a UTC timestamp, its kind, its data and a hash chained
to the previous record, so a rewritten, removed or reordered line is detected by `verify()`.
The class offers no way to edit or delete: the file is only ever opened for appending.

The ledger identifies packets by their random id, never by the dataset's segment number, so it
can be read without unblinding anything.
"""
import hashlib
import json
from datetime import datetime, timezone

KINDS = ("packet", "review", "decision")
GENESIS = "0" * 64


class LedgerCorrupted(Exception):
    """The ledger file no longer matches its own hash chain."""


def _digest(previous, body):
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((previous + canonical).encode()).hexdigest()


def read(path):
    """Return every record, after checking the whole chain."""
    records, previous = [], GENESIS
    if not path.exists():
        return records
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        try:
            record = json.loads(line)
            body = {key: record[key] for key in ("seq", "time", "kind", "data")}
            intact = (record["seq"] == number and record["previous"] == previous
                      and record["hash"] == _digest(previous, body))
        except (json.JSONDecodeError, KeyError, TypeError):
            intact = False
        if not intact:
            raise LedgerCorrupted(f"{path.name}: record {number} breaks the chain")
        records.append(record)
        previous = record["hash"]
    return records


class Ledger:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = read(path)   # refuses to continue a ledger that has been tampered with
        self._seq = len(existing)
        self._previous = existing[-1]["hash"] if existing else GENESIS

    def append(self, kind, data):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {list(KINDS)}")
        body = {"seq": self._seq + 1, "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "kind": kind, "data": data}
        record = {**body, "previous": self._previous, "hash": _digest(self._previous, body)}
        with open(self.path, "a") as file:
            file.write(json.dumps(record, sort_keys=True) + "\n")
        self._seq, self._previous = record["seq"], record["hash"]
        return record

    def verify(self):
        return len(read(self.path))
