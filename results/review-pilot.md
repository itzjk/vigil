# Review layer report: practice set

> **Dry run with a test double.** The reviews below come from a fixed rule that exists only to
> exercise the circuit end to end. These numbers are **not a result** and say nothing about how
> a real review layer performs.

Evaluated on 12 segments, 6 of them anomalous. 12 distinct alarmed segments were reviewed twice each.

| Detector | Alarms before | False alarms before | Dismissed | False alarms removed | Real anomalies lost | Confirmed | Escalated to a person | Alarms after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all-flagged | 12 | 6 | 8 | 6 | 2 | 2 | 2 | 4 |

| Detector | Precision / recall / F1 before | Precision / recall / F1 after |
|---|---|---|
| all-flagged | 0.500 / 1.000 / 0.667 | 1.000 / 0.667 / 0.800 |

Decision rule: an alarm is **dismissed** only when both reviews say nominal with confidence of at least 0.8; it is **confirmed** when both say anomaly; anything else (disagreement, any "unsure", a rejected review) is **escalated** to a person. "After" keeps every alarm that was not dismissed.

Reviewers: `fixed-rule-a` version 1 (test double); `fixed-rule-b` version 1 (test double). Reviews rejected as malformed: 0. Ledger records: 48, hash chain verified.
