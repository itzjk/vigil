#!/bin/sh
# Runs the review circuit. `./review.sh --examples` runs it end to end on the twelve example segments.
# Needs the environment, data and baseline that ./run.sh produces.
set -eu
cd "$(dirname "$0")"
[ -x .venv/bin/python ] && [ -f data/opssat_ad/segments.csv ] && [ -f results/predictions/IForest.csv ] || {
    echo "Run ./run.sh first: the review circuit needs the environment, the data and the baseline." >&2
    exit 1
}
exec .venv/bin/python -m review "$@"
