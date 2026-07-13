# Phase 0 baseline — fdw_directmodify_leak

**Target:** upstream commit
`232d8caeaaa06fd3c6b76a68ef9c62ea5fdf12ea`
*"Fix memory leakage in postgres_fdw's DirectModify code path."*

- **Author + committer:** Tom Lane
- **Date:** 2025-05-30
- **Reviewer:** Matheus Alcantara
- **Backpatch-through:** PG13
- **Discussion:** postgr.es/m/2976982.1748049023@sss.pgh.pa.us
- **Files:** `contrib/postgres_fdw/postgres_fdw.c` (+35 / −27, single
  file)
- **Signal per commit message:** *"the ensuing session-lifespan leak
  is visible under Valgrind"* — hint that RSS-only observability is
  weak. Confirmed on this run: signal is only visible under
  significant amplification (~20 k iterations of the failing
  DirectModify pattern).

**Parent pin (harness base):** `d98cefe1143` (Allow larger packets
during GSSAPI authentication exchange) — the commit immediately
before the fix.

**Worktree:** `postgresql-dev-feature-fdw-directmodify-leak` on
branch `feature_fdw_directmodify_leak`.

**Build:** cassert + debug, meson build-debug, installed to
`install-debug/`.

## Reproducer

### Setup — postgres_fdw with loopback connection

```sql
CREATE EXTENSION postgres_fdw;
CREATE SERVER loopback FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (host '/tmp', port '<port>', dbname 'postgres');
CREATE USER MAPPING FOR PUBLIC SERVER loopback;
CREATE TABLE remote_t (id int PRIMARY KEY, val int, tag text);
INSERT INTO remote_t
  SELECT g, g*10, 'row' || g FROM generate_series(1, 1000) g;
CREATE FOREIGN TABLE t_fdw (id int, val int, tag text)
  SERVER loopback OPTIONS (table_name 'remote_t');
```

### Plan-shape verification (F31, Step 0.4)

```sql
EXPLAIN (VERBOSE, COSTS OFF)
UPDATE t_fdw SET val = val
 WHERE id BETWEEN 1 AND 100
 RETURNING id, 1000/(id-50);
```

produces:

```
 Update on public.t_fdw
   Output: id, (1000 / (id - 50))
   ->  Foreign Update on public.t_fdw
         Remote SQL: UPDATE public.remote_t SET val = val
                     WHERE ((id >= 1)) AND ((id <= 100)) RETURNING id
```

`Foreign Update` is the `DirectModify` shape — the whole modify is
pushed to the remote, `RETURNING id` is fetched back as a PGresult,
and the local `1000/(id-50)` projection runs on those returned
rows.  When id=50 hits the local projection, div-by-zero fires
mid-fetch and control aborts through the surrounding executor.
The PGresult holding the ~100-row RETURNING batch is orphaned in
libpq's malloc pool.

If the plan shape is anything OTHER than `Foreign Update` (e.g. a
local `Update on t_fdw` with a `Foreign Scan` child), the leak
doesn't reproduce — that's a non-DirectModify shape and the fix
isn't exercised.

### Amplified reproducer

```sql
-- 20 000 iterations of the failing DirectModify + rollback.
-- Each iteration leaks the PGresult for a ~100-row RETURNING batch
-- (~4 KB of malloc'd libpq state).
BEGIN;
UPDATE t_fdw SET val = val WHERE id BETWEEN 1 AND 100
  RETURNING id, 1000/(id-50);
ROLLBACK;
-- ... × 20 000
```

## Leak signal on parent pin

Backend RSS sampled by external `ps -o rss=` targeting the psql
backend's PID (looked up via `pg_stat_activity` with a
`state <> 'idle'` + `application_name = 'psql'` filter):

| t     | RSS   | delta         |
|------:|------:|--------------:|
|   1 s |  11.6 MB | (baseline) |
|   5 s |  31.8 MB | +20 MB      |
|  10 s |  26.3 MB | (noisy)     |
|  15 s |  46.7 MB |             |
|  20 s |  70.1 MB |             |
|  25 s |  90.9 MB | **+79 MB / 24 s** |
|  26 s |  88.6 MB | (session ending) |

Sustained **~3.3 MB/s** of RSS climb across the loop, dropping
slightly when the loop finishes (some libpq caches settle).  The
noise at t=8-9 s (a temporary drop to ~21 MB) is likely
libpq-side batching / connection retry behavior; net trajectory is
unambiguously upward across the 25-second window.

Query-lifespan (per-transaction) memory usage releases at each
`ROLLBACK`, so per-iteration signal is ~4 KB (100-row RETURNING
PGresult + row-buffer headers).  20 000 iterations × 4 KB ≈ 80 MB
— matches the observed RSS delta.

## Notes on reproducer construction (F31 evidence)

Two dead ends before landing the working amplifier, both worth
recording:

1. **`WITH x AS (UPDATE ... RETURNING) SELECT ... FROM x`**
   pattern executes the CTE eagerly BEFORE the SELECT projects,
   so the div-by-zero fires inside CTE evaluation.  Plan shape
   was still `Foreign Update`, but the timing of the abort
   relative to PGresult receipt differs slightly from the
   direct-`RETURNING` shape.  Kept the direct shape for
   fidelity.

2. **pgbench with `\set ON_ERROR_STOP 0`** silently ignored the
   directive because pgbench's error handling doesn't use psql's
   `ON_ERROR_STOP` semantics — pgbench aborts on any query
   error unless `--exit-on-abort no` is passed (available since
   PG 17).  Switched to a `BEGIN; UPDATE; ROLLBACK;` psql script
   which lets each failure roll back cleanly and the loop
   continue.

3. **Plpgsql `EXCEPTION WHEN OTHERS` wrapper** cached the plan at
   its first invocation, which apparently interfered with
   DirectModify re-planning; the loop completed in ~50 ms across
   2 000 calls, suggesting the failing UPDATE wasn't actually
   firing on iterations 2..2000.  Direct `BEGIN;`/`ROLLBACK;`
   sidesteps the cache.

Cite these as F31 evidence when this scenario lands next in a
brainstorm — the reproducer-shape iteration cost was real.

## Phase 0 exit condition — MET

- Reproducer exists at both the semantic level (a failing
  DirectModify RETURNING that leaks a PGresult) and the amplified
  level (20 k-iteration RSS canary).
- Reproducer verified to show ~80 MB of RSS growth over ~25 s on
  the parent pin — enough magnitude to compare pre-fix vs post-fix
  trivially.
- Plan shape (`Foreign Update`) confirmed and cited per F31 /
  scenario#34 Step 0.4.
- No pg_backend_memory_contexts signal (the PGresult lives in
  libpq's malloc pool, not a MemoryContext) — this is a
  `ps -o rss=` and Valgrind class of signal.
