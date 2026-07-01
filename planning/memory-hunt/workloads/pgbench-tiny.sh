#!/usr/bin/env bash
# Workload 3: pgbench at scale=1 for ~60s.
# Lighter than upstream's default because ASan multiplies wall-time ~2x.
#
# Run: workloads/pgbench-tiny.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export PATH="$ROOT/dev/install-asan/bin:$PATH"

PSQL="psql -h /tmp -p 5433 -d postgres"
PGB="pgbench -h /tmp -p 5433"

echo "=== pgbench init scale=1 ==="
$PSQL -c "DROP DATABASE IF EXISTS pgbench_tiny;"
$PSQL -c "CREATE DATABASE pgbench_tiny;"
$PGB -i -s 1 pgbench_tiny 2>&1 | tail -10

echo "=== pgbench run: 4 clients, 60s ==="
$PGB -c 4 -T 60 -P 10 pgbench_tiny 2>&1 | tail -20

echo "=== pgbench cleanup ==="
$PSQL -c "DROP DATABASE pgbench_tiny;"
