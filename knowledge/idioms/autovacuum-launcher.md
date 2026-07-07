# Autovacuum launcher — the autovac launcher + worker loop

`autovacuum_launcher` is the postmaster-spawned process that
**decides when to vacuum** and **forks per-database worker
processes** to do the work. The launcher runs continuously
(naptime between cycles); each worker runs to completion
(one database, one pass). Tuning autovacuum tuning is
mostly tuning these knobs.

Anchors:
- `source/src/backend/postmaster/autovacuum.c:413
  AutoVacLauncherMain` [verified-by-code]
- `source/src/backend/postmaster/autovacuum.c:378
  do_autovacuum` (worker main) [verified-by-code]
- `knowledge/idioms/vacuum-skip-pages.md` — companion;
  what VACUUM actually does
- `knowledge/idioms/xmin-horizon-management.md` — what
  autovacuum is trying to advance

## The launcher main loop

```c
AutoVacLauncherMain(const void *startup_data, ...)
```

[verified-by-code `autovacuum.c:413`]

Phases per iteration:

1. **Wait** — `autovacuum_naptime` seconds (default 60).
2. **Build database list** — `pg_database`-scan to identify
   per-DB candidates.
3. **Pick a database** — round-robin or priority-based
   (databases nearing wraparound jump the queue).
4. **Fork a worker** — `AutoVacWorkerMain` for that DB.
5. Loop.

The launcher itself doesn't do per-table VACUUM work; it
just delegates.

## The 2 launcher GUCs

```c
int autovacuum_naptime;        /* default 60 seconds */
int autovacuum_max_workers;    /* default 3 */
```

[verified-by-code `autovacuum.c:125-127`]

- **`autovacuum_naptime`** — interval between launcher
  cycles. Lower = launcher checks more often (more
  responsive but more CPU); higher = less responsive but
  cheaper.
- **`autovacuum_max_workers`** — max concurrent worker
  processes. Each worker is one DB; concurrency = how
  many DBs autovac can vacuum simultaneously.

## The worker (do_autovacuum)

```c
static void do_autovacuum(void);
```

[verified-by-code `autovacuum.c:378`]

For the assigned database:

1. Connect to the database.
2. Build the list of candidate tables (those exceeding
   the autovac thresholds).
3. For each candidate, VACUUM + ANALYZE (or just one).
4. Disconnect; exit.

A worker runs to completion. The launcher waits naptime
before starting the next worker on the same DB.

## The threshold formula

A table is autovacuum-candidate when:

```
n_dead_tup ≥ autovacuum_vacuum_threshold +
             autovacuum_vacuum_scale_factor × reltuples
```

- **`autovacuum_vacuum_threshold`** — fixed component
  (default 50).
- **`autovacuum_vacuum_scale_factor`** — proportional
  component (default 0.2 = 20%).

So a small table (100 rows) is candidate at 70 dead tuples;
a large table (1M rows) is candidate at 200,050.

The thresholds can be per-table-overridden via
`ALTER TABLE ... SET (autovacuum_vacuum_threshold = ...)`.

## ANALYZE threshold

```
n_mod_since_analyze ≥ autovacuum_analyze_threshold +
                       autovacuum_analyze_scale_factor × reltuples
```

Separate thresholds for ANALYZE (collect stats) vs VACUUM
(remove dead tuples). Default `analyze_scale_factor = 0.1`
(10%).

ANALYZE is cheaper than VACUUM; tighter thresholds are
common.

## Wraparound emergency mode

When a database's oldest XID is approaching wraparound (~200
million transactions remaining), autovacuum enters
**emergency mode**:

- Workers ignore `autovacuum_vacuum_threshold` — VACUUM
  every relation.
- Workers ignore `cost_delay` limits — go as fast as
  possible.
- The launcher picks the at-risk database first.

This is the system protecting itself; you can't disable it.
Visible to operators as `pg_stat_database.tup_returned`
spikes + autovacuum runs that don't stop.

## per-table autovac tuning

For specific large tables:

```sql
ALTER TABLE bigtable SET (
    autovacuum_vacuum_scale_factor = 0.05,    -- 5% instead of 20%
    autovacuum_analyze_scale_factor = 0.01    -- 1% instead of 10%
);
```

Useful for tables where you want autovac to run more often.
Set scale-factor low and threshold high (or vice versa) to
balance.

## Disabling autovacuum (you don't)

`autovacuum = off` is permitted but **strongly
discouraged**. Without autovacuum:
- Dead tuples accumulate (bloat).
- Stats grow stale (bad query plans).
- XID wraparound is hard-to-prevent.

The legitimate "disable autovacuum" use case is a one-table
exception:

```sql
ALTER TABLE static_lookup SET (autovacuum_enabled = false);
```

For a table that NEVER updates (or whose updates are too
expensive to vacuum frequently).

## The worker-launcher coordination

The launcher and workers communicate via shared memory
(`AutoVacuumShmem`):

- Launcher: posts "please vacuum DB X" requests.
- Workers: claim a request, run, post completion.
- Launcher: re-checks after worker exits; possibly schedules
  more.

The launcher also receives signals from regular backends:
`pg_stat_activity` events, dropped relations, etc., to
prioritize attention.

## Common review-time concerns

- **`autovacuum_max_workers` ≤ `max_worker_processes`** —
  workers come from the bgworker pool.
- **Don't disable autovacuum cluster-wide.** Bloat + bad
  plans + wraparound risk.
- **Per-table tuning beats global tuning** for hot tables.
- **Wraparound emergency runs are unstoppable** — plan
  capacity accordingly.
- **Workers respect `vacuum_cost_delay` / `cost_limit`** —
  configurable per-worker pacing.

## Invariants

- **[INV-1]** Launcher runs continuously; per-DB workers
  forked on demand.
- **[INV-2]** `n_dead_tup ≥ thr + scale × reltuples` is the
  vacuum-candidate predicate.
- **[INV-3]** Wraparound emergency overrides thresholds.
- **[INV-4]** Per-table settings override global.
- **[INV-5]** `autovacuum_max_workers` is the concurrency
  cap; comes from bgworker pool.

## Useful greps

- The launcher entry:
  `grep -n 'AutoVacLauncherMain\|AutoVacWorkerMain' source/src/backend/postmaster/autovacuum.c | head -5`
- The threshold computation:
  `grep -n 'autovacuum_vacuum_threshold\|autovacuum_vacuum_scale_factor' source/src/backend/postmaster/autovacuum.c | head -10`
- Wraparound logic:
  `grep -n 'wraparound\|EmergencyMode' source/src/backend/postmaster/autovacuum.c | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/postmaster/autovacuum.c`](../files/src/backend/postmaster/autovacuum.c.md) | 378 | do_autovacuum (worker main) |
| [`src/backend/postmaster/autovacuum.c`](../files/src/backend/postmaster/autovacuum.c.md) | 413 | AutoVacLauncherMain |
| [`src/backend/postmaster/autovacuum.c`](../files/src/backend/postmaster/autovacuum.c.md) | — | launcher + worker implementation |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/vacuum-skip-pages.md` — what VACUUM
  actually does once a worker starts.
- `knowledge/idioms/xmin-horizon-management.md` — what
  autovac is trying to advance.
- `knowledge/idioms/background-worker-startup.md` — workers
  come from the bgworker pool.
- `knowledge/subsystems/contrib-pg_stat_statements.md` —
  observability for autovac impact.
- `.claude/skills/debugging/SKILL.md` — autovacuum diag
  is a common probe.
- `source/src/backend/postmaster/autovacuum.c` — launcher
  + worker implementation.
