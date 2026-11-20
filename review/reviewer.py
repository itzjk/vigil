"""Pluggable reviewers: each takes a packet folder and returns one validated review.

A review is a JSON object with exactly four fields:

    verdict     "anomaly" | "nominal" | "unsure"
    confidence  number between 0 and 1
    reason      one sentence citing something visible in the packet (where, how much)
    next_check  what to look at next to confirm

Two reviewers are implemented. `RuleReviewer` is a deterministic fixed rule: a TEST DOUBLE for
checking the circuit, not a reviewer anyone should trust. `CommandReviewer` hands the packet
to an external program chosen through environment variables and reads the review from its
standard output; that is the socket our own agent system plugs into.

Malformed output from an external reviewer is never repaired or guessed: it is rejected and
recorded as "unsure".
"""
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

VERDICTS = ("anomaly", "nominal", "unsure")
FIELDS = ("verdict", "confidence", "reason", "next_check")
MAX_TEXT = 600
COMMAND_VARIABLE = "VIGIL_REVIEWER_CMD"
VERSION_VARIABLE = "VIGIL_REVIEWER_VERSION"
TIMEOUT_VARIABLE = "VIGIL_REVIEWER_TIMEOUT"
SLOT_VARIABLE = "VIGIL_REVIEW_SLOT"
DEFAULT_TIMEOUT_S = 600


class InvalidReview(ValueError):
    """The reviewer's output does not follow the review schema."""


@dataclass(frozen=True)
class Outcome:
    """A validated review, or the "unsure" that stands in for a rejected one."""
    review: dict
    rejection: Optional[str] = None   # why the reviewer's own output was rejected, if it was


def validate(candidate):
    """Return the review if it follows the schema exactly; raise InvalidReview otherwise."""
    if not isinstance(candidate, dict):
        raise InvalidReview("a review must be a JSON object")
    if set(candidate) != set(FIELDS):
        raise InvalidReview(f"a review must have exactly the fields {list(FIELDS)}, got {sorted(candidate)}")
    if candidate["verdict"] not in VERDICTS:
        raise InvalidReview(f"verdict must be one of {list(VERDICTS)}")
    confidence = candidate["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise InvalidReview("confidence must be a number between 0 and 1")
    for field in ("reason", "next_check"):
        text = candidate[field]
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise InvalidReview(f"{field} must be a non-empty string of at most {MAX_TEXT} characters")
    if candidate["verdict"] != "unsure" and not any(character.isdigit() for character in candidate["reason"]):
        raise InvalidReview("reason must cite something measurable (where, how much)")
    return {field: candidate[field] for field in FIELDS}


def rejected(why):
    """The outcome recorded when a reviewer's output cannot be accepted."""
    return Outcome({"verdict": "unsure", "confidence": 0.0,
                    "reason": "The reviewer's output was rejected and not interpreted.",
                    "next_check": "Send this alarm to a person."}, rejection=why)


class RuleReviewer:
    """TEST DOUBLE. A fixed rule on the packet summary; deterministic, for tests and end-to-end checks."""

    version = "1"
    is_test_double = True

    def __init__(self, name="fixed_rule", anomaly_factor=2.0):
        self.name = name
        self.anomaly_factor = anomaly_factor

    def review(self, packet_dir):
        summary = json.loads((Path(packet_dir) / "summary.json").read_text())
        reference, jump = summary["channel_reference"], summary["largest_jump"]
        typical = reference["largest_jump_p95"]
        if typical <= 0:
            return Outcome(validate({
                "verdict": "unsure", "confidence": 0.0,
                "reason": "The channel's nominal examples have no jumps to compare against.",
                "next_check": "Compare the plot with the reference sheet by eye."}))
        ratio = jump["size"] / typical
        cited = (f"Largest jump {jump['size']:.3g} at t={jump['at_s']:.0f} s is {ratio:.1f}x the "
                 f"channel's nominal 95th percentile ({typical:.3g})")
        if summary["max"] > reference["max_highest"] or summary["min"] < reference["min_lowest"]:
            verdict, confidence = "anomaly", 0.9
            cited = (f"Range {summary['min']:.3g} to {summary['max']:.3g} leaves the nominal range "
                     f"{reference['min_lowest']:.3g} to {reference['max_highest']:.3g}; {cited[0].lower()}{cited[1:]}")
        elif ratio >= self.anomaly_factor:
            verdict, confidence = "anomaly", 0.9
        elif ratio <= 1:
            verdict, confidence = "nominal", 0.85
        else:
            verdict, confidence = "unsure", 0.5
        return Outcome(validate({
            "verdict": verdict, "confidence": confidence, "reason": cited + ".",
            "next_check": f"Inspect the samples around t={jump['at_s']:.0f} s against the reference sheet."}))


class CommandReviewer:
    """Runs an external program on the packet folder and reads one review from its stdout.

    The program is taken from VIGIL_REVIEWER_CMD (split like a shell command line) and is
    called with the packet folder as its last argument and VIGIL_REVIEW_SLOT set to the
    review slot (1 or 2). It must print a single JSON object following the review schema.
    """

    is_test_double = False

    def __init__(self, slot, environment=None):
        environment = os.environ if environment is None else environment
        if not environment.get(COMMAND_VARIABLE, "").strip():
            raise RuntimeError(f"set {COMMAND_VARIABLE} to the reviewer program before using the command reviewer")
        self._command = shlex.split(environment[COMMAND_VARIABLE])
        self._timeout = float(environment.get(TIMEOUT_VARIABLE, DEFAULT_TIMEOUT_S))
        self._environment = {**environment, SLOT_VARIABLE: str(slot)}
        self.name = f"command_{slot}"
        self.version = environment.get(VERSION_VARIABLE, "unversioned")

    def review(self, packet_dir):
        try:
            finished = subprocess.run([*self._command, str(packet_dir)], capture_output=True, text=True,
                                      timeout=self._timeout, env=self._environment)
        except subprocess.TimeoutExpired:
            return rejected(f"no answer within {self._timeout:g} s")
        except OSError as error:
            return rejected(f"the reviewer program could not be run: {error.strerror}")
        if finished.returncode != 0:
            return rejected(f"the reviewer program exited with status {finished.returncode}")
        try:
            return Outcome(validate(json.loads(finished.stdout)))
        except json.JSONDecodeError:
            return rejected("the output is not a single JSON object")
        except InvalidReview as error:
            return rejected(str(error))
