#!/usr/bin/env bash
# Inside-container: build PG, initdb, run parallel-VACUUM reproducer for
# b20c952ce70 (pgstat_progress_parallel_incr_param leak), sample worker RSS.
set -euo pipefail

BUILD=/home/pg/build
INSTALL=/home/pg/install
DATA=/home/pg/data
EVIDIR=/evidence

rm -rf "$BUILD" "$INSTALL" "$DATA"
mkdir -p "$BUILD" "$INSTALL"

echo "=== meson setup + build ==="
cd /
meson setup "$BUILD" /pg-source \
  --buildtype=debug \
  -Dcassert=true \
  -Ddebug=true \
  -Doptimization=0 \
  -Dprefix="$INSTALL" >/tmp/setup.log 2>&1 || { tail -30 /tmp/setup.log; exit 1; }
cd "$BUILD"
ninja -j "$(nproc)" install >/tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }

{
  echo "Commit: $(cd /pg-source && git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "Date:   $(date -u +%FT%TZ)"
} | tee "$EVIDIR/build-info.txt"

"$INSTALL/bin/initdb" -D "$DATA" --locale=C --encoding=UTF8 >/tmp/initdb.log 2>&1 || { tail -20 /tmp/initdb.log; exit 1; }

# Configure for parallel VACUUM with cost-delay timing reporting (the hot path
# that exercises pgstat_progress_parallel_incr_param thousands of times per
# worker lifetime).
cat >> "$DATA/postgresql.conf" <<'CONF'
shared_buffers = '256MB'
max_parallel_maintenance_workers = 4
max_parallel_workers = 8
max_parallel_workers_per_gather = 0
maintenance_work_mem = '256MB'
track_cost_delay_timing = on
vacuum_cost_delay = 1ms
vacuum_cost_limit = 1000
CONF

"$INSTALL/bin/pg_ctl" -D "$DATA" -l "$DATA/server.log" -o "-k /tmp" start
sleep 1

PSQL="$INSTALL/bin/psql -h /tmp -d postgres"

echo "=== prepare big table with many indexes ==="
$PSQL <<'SQL' 2>&1 | tail -5
DROP TABLE IF EXISTS big;
CREATE TABLE big (
  id int,
  c1 int, c2 int, c3 int, c4 int,
  c5 int, c6 int, c7 int, c8 int,
  c9 int, c10 int, c11 int, c12 int,
  c13 int, c14 int, c15 int, c16 int
);
INSERT INTO big
  SELECT g, g, g*2, g*3, g*5, g*7, g*11, g*13, g*17, g*19, g*23, g*29, g*31,
         g*37, g*41, g*43, g*47
  FROM generate_series(1, 10000000) g;
CREATE INDEX big_c1  ON big(c1);
CREATE INDEX big_c2  ON big(c2);
CREATE INDEX big_c3  ON big(c3);
CREATE INDEX big_c4  ON big(c4);
CREATE INDEX big_c5  ON big(c5);
CREATE INDEX big_c6  ON big(c6);
CREATE INDEX big_c7  ON big(c7);
CREATE INDEX big_c8  ON big(c8);
CREATE INDEX big_c9  ON big(c9);
CREATE INDEX big_c10 ON big(c10);
CREATE INDEX big_c11 ON big(c11);
CREATE INDEX big_c12 ON big(c12);
CREATE INDEX big_c13 ON big(c13);
CREATE INDEX big_c14 ON big(c14);
CREATE INDEX big_c15 ON big(c15);
CREATE INDEX big_c16 ON big(c16);
SELECT pg_size_pretty(pg_total_relation_size('big')) AS total_size;
SQL

echo "=== generate dead rows ==="
$PSQL -c "UPDATE big SET c1 = c1 + 1 WHERE id % 2 = 0;" 2>&1 | tail -3
$PSQL -c "DELETE FROM big WHERE id % 7 = 0;" 2>&1 | tail -3

echo "=== launching parallel VACUUM (background) ==="
$PSQL -c "VACUUM (PARALLEL 4, VERBOSE) big;" > "$EVIDIR/vacuum.log" 2>&1 &
VAC_PID=$!
echo "psql pid: $VAC_PID"

# Sample RSS of the parallel WORKERS (not postmaster, not the driver).
# Worker processes have cmdline starting "postgres: parallel worker".
{
  echo -e "t\tworker_pid\trss_kb"
} > "$EVIDIR/rss-timeseries.tsv"

T=0
while kill -0 "$VAC_PID" 2>/dev/null; do
  # Sample any parallel worker
  ps -e -o pid=,rss=,args= 2>/dev/null \
    | awk '/postgres: parallel worker/' \
    | while read -r pid rss rest; do
        echo -e "${T}\t${pid}\t${rss}" >> "$EVIDIR/rss-timeseries.tsv"
      done || true
  T=$((T+1))
  if [[ $T -gt 600 ]]; then
    echo "timeout at ${T}s — killing VACUUM"
    kill "$VAC_PID" 2>/dev/null || true
    break
  fi
  sleep 0.5
done

wait "$VAC_PID" 2>/dev/null
echo "VACUUM finished after ~${T} samples (~$((T/2))s wall)"

echo "=== VACUUM output (last 15 lines) ==="
tail -15 "$EVIDIR/vacuum.log"

echo "=== per-worker RSS trajectory (max RSS per worker over time) ==="
awk -F'\t' 'NR>1 {
  if ($3+0 > peak[$2]) peak[$2] = $3+0
  if (!(t[$2]+0)) first[$2] = $3+0
  t[$2] = $1
}
END {
  for (p in peak) printf "worker pid=%s  first_rss=%d  peak_rss=%d  delta=%d KB\n", p, first[p], peak[p], peak[p]-first[p]
}' "$EVIDIR/rss-timeseries.tsv" | sort -k4 -nr

echo "=== max worker RSS across the whole run ==="
awk -F'\t' 'NR>1 && $3+0 > peak {peak=$3+0; pidp=$2; tp=$1} END{printf "peak rss_kb=%d  at t=%s  worker_pid=%s\n", peak+0, tp, pidp}' "$EVIDIR/rss-timeseries.tsv"

"$INSTALL/bin/pg_ctl" -D "$DATA" stop -m fast 2>&1 | tail -2
