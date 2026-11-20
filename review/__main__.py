"""Run the review circuit end to end: packets -> two reviews -> decision -> ledger -> report.

    python -m review --examples              the 12 example segments with the fixed-rule test double
    python -m review --examples --external   the 12 example segments with the external reviewer
    python -m review --test --external    the test-split alarms with the external reviewer
    python -m review --test --packets-only   only build the packets, review nothing

The fixed-rule reviewer is refused on the test split: its numbers would look like a result.
"""
import argparse
import sys
from datetime import datetime, timezone

from opssat import ROOT
from review.ledger import Ledger
from review.packet import alarms_from_examples, alarms_on_test_split, build_packets
from review.panel import review_alarm
from review.reviewer import CommandReviewer, RuleReviewer
from review.score import report, score_run

REPORTS = {"examples": ROOT / "results" / "review_examples.md", "test": ROOT / "results" / "review.md"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--examples", action="store_true", help="review the 12 example segments")
    source.add_argument("--test", action="store_true", help="review the alarms raised on the test split")
    parser.add_argument("--external", action="store_true",
                        help="use the external reviewer program instead of the fixed-rule test double")
    parser.add_argument("--packets-only", action="store_true", help="build the packets and stop")
    options = parser.parse_args()
    if options.test and not (options.external or options.packets_only):
        sys.exit("The fixed-rule reviewer is a test double and is not run on the test split. "
                 "Use --external (or --packets-only).")

    if not options.packets_only:
        try:
            reviewers = ([CommandReviewer(1), CommandReviewer(2)] if options.external else
                         [RuleReviewer("fixed_rule_a", 2.0), RuleReviewer("fixed_rule_b", 3.0)])
        except RuntimeError as error:
            sys.exit(str(error))

    alarm_set, pool = alarms_from_examples() if options.examples else alarms_on_test_split()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "runs" / f"{alarm_set.source}_{stamp}"
    packets = build_packets(alarm_set, pool, run_dir)
    print(f"{len(packets)} packets in {run_dir.relative_to(ROOT)}/packets")
    if options.packets_only:
        return

    ledger = Ledger(run_dir / "ledger.jsonl")
    tally = {}
    for packet_id, folder in packets.items():
        decision = review_alarm(packet_id, folder, reviewers, ledger)
        tally[decision] = tally.get(decision, 0) + 1
    print("decisions: " + ", ".join(f"{count} {decision}" for decision, count in sorted(tally.items())))

    text = report(score_run(run_dir))
    REPORTS[alarm_set.source].write_text(text)
    print(f"ledger: {ledger.verify()} records, chain verified")
    print(f"report: {REPORTS[alarm_set.source].relative_to(ROOT)}\n")
    print(text)


if __name__ == "__main__":
    main()
