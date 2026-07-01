#!/usr/bin/env bash
# Inside-container: build PG, initdb, run jsonpath reproducer, sample backend RSS.
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
  echo "Commit: $(cd /pg-source && git rev-parse HEAD 2>/dev/null || echo 'unknown — worktree git pointer broken inside container')"
  echo "Date:   $(date -u +%FT%TZ)"
} | tee "$EVIDIR/build-info.txt"

"$INSTALL/bin/initdb" -D "$DATA" --locale=C --encoding=UTF8 >/tmp/initdb.log 2>&1 || { tail -20 /tmp/initdb.log; exit 1; }
"$INSTALL/bin/pg_ctl" -D "$DATA" -l "$DATA/server.log" -o "-k /tmp" start
sleep 1

# Run reproducer in background. Use a function so the redirection is unambiguous.
run_repro() {
  "$INSTALL/bin/psql" -h /tmp -d postgres -X -q -At <<'SQL'
\timing on
SELECT count(*) FROM (
  SELECT jsonb_path_query(
    (SELECT jsonb_agg(i) FROM generate_series(1, 10000) i),
    '$[*] ? (@ < $)'
  )
) z;
SQL
}

echo "=== launching reproducer in background ==="
run_repro > "$EVIDIR/repro-output.txt" 2>&1 &
REPRO_PID=$!
echo "reproducer host pid: $REPRO_PID"

# Sample RSS while reproducer runs. Match only `postgres: postgres postgres ...`
# backend processes (not postmaster, not aux workers, not the awk itself).
{
  echo -e "t\tpid\trss_kb\tcmd"
} > "$EVIDIR/rss-timeseries.tsv"

T=0
while kill -0 "$REPRO_PID" 2>/dev/null; do
  # Sample any postgres process with reasonably large RSS — pick the busiest.
  # Anchor on 'postgres' in cmd to skip the awk/sleep/bash.
  ps -e -o pid=,rss=,args= 2>/dev/null \
    | awk '$NF!="" && /postgres/ && !/pg_ctl|inside-jsonpath|grep|awk/' \
    | sort -k2,2 -nr | head -3 \
    | while read -r pid rss rest; do
        echo -e "${T}\t${pid}\t${rss}\t${rest}" >> "$EVIDIR/rss-timeseries.tsv"
      done || true
  if [[ $T -gt 600 ]]; then
    echo "timeout at $T s — killing reproducer"
    kill "$REPRO_PID" 2>/dev/null || true
    break
  fi
  sleep 0.2
  T=$((T+1))
done

wait "$REPRO_PID" 2>/dev/null
REPRO_EXIT=$?
echo "reproducer exit: $REPRO_EXIT after ~${T}s"

echo "=== reproducer output ==="
cat "$EVIDIR/repro-output.txt"

echo "=== RSS peak observed ==="
awk -F'\t' 'NR>1 && $3+0 > peak {peak=$3+0; pidp=$2; tp=$1} END{printf "peak rss_kb=%d  at t=%ss  pid=%s\n", peak+0, tp, pidp}' "$EVIDIR/rss-timeseries.tsv"

echo "=== RSS timeline ==="
awk -F'\t' 'NR>1 {if($3+0>max[$1]) max[$1]=$3+0; pid[$1]=$2} END {for(t in max) printf "t=%ss  pid=%s  max_rss_kb=%d\n", t, pid[t], max[t]}' "$EVIDIR/rss-timeseries.tsv" | sort -t= -k2 -n

"$INSTALL/bin/pg_ctl" -D "$DATA" stop -m fast 2>&1 | tail -2
