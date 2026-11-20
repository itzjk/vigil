#!/bin/sh
# Runs everything from scratch: environment, data, tests, baseline, examples and a check of the review circuit.
set -eu
cd "$(dirname "$0")"

# The versions pinned in requirements.txt (the dataset's own) need Python 3.9 to 3.12.
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; sys.exit(not (3, 9) <= sys.version_info[:2] <= (3, 12))' || {
    echo "Python 3.9 to 3.12 is required; set it with PYTHON=/path/to/python ./run.sh" >&2
    exit 1
}

if [ ! -x .venv/bin/python ]; then
    "$PYTHON" -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
fi
.venv/bin/pip install --quiet -r requirements.txt

echo "== 1. Data =="
.venv/bin/python download.py
echo "== 2. Tests =="
.venv/bin/python -m pytest -q tests
echo "== 3. Baseline =="
.venv/bin/python baseline.py
echo "== 4. Examples =="
.venv/bin/python build_examples.py
echo "== 5. Review circuit on the examples (fixed-rule test double, not a result) =="
.venv/bin/python -m review --examples
