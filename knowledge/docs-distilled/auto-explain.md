---
source_url: https://www.postgresql.org/docs/current/auto-explain.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — auto_explain (the executor-hook example)

`contrib/auto_explain` is the textbook example of chaining the four executor
hooks (`ExecutorStart/Run/Finish/End`) on `_PG_init`. It logs the plan of any
statement exceeding a duration threshold, with no application change. Read it
when wiring `ExecutorXxx_hook` in an extension. `[from-docs]`

## Loading & the hook chain (verified against source)

- `_PG_init` saves the previous hook then overwrites the global — the standard
  "save-prev, install-mine, call-prev-in-mine" idiom:
  `prev_ExecutorStart = ExecutorStart_hook; ExecutorStart_hook = explain_ExecutorStart;`
  (and the same for Run/Finish/End) at
  `source/contrib/auto_explain/auto_explain.c:313-320`; each wrapper calls the
  saved `prev_*` so multiple modules chain cleanly (e.g. `:368-369`).
  `[verified-by-code]`
- Loadable three ways: `shared_preload_libraries` (all sessions),
  `session_preload_libraries`, or per-session `LOAD 'auto_explain'` (superuser).
  **Only statements run *after* the load are instrumented.** `[from-docs]`

## Configuration (exact defaults)

- `auto_explain.log_min_duration` — ms; default **-1 (disabled)**; `0` logs all
  plans; superuser-only. Defined at `auto_explain.c:139`. `[verified-by-code]`
- `auto_explain.log_analyze` — default **off**. Turning it on makes the module
  behave like `EXPLAIN ANALYZE`. `[from-docs]`
- `auto_explain.log_buffers` / `log_wal` / `log_timing` / `log_triggers` — all
  require `log_analyze=on`. `log_timing` defaults **on**; the rest default
  **off**. `[from-docs]`
- `auto_explain.log_verbose` (off), `log_settings` (off), `log_format`
  (`text`|xml|json|yaml, default **text**), `log_level` (default **LOG**),
  `log_parameter_max_length` (default **-1** = full). `[from-docs]`
- `auto_explain.log_nested_statements` — default **off**: statements *inside*
  functions are not logged unless turned on. `[from-docs]`
- `auto_explain.sample_rate` — default **1** (all). Field
  `auto_explain_sample_rate = 1` at `auto_explain.c:49`; defined at `:297`.
  `[verified-by-code]`

## The two non-obvious traps

- **Timing overhead is unconditional.** With `log_analyze=on` + `log_timing=on`,
  per-node `INSTRUMENT_TIMER` runs on **every** statement in the session, even
  ones too fast to ever be logged — "an extremely negative impact on
  performance." Mitigation: `log_timing=off` (keeps row counts, drops per-node
  times). `[from-docs]`
- **Sampling is per top-level statement.** The sample decision is taken once at
  `nesting_level == 0` (`current_query_sampled = pg_prng_double(...) < sample_rate`,
  `auto_explain.c:339-342`) and inherited by every nested statement — so nested
  statements are all-or-nothing with their top statement, never independently
  sampled. `[verified-by-code]`

## Links into corpus

- `[[knowledge/docs-distilled/executor.md]]` — the `ExecutorStart→Run→Finish→End`
  lifecycle these hooks bracket.
- `[[knowledge/docs-distilled/parallel-plans.md]]` / `[[knowledge/docs-distilled/explicit-joins.md]]`
  — what the logged plan trees express.
- Skills: `executor-and-planner` (the hook points), `bgworker-and-extensions`
  (the `_PG_init` hook-chaining idiom), `gucs-config` (the `DefineCustom*` GUCs).
