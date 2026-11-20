"""Two independent reviews per alarm and one written decision rule.

Independence: each reviewer gets its own fresh copy of the packet in a separate temporary
folder and never sees the other's answer (nor a place where the other could have left one).

Decision rule:

    dismissed   both reviews say "nominal", each with confidence >= DISMISS_CONFIDENCE
    confirmed   both reviews say "anomaly"
    escalated   anything else: disagreement, any "unsure", a nominal verdict below the bar,
                or a rejected review. Escalated alarms go to a person.

Only a dismissal removes an alarm. Confirmed and escalated alarms both still reach a person;
the difference is what the person is told.
"""
import hashlib
import shutil
import tempfile
from pathlib import Path

DISMISS_CONFIDENCE = 0.8
DECISIONS = ("dismissed", "confirmed", "escalated")


def decide(first, second, dismiss_confidence=DISMISS_CONFIDENCE):
    """Apply the decision rule to two reviews."""
    verdicts = {first["verdict"], second["verdict"]}
    if verdicts == {"nominal"} and min(first["confidence"], second["confidence"]) >= dismiss_confidence:
        return "dismissed"
    if verdicts == {"anomaly"}:
        return "confirmed"
    return "escalated"


def _fingerprint(packet_dir):
    digest = hashlib.sha256()
    for file in sorted(Path(packet_dir).iterdir()):
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def review_alarm(packet_id, packet_dir, reviewers, ledger):
    """Log the packet, collect two independent reviews, decide, and log everything."""
    if len(reviewers) != 2:
        raise ValueError("the panel needs exactly two reviewers")
    ledger.append("packet", {"packet_id": packet_id, "sha256": _fingerprint(packet_dir)})
    reviews = []
    for slot, reviewer in enumerate(reviewers, start=1):
        with tempfile.TemporaryDirectory(prefix="alarm-guard-review-") as scratch:
            private_copy = Path(scratch) / packet_id
            shutil.copytree(packet_dir, private_copy)
            outcome = reviewer.review(private_copy)
        ledger.append("review", {
            "packet_id": packet_id, "slot": slot, "reviewer": reviewer.name,
            "reviewer_version": reviewer.version, "test_double": reviewer.is_test_double,
            "review": outcome.review, "rejection": outcome.rejection})
        reviews.append(outcome.review)
    decision = decide(*reviews)
    ledger.append("decision", {"packet_id": packet_id, "decision": decision,
                               "rule": f"two-reviews/dismiss-at-{DISMISS_CONFIDENCE}"})
    return decision
