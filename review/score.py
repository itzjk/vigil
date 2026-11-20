"""Score a review run. This is the only module where the true labels enter.

From the ledger (decisions per packet), the private key (packet -> segment) and the labels, it
reports per detector: alarms before and after review, false alarms removed, real anomalies lost
by a wrong dismissal, how many alarms were escalated to a person, and precision / recall / F1
before and after, computed with the project's single scorer (measure.py).

"After" counts every alarm that was not dismissed, so confirmed and escalated alarms both stay.
"""
import json

from measure import measure
from opssat import ROOT, load_table
from review import ledger as ledger_module
from review.panel import DECISIONS, DISMISS_CONFIDENCE

TEST_DOUBLE_BANNER = (
    "> **Dry run with a test double.** The reviews below come from a fixed rule that exists only to\n"
    "> exercise the circuit end to end. These numbers are **not a result** and say nothing about how\n"
    "> a real review layer performs.\n")


def load_truth(source, universe):
    """True label (1 = anomaly) of every handle in the universe."""
    if source == "test":
        anomaly = load_table().anomaly
        return {handle: int(anomaly[int(handle.split(":")[1])]) for handle in universe}
    if source == "practice":
        answers = json.loads((ROOT / "practice" / "answers.json").read_text())["answers"]
        labels = {f"practice:{answer['case']}": int(answer["label"] == "anomaly") for answer in answers}
        return {handle: labels[handle] for handle in universe}
    raise ValueError(f"unknown source: {source}")


def decisions_from(records):
    """packet_id -> decision; every packet must be decided exactly once."""
    decisions = {}
    for record in records:
        if record["kind"] == "decision":
            packet_id = record["data"]["packet_id"]
            if packet_id in decisions:
                raise ValueError(f"{packet_id} was decided more than once")
            decisions[packet_id] = record["data"]["decision"]
    return decisions


def score_detector(raised, universe, truth, decision_of):
    """Before/after figures for one detector. `raised` and `universe` are handles."""
    undecided = [handle for handle in raised if handle not in decision_of]
    if undecided:
        raise ValueError(f"{len(undecided)} alarms have no decision in the ledger")
    counts = {decision: sum(decision_of[h] == decision for h in raised) for decision in DECISIONS}
    dismissed = {h for h in raised if decision_of[h] == "dismissed"}
    labels = [truth[h] for h in universe]
    before = measure(labels, [int(h in raised) for h in universe])
    after = measure(labels, [int(h in raised and h not in dismissed) for h in universe])
    return {
        "alarms_before": len(raised),
        "false_alarms_before": before["fp"],
        **counts,
        "false_alarms_removed": sum(truth[h] == 0 for h in dismissed),
        "real_anomalies_lost": sum(truth[h] == 1 for h in dismissed),
        "alarms_after": len(raised) - len(dismissed),
        "before": before,
        "after": after,
    }


def score_run(run_dir, truth=None):
    """Score a whole run folder; returns {"per_detector": ..., "reviewers": ..., ...}."""
    records = ledger_module.read(run_dir / "ledger.jsonl")   # also verifies the hash chain
    key = json.loads((run_dir / "private" / "key.json").read_text())
    truth = load_truth(key["source"], key["universe"]) if truth is None else truth
    decisions = decisions_from(records)
    decision_of = {key["packets"][packet_id]: decision for packet_id, decision in decisions.items()}
    reviews = [record["data"] for record in records if record["kind"] == "review"]
    return {
        "source": key["source"],
        "ledger_records": len(records),
        "packets": len(key["packets"]),
        "reviewers": sorted({(r["reviewer"], r["reviewer_version"], r["test_double"]) for r in reviews}),
        "rejected_reviews": sum(r["rejection"] is not None for r in reviews),
        "per_detector": {
            detector: score_detector({key["packets"][p] for p in packet_ids}, key["universe"], truth, decision_of)
            for detector, packet_ids in key["alarms"].items()},
    }


def report(scored):
    def prf(metrics):
        return f"{metrics['precision']:.3f} / {metrics['recall']:.3f} / {metrics['f1']:.3f}"

    universe = next(iter(scored["per_detector"].values()))["before"]
    lines = [f"# Review layer report: {scored['source']} set", ""]
    if any(is_double for _, _, is_double in scored["reviewers"]):
        lines += [TEST_DOUBLE_BANNER]
    lines += [
        f"Evaluated on {universe['n']} segments, {universe['tp'] + universe['fn']} of them anomalous. "
        f"{scored['packets']} distinct alarmed segments were reviewed twice each.",
        "",
        "| Detector | Alarms before | False alarms before | Dismissed | False alarms removed "
        "| Real anomalies lost | Confirmed | Escalated to a person | Alarms after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for detector, row in scored["per_detector"].items():
        lines.append(f"| {detector} | {row['alarms_before']} | {row['false_alarms_before']} | {row['dismissed']} "
                     f"| {row['false_alarms_removed']} | {row['real_anomalies_lost']} | {row['confirmed']} "
                     f"| {row['escalated']} | {row['alarms_after']} |")
    lines += ["", "| Detector | Precision / recall / F1 before | Precision / recall / F1 after |", "|---|---|---|"]
    for detector, row in scored["per_detector"].items():
        lines.append(f"| {detector} | {prf(row['before'])} | {prf(row['after'])} |")
    lines += [
        "",
        f"Decision rule: an alarm is **dismissed** only when both reviews say nominal with confidence of at "
        f"least {DISMISS_CONFIDENCE}; it is **confirmed** when both say anomaly; anything else (disagreement, "
        f"any \"unsure\", a rejected review) is **escalated** to a person. \"After\" keeps every alarm that "
        f"was not dismissed.",
        "",
        "Reviewers: " + "; ".join(f"`{name}` version {version}" + (" (test double)" if is_double else "")
                                  for name, version, is_double in scored["reviewers"])
        + f". Reviews rejected as malformed: {scored['rejected_reviews']}. "
        f"Ledger records: {scored['ledger_records']}, hash chain verified.",
    ]
    return "\n".join(lines) + "\n"
