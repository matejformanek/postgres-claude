#!/usr/bin/env bash
# Workload 2: smallest representative regress slice.
# Runs select, expressions, boolean, numeric, int4 only.
#
# Assumes ASan cluster is running on port 5433.
# Output: writes ASan/UBSan logs to /tmp/asan-pg.* and /tmp/ubsan-pg.*.
#
# Run: workloads/regress-subset.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT/dev/build-asan"

# These are the smallest representative tests touching parser, executor,
# expression eval, and arithmetic. ~30s total runtime under ASan.
TESTS="select expressions boolean numeric int4"

echo "=== regress subset against ASan cluster :5433 ==="
# Use existing cluster (not initdb-and-go), via PG_REGRESS_PORT env.
# Falls back to the standard pg_regress driver.
PGPORT=5433 PGHOST=/tmp ../install-asan/bin/pg_regress \
  --bindir="$ROOT/dev/install-asan/bin" \
  --port=5433 \
  --host=/tmp \
  --use-existing \
  --dbname=regression \
  --inputdir="$ROOT/dev/src/test/regress" \
  --outputdir=/tmp/regress-subset-out \
  $TESTS 2>&1 | tail -50
