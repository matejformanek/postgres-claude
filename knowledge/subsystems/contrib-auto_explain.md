# contrib-auto_explain (automatic EXPLAIN logger)

- **Source path:** `source/contrib/auto_explain/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` only — NOT a SQL
  extension (no `.control` file, no `CREATE EXTENSION`)
- **Surface:** zero SQL functions; everything via GUCs

## 1. Purpose

Automatically log the `EXPLAIN` plan of any statement whose
execution exceeds a configurable threshold. Used in production
to catch the long tail of slow queries without modifying
application code or running `EXPLAIN` after the fact (by which
time the plan may have changed).

Differs from every other contrib extension covered so far —
it's a **hook installer**, not a function library. No SQL
surface, no superuser-callable functions. The GUCs are the
entire interface.

## 2. Mental model — three executor hooks

The module installs three executor-callback hooks at
`_PG_init` [verified-by-code `auto_explain.c:313-320`]:

```c
prev_ExecutorStart = ExecutorStart_hook;
ExecutorStart_hook = explain_ExecutorStart;
prev_ExecutorRun   = ExecutorRun_hook;
ExecutorRun_hook   = explain_ExecutorRun;
prev_ExecutorFinish = ExecutorFinish_hook;
ExecutorFinish_hook = explain_ExecutorFinish;
prev_ExecutorEnd   = ExecutorEnd_hook;
ExecutorEnd_hook   = explain_ExecutorEnd;
```

The hook chain pattern: save the previous hook, install the
new one, call the previous from inside the new
[verified-by-code `auto_explain.c:384-385`]. This is the
canonical hook-stacking idiom — multiple modules can install
the same hook and all observe the executor flow.

- `ExecutorStart` — install instrumentation if the query is
  to be logged.
- `ExecutorEnd` — query just finished; if it ran > threshold,
  log the plan + actual timings.

## 3. The 12 GUCs

[verified-by-code `auto_explain.c:139-280`]

| GUC | Default | Purpose |
|---|---|---|
| `auto_explain.log_min_duration` | -1 (off) | Threshold in ms; -1 disables |
| `auto_explain.log_parameter_max_length` | -1 | Truncate bound parameters |
| `auto_explain.log_analyze` | off | Like `EXPLAIN ANALYZE` (actual timings) |
| `auto_explain.log_settings` | off | Include non-default GUCs |
| `auto_explain.log_verbose` | off | `EXPLAIN VERBOSE` semantics |
| `auto_explain.log_buffers` | off | Include buffer-usage counters |
| `auto_explain.log_io` | off | Include I/O timing |
| `auto_explain.log_wal` | off | Include WAL-record stats |
| `auto_explain.log_triggers` | off | Include trigger timings |
| `auto_explain.log_nested_statements` | off | Log inside functions / procedures |
| `auto_explain.log_timing` | on | Per-node timing (high overhead on some hardware) |
| `auto_explain.log_format` | text | text / xml / json / yaml |
| `auto_explain.log_level` | LOG | Syslog level for output |
| `auto_explain.sample_rate` | 1.0 | Sample fraction (0..1) for non-zero-duration queries |

The `log_analyze` GUC is the load-bearing one — it activates
the per-tuple instrumentation that makes EXPLAIN ANALYZE
informative but expensive. Enabling it on a hot OLTP system
adds measurable per-row overhead.

## 4. The threshold + sampling logic

`log_min_duration` is the gate:
- `-1`: log nothing.
- `0`: log every query.
- `N > 0`: log queries that ran ≥ N ms.

If `sample_rate < 1.0`, eligible queries are dropped
randomly to that fraction. Sample-rate applies BEFORE the
duration check would have triggered logging — useful when
even sampled overhead matters.

## 5. The "nested statements" knob

By default, only the outermost statement in a function /
procedure / trigger is considered for logging. With
`log_nested_statements=on`, every SQL statement inside an
SPL function gets the same threshold check. Useful for
diagnosing slow PL/pgSQL functions whose individual SQL
fragments add up.

## 6. Production-use guidance

- **Load only via `shared_preload_libraries`** — the module's
  hooks must be installed at postmaster start to catch every
  query. Per-session `LOAD` won't work for non-superuser
  queries.
- **`log_analyze=on` doubles or triples per-tuple overhead.**
  Acceptable for non-critical workloads; benchmark before
  enabling on a hot OLTP system.
- **`log_timing=off` mitigates `log_analyze` cost** on
  hardware with expensive `clock_gettime`. Per-node row counts
  still work; only the per-node timings disappear.
- **`log_buffers` + `log_io` are cheap** — they read existing
  counters; no extra clock reads. Add them by default.
- **`log_format=json`** with a log aggregator (Loki / ELK) is
  the canonical observability stack pattern.

## 7. Hook composition with other modules

`pg_stat_statements`, `pg_plan_advice`, custom audit modules
all install executor hooks. **Load order in
`shared_preload_libraries` matters** — the last loaded module
runs first (last-installed = top of the chain). For
auto_explain to see actual execution timings, it should
chain on top of any module that mutates the plan.

The hook chain pattern (call `prev_*` from inside `explain_*`)
[verified-by-code `auto_explain.c:384-385`] makes the order
correct regardless: every chained hook gets to observe.

## 8. Output format

Logged lines go through `ereport` at `auto_explain.log_level`
(default `LOG`). Format follows `EXPLAIN`'s `format` option:

- `text` (default) — multi-line, human-readable; same as
  `psql`'s `EXPLAIN ANALYZE`.
- `json` — single-line, log-parser-friendly.
- `xml`, `yaml` — for ecosystem tools that prefer them.

Each log line is prefixed by the standard logger metadata
(`log_line_prefix` + the query identifier if
`compute_query_id=on`).

## 9. Invariants

- **[INV-1]** No SQL surface; all interaction is via GUCs.
- **[INV-2]** Hooks chain via `prev_*` calls; never overwrite
  without preserving the predecessor.
- **[INV-3]** `log_analyze=on` requires `ExecutorStart` to
  enable instrumentation BEFORE the first tuple is fetched.
- **[INV-4]** `log_nested_statements=off` (default) suppresses
  inside-SPL logging; queries from `SECURITY DEFINER`
  functions are still considered top-level.
- **[INV-5]** `sample_rate=0` disables logging without
  releasing the hook (cheaper to re-enable than to drop the
  module).

## 10. Useful greps

- GUC registration sites:
  `grep -n 'DefineCustom.*Variable' source/contrib/auto_explain/auto_explain.c`
- Hook installation:
  `grep -n 'ExecutorStart_hook\|ExecutorRun_hook\|ExecutorEnd_hook' source/contrib/auto_explain/auto_explain.c`
- Sampling + threshold check:
  `grep -n 'sample_rate\|log_min_duration' source/contrib/auto_explain/auto_explain.c`

## 11. Cross-references

- `.claude/skills/debugging/SKILL.md` — auto_explain is the
  recommended slow-query-discovery path; complements
  `pg_stat_statements`.
- `.claude/skills/executor-and-planner/SKILL.md` — the
  Executor* hooks this module attaches to.
- `.claude/skills/gucs-config/SKILL.md` — `DefineCustom*Variable`
  registration pattern (the GUC surface).
- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  `shared_preload_libraries` loading.
- `knowledge/subsystems/executor.md` — executor hook
  contracts; what the hook callbacks see.
- `source/contrib/auto_explain/auto_explain.c` — single-file
  implementation.
