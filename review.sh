#!/bin/sh
# Runs the review circuit. `./review.sh --pilot` is the end-to-end dry run on the practice cases.
# Needs the environment, data and baseline that ./run.sh produces.
set -eu
cd "$(dirname "$0")"
[ -x .venv/bin/python ] && [ -f data/opssat-ad/segments.csv ] && [ -f results/predictions/IForest.csv ] || {
    echo "Run ./run.sh first: the review circuit needs the environment, the data and the baseline." >&2
    exit 1
}
exec .venv/bin/python -m review "$@"
