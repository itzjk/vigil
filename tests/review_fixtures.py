"""Synthetic alarms and reference pool, so the review tests need no dataset."""
import numpy as np

from review.packet import Alarm, AlarmSet, ReferencePool

CHANNEL = "CADC0872"
# A dataset segment number that cannot collide with any other number in a packet.
SECRET_SEGMENT = 987654


def arc(samples=60, spike=0.0):
    seconds = np.arange(samples, dtype=float)
    values = np.sin(np.linspace(0, np.pi, samples)) * 3e-5 + 1e-6
    values[samples // 2] += spike
    return seconds, values


def pool():
    return ReferencePool({CHANNEL: [(*arc(40 + 5 * i), 1) for i in range(8)]})


def alarm_set():
    """Three alarmed segments: a clean arc, a spiky one and the one with the secret number."""
    alarms = {
        "test:1": Alarm("test:1", CHANNEL, 1, *arc()),
        "test:2": Alarm("test:2", CHANNEL, 1, *arc(spike=9e-5)),
        f"test:{SECRET_SEGMENT}": Alarm(f"test:{SECRET_SEGMENT}", CHANNEL, 1, *arc(80)),
    }
    flagged = {"DetA": ["test:1", "test:2"], "DetB": ["test:2", f"test:{SECRET_SEGMENT}"]}
    universe = [*alarms, "test:4", "test:5"]
    return AlarmSet("test", alarms, flagged, universe)
