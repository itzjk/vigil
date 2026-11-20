"""Reviewers: the schema, the fixed-rule test double and the external-command socket."""
import json
import sys

import pytest

from review.packet import build_packets
from review.reviewer import COMMAND_VARIABLE, CommandReviewer, InvalidReview, RuleReviewer, validate
from review_fixtures import alarm_set, pool

GOOD = {"verdict": "anomaly", "confidence": 0.9,
        "reason": "Single-sample spike to 6.3e-5 at t=143 s.", "next_check": "Look at the neighbours."}


def test_valid_review_passes_unchanged():
    assert validate(dict(GOOD)) == GOOD


@pytest.mark.parametrize("broken", [
    "anomaly",                                           # not an object
    {k: v for k, v in GOOD.items() if k != "next_check"},  # missing field
    {**GOOD, "label": 1},                                # extra field
    {**GOOD, "verdict": "maybe"},
    {**GOOD, "confidence": 1.2},
    {**GOOD, "confidence": "high"},
    {**GOOD, "confidence": True},
    {**GOOD, "reason": ""},
    {**GOOD, "reason": "It looks odd."},                 # cites nothing measurable
    {**GOOD, "next_check": None},
])
def test_malformed_review_is_rejected(broken):
    with pytest.raises(InvalidReview):
        validate(broken)


def test_unsure_may_have_no_numbers():
    assert validate({**GOOD, "verdict": "unsure", "confidence": 0.2, "reason": "Cannot tell."})


def packets(tmp_path):
    return build_packets(alarm_set(), pool(), tmp_path)


def by_jump(folders):
    return sorted(folders.values(),
                  key=lambda f: json.loads((f / "summary.json").read_text())["largest_jump"]["size"])


def test_rule_reviewer_is_deterministic_and_cites_the_packet(tmp_path):
    calm, _, spiky = by_jump(packets(tmp_path))
    reviewer = RuleReviewer()
    assert reviewer.is_test_double
    assert reviewer.review(calm).review["verdict"] == "nominal"
    spiky_review = reviewer.review(spiky).review
    assert spiky_review["verdict"] == "anomaly" and "t=31 s" in spiky_review["reason"]
    assert reviewer.review(spiky) == reviewer.review(spiky)


def command_reviewer(tmp_path, body, slot=1, **extra):
    script = tmp_path / "reviewer.py"
    script.write_text(body)
    return CommandReviewer(slot, {COMMAND_VARIABLE: f"{sys.executable} {script}", **extra})


def test_command_reviewer_happy_path(tmp_path):
    folder = by_jump(packets(tmp_path))[0]
    reviewer = command_reviewer(tmp_path, f"""
import json, os, sys
summary = json.load(open(os.path.join(sys.argv[-1], "summary.json")))
print(json.dumps({{"verdict": "nominal", "confidence": 0.9,
                  "reason": "Slot " + os.environ["ALARM_GUARD_REVIEW_SLOT"] + ": max " + str(summary["max"]),
                  "next_check": "none"}}))
""", slot=2, ALARM_GUARD_REVIEWER_VERSION="v7")
    outcome = reviewer.review(folder)
    assert outcome.rejection is None
    assert outcome.review["verdict"] == "nominal" and outcome.review["reason"].startswith("Slot 2: max ")
    assert (reviewer.name, reviewer.version, reviewer.is_test_double) == ("command-2", "v7", False)


@pytest.mark.parametrize("body, why", [
    ("print('the segment looks anomalous to me')", "not a single JSON object"),
    ("print('{\"verdict\": \"anomaly\"}')", "exactly the fields"),
    ("print('{\"verdict\": \"anomaly\", \"confidence\": 7, \"reason\": \"x 1\", \"next_check\": \"y\"}')",
     "confidence"),
    ("print('{}'); print('{}')", "not a single JSON object"),
    ("", "not a single JSON object"),
    ("import sys; sys.exit(3)", "status 3"),
    ("import time; time.sleep(5)", "no answer within"),
])
def test_command_reviewer_rejects_malformed_output_as_unsure(tmp_path, body, why):
    folder = by_jump(packets(tmp_path))[0]
    outcome = command_reviewer(tmp_path, body, ALARM_GUARD_REVIEWER_TIMEOUT="1").review(folder)
    assert why in outcome.rejection
    assert outcome.review["verdict"] == "unsure" and outcome.review["confidence"] == 0.0


def test_command_reviewer_needs_its_variable_and_survives_a_missing_program(tmp_path):
    with pytest.raises(RuntimeError, match=COMMAND_VARIABLE):
        CommandReviewer(1, {})
    outcome = CommandReviewer(1, {COMMAND_VARIABLE: str(tmp_path / "does-not-exist")}).review(tmp_path)
    assert "could not be run" in outcome.rejection and outcome.review["verdict"] == "unsure"
