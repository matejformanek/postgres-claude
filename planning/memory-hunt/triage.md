# Phase 1 triage — calibration target picked

**Date:** 2026-06-22
**Phase 0 outcome:** harness clean on master; pivoted to surgical reproducers
against the 2025-2026 leak-fix corpus.

## Target picked

**Commit `5a2043bf713`** — *"Fix transient memory leakage in jsonpath
evaluation."* (Tom Lane, 2026-03-19)

**Parent (pre-fix):** `7724cb9935a96eabba80f5e62ee4b32068967dd2`

### Why this one

1. **Gold-standard reproducer in the commit message.** Tom Lane's
   commits historically ship a one-line SQL repro and a target
   RSS/time number. Eliminates "is this the right query?" friction.

2. **Big signal-to-noise ratio.** Parent → fix is a 177× memory
   reduction. No statistical fishing required; the leak is visible
   at the OS level.

3. **Recent + isolated.** Single-commit fix on `jsonpath_exec.c` +
   `jsonpath_internal.h` (2026-03-19). Easy to isolate; no
   surrounding feature work to disentangle.

4. **Subsystem we already have corpus for** (or near). JSON path
   evaluation sits at the executor-expression boundary; relates
   to existing `knowledge/idioms/memory-contexts.md` work.

5. **Tests the right detection signal.** This leak doesn't show in
   Valgrind's `definitely lost:` line — the temp lists are reachable
   from a still-live MemoryContext throughout the function call.
   RSS sampling catches it; `pg_backend_memory_contexts` would too.
   Confirms our harness has *two* viable signals, not just Valgrind.

## Reproducer recipe (one-line)

```sql
SELECT jsonb_path_query(
  (SELECT jsonb_agg(i) FROM generate_series(1, 10000) i),
  '$[*] ? (@ < $)');
```

Driver: `planning/memory-hunt/container/inside-jsonpath.sh` (rebuilds
PG, initdbs, samples backend RSS every 0.2s during query execution).

## Evidence

### Parent commit (`7724cb9935a`)

`planning/memory-hunt/evidence/jsonpath-parent/`:

- `rss-timeseries.tsv`: RSS climbs from ~32 MB baseline to a peak
  of **5,686,688 KB (5.7 GB)** at t=49s; plateaus until t=59s; drops
  to ~1.4 GB at t=61s as the query returns.
- `repro-output.txt`: returned 9999 rows; query took ~60s.

### Fix commit (`5a2043bf713`)

`planning/memory-hunt/evidence/jsonpath-fix/`:

- `rss-timeseries.tsv`: RSS stays flat at **32,160 KB (32 MB)** for
  the entire 15s probe window — no measurable growth.
- `repro-output.txt`: returned 9999 rows; query took 3.07s.

### Verification deltas

| metric                | parent           | fix              | delta       |
|-----------------------|-----------------:|-----------------:|------------:|
| Peak backend RSS      | 5,686,688 KB     | 32,160 KB        | -99.4%      |
| Query wall-clock      | ~60 s            | 3.07 s           | 20× faster  |
| Result correctness    | 9999 rows        | 9999 rows        | identical   |

## Mapping to plan §3 (initial candidate files)

The fix touches:

```
src/backend/utils/adt/jsonpath_exec.c
src/include/utils/jsonpath_internal.h
```

(Plus a test addition under `src/test/regress/expected/jsonb_jsonpath.out`
and `sql/jsonb_jsonpath.sql`.)

## Decision for next phase

The plan as written would now invoke `pg-feature-brainstorm` → 
`pg-feature-plan` → `pg-implement` *as if the fix didn't exist*, then
compare our derived fix to Tom Lane's actual fix as the calibration
output. Three branches at this fork:

A. **Run the trilogy blind** — best methodology validation, biggest
   work. The brainstorm has to read `JsonValueList` + its callers in
   `jsonpath_exec.c`, decide between "track + free per-iteration"
   vs "switch to a per-evaluation arena" vs Tom Lane's actual
   approach (expansible-array JsonbValue struct with on-stack
   inline storage). Compare ours to Tom's at the end.

B. **Apply the fix manually as a regression test** — checkout the
   fix on top of parent, confirm the leak is gone via the harness
   we just built, no trilogy run. Validates the harness only.

C. **Stop here, write up methodology lesson** — the per-target
   harness exists; we've shown it surfaces a known leak with a
   177× signal. Phase 1 calibration done. Future targets can use
   the same template.

Recommend (A) — that's the actual sesvars-style calibration this
plan was designed to produce. (B) and (C) save time but punt on
the harder question: can the planner trilogy actually reach Tom
Lane's design choices unaided?
