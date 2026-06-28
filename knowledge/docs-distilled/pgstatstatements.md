---
source_url: https://www.postgresql.org/docs/current/pgstatstatements.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_stat_statements (query jumbling + the R13 contrib gate)

`contrib/pg_stat_statements` aggregates planning/execution stats per *normalized*
query. It is the contrib module the R13 phase-end ladder specifically gates on
for **catalog** and **executor/planner** changes — because it exercises builtins
and operators by name and silently regresses when their entries shift. This note
captures the jumbling/storage internals, not the column reference. `[from-docs]`

## Startup & the compute_query_id dependency (verified against source)

- Must be in `shared_preload_libraries`: it allocates shared memory at start
  (sized by `pg_stat_statements.max`, allocated even if `track=none`) and installs
  `planner_hook = pgss_planner` (`source/contrib/pg_stat_statements/pg_stat_statements.c:483`)
  and `ExecutorStart_hook = pgss_ExecutorStart` (`:485`). `[verified-by-code]`
- Inactive unless **`compute_query_id`** is `on`/`auto` (or a third-party id
  module is loaded); otherwise `queryid` is 0 and nothing is tracked. Since PG14
  the normalization/id is done by **core**, not the module
  (`pg_stat_statements.c:12`). `[verified-by-code]`

## Query jumbling & normalization

- `queryid` is a hash of the **post-parse-analysis tree** (the "jumble"), not the
  SQL text — so constants are abstracted away and grouped. The representative
  text shows constants replaced by `$1,$2,…` (numbering continues past the
  highest existing `$n`). `[from-docs]`
- **IN-list squashing**: queries differing only in list length collapse to one
  entry, rendered `… IN ($1 /*, ... */)`. `[from-docs]`
- One text → **multiple** entries when meaning differs (e.g. different
  `search_path` resolving the same name to different objects). Multiple texts →
  one entry for semantically-equivalent queries differing only in constants.
  queryid is **sensitive to object OIDs** (drop+recreate a function/table → new
  id) and to **machine architecture**, and is **unstable across major versions**
  but stable across minor versions on the same arch. `[from-docs]`

## Entry management & query-text storage (verified against source)

- `pg_stat_statements.max` default **5000** (`static int pgss_max = 5000;`
  `pg_stat_statements.c:303`; `DefineCustomIntVariable(... &pgss_max …)` `:415`).
  Hard cap on distinct (dbid, userid, queryid, toplevel) rows; least-executed
  entries are evicted (usage decays by `USAGE_DECREASE_FACTOR 0.99`, freeing
  `USAGE_DEALLOC_PERCENT 5`% at a time, `:98-100`). `pg_stat_statements_info.dealloc`
  counts evictions; a high rate → raise `.max`. `[verified-by-code]`
- **Query texts live in an external file, not shared memory** —
  `PGSS_TEXT_FILE = PG_STAT_TMP_DIR "/pgss_query_texts.stat"`
  (`pg_stat_statements.c:85`), referenced by `query_offset` per entry (`:237`).
  Lets texts be arbitrarily long; if the file bloats, all texts may be discarded
  (rows show `NULL` query, stats survive). `[verified-by-code]`
- `pg_stat_statements.save` default **on** (persist + reload across restart).
  `track` (default **top**; top/all/none), `track_utility` (default **on**),
  `track_planning` (default **off** — costly under concurrency as identical
  statements contend on one entry). `[from-docs]`

## Why R13 names this module

- A catalog change (`pg_proc.dat`/`pg_operator.dat` …) or executor/planner change
  can shift jumbling, costing, or builtin resolution; `pg_stat_statements`'s own
  regression suite (e.g. `squashing.sql`) exercises those by name and is
  **invisible to a `--suite regress`-only check**. R13 requires
  `--suite pg_stat_statements` for both tiers. See
  `.claude/rules/pg-implement-discipline.md` (R13). `[from-repo]`

## Links into corpus

- `[[knowledge/docs-distilled/monitoring-stats.md]]` — the cumulative-stats system
  this complements.
- `[[knowledge/docs-distilled/auto-explain.md]]` — the other executor-hook contrib
  (per-statement plans vs aggregate counters).
- Skills: `testing` (R13 contrib gate), `executor-and-planner`,
  `catalog-conventions` (why catalog edits can move queryids).
