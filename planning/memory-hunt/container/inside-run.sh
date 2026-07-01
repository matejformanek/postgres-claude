#!/usr/bin/env bash
# Runs inside the pg-memhunt container AFTER inside-build.sh.
# Starts PG under Valgrind, runs workloads, captures evidence.
set -euo pipefail

INSTALL=/home/pg/install
DATA=/home/pg/data
SUP=/pg-source/src/tools/valgrind.supp
EVIDIR=/evidence

# Initdb if not already there
if [[ ! -f "$DATA/PG_VERSION" ]]; then
  echo "=== initdb ==="
  "$INSTALL/bin/initdb" -D "$DATA" --locale=C --encoding=UTF8 2>&1 | tail -5
fi

PORT=5433
PIDFILE="$DATA/postmaster.pid"
LOG="$DATA/server.log"
VLOG="$EVIDIR/valgrind.log"

# Stop any running postmaster
if [[ -f "$PIDFILE" ]]; then
  "$INSTALL/bin/pg_ctl" -D "$DATA" stop -m immediate 2>&1 | tail -2 || true
  sleep 1
fi

echo "=== start postgres under Valgrind ==="
echo "  Valgrind log -> $VLOG"
# Run postgres in background under valgrind. Use --trace-children so forked
# backends are also instrumented. Use --child-silent-after-fork=no so backend
# leaks fire too. Use the upstream suppressions file.
nohup valgrind \
    --tool=memcheck \
    --leak-check=full \
    --show-leak-kinds=definite,indirect,possible \
    --track-origins=yes \
    --trace-children=yes \
    --child-silent-after-fork=no \
    --num-callers=40 \
    --error-limit=no \
    --suppressions="$SUP" \
    --log-file="$VLOG-%p" \
    "$INSTALL/bin/postgres" \
        -D "$DATA" -p "$PORT" -k /tmp \
        > "$LOG" 2>&1 &
PMPID=$!
echo "valgrind postmaster pid=$PMPID"

# Wait for cluster to accept connections (valgrind makes init slow)
for i in $(seq 1 120); do
  if "$INSTALL/bin/psql" -h /tmp -p "$PORT" -d postgres -tAc 'select 1' >/dev/null 2>&1; then
    echo "cluster ready after ${i}s"
    break
  fi
  sleep 1
done

PSQL="$INSTALL/bin/psql -h /tmp -p $PORT -d postgres"

# --- Workload 1: normal-select (light) ---
echo "=== WL1: normal-select ==="
$PSQL -X -q -f /workloads/normal-select.sql > "$EVIDIR/wl1-stdout.txt" 2> "$EVIDIR/wl1-stderr.txt" || true

# --- Workload 4: diverse-subsystems ---
echo "=== WL4: diverse-subsystems ==="
# Rewrite the pg_backend_memory_contexts COPY paths so they land in /evidence
sed -e "s|planning/memory-hunt/evidence|$EVIDIR|g" /workloads/diverse-subsystems.sql > /tmp/wl4.sql
$PSQL -X -q -f /tmp/wl4.sql > "$EVIDIR/wl4-stdout.txt" 2> "$EVIDIR/wl4-stderr.txt" || true

# --- Workload 3: pgbench-tiny ---
echo "=== WL3: pgbench-tiny ==="
$PSQL -c "DROP DATABASE IF EXISTS pgbench_tiny;"
$PSQL -c "CREATE DATABASE pgbench_tiny;"
"$INSTALL/bin/pgbench" -h /tmp -p "$PORT" -i -s 1 pgbench_tiny 2>&1 | tail -5
"$INSTALL/bin/pgbench" -h /tmp -p "$PORT" -c 2 -T 10 pgbench_tiny > "$EVIDIR/wl3-pgbench.txt" 2>&1 || true
$PSQL -c "DROP DATABASE pgbench_tiny;"

echo "=== stop postgres (clean shutdown so Valgrind can finalize leaks) ==="
"$INSTALL/bin/pg_ctl" -D "$DATA" stop -m fast 2>&1 | tail -3 || true

# Give valgrind a moment to flush
sleep 3

echo "=== summarize valgrind logs ==="
ls -la "$EVIDIR/"valgrind.log-* 2>/dev/null | head -10
for f in "$EVIDIR/"valgrind.log-*; do
  [[ -f "$f" ]] || continue
  PID=${f##*-}
  # Extract per-process Valgrind error summary
  TAIL=$(grep -E 'ERROR SUMMARY|definitely lost:|indirectly lost:|possibly lost:|still reachable:|suppressed:' "$f" | tail -10)
  if [[ -n "$TAIL" ]]; then
    echo "--- pid $PID ---"
    echo "$TAIL"
  fi
done | tee "$EVIDIR/valgrind-summary.txt"
