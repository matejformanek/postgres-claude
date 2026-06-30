# `contrib/auto_explain/auto_explain.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~830
- **Source:** `source/contrib/auto_explain/auto_explain.c`

Single-file backend extension that installs the four Executor* hooks
(`ExecutorStart`, `ExecutorRun`, `ExecutorFinish`, `ExecutorEnd`) and
auto-emits an EXPLAIN-style plan dump to the server log for any
top-level (or optionally nested) query whose wall-clock duration
exceeds `auto_explain.log_min_duration`. Sampling, per-query
instrumentation flag selection, and a hand-rolled mini-parser for
extension EXPLAIN options live here. The module is loaded via
`session_preload_libraries` / `shared_preload_libraries`. [verified-by-code]

## API / entry points

- `_PG_init` (auto_explain.c:135-321) — registers 14 GUCs, all
  `PGC_SUSET`, then chains the four Executor* hooks saving each
  previous hook pointer. `MarkGUCPrefixReserved("auto_explain")`
  blocks unknown sub-GUCs. [verified-by-code]
- `explain_ExecutorStart` (auto_explain.c:326-372) — at
  `nesting_level == 0` decides per-query whether to sample, using
  `pg_prng_double(&pg_global_prng_state) < sample_rate`. Parallel
  workers are forced not-sampled so the leader's EXPLAIN handles
  reporting once. Then OR-s in `INSTRUMENT_TIMER` (always) and, if
  `log_analyze`, the requested INSTRUMENT_* bits. [verified-by-code]
- `explain_ExecutorRun` / `explain_ExecutorFinish`
  (auto_explain.c:377-415) — wrap `standard_*` with `PG_TRY/PG_FINALLY`
  to keep `nesting_level` honest across longjmp out of executor.
  [verified-by-code]
- `explain_ExecutorEnd` (auto_explain.c:420-500) — does the actual
  ereport. Switches to `queryDesc->estate->es_query_cxt` so
  `NewExplainState` and friends get cleaned up at executor teardown.
  Logs only if `INSTR_TIME_GET_MILLISEC(query_instr->total) >=
  log_min_duration`. Emits via `ereport(auto_explain_log_level,
  errmsg("duration: %.3f ms  plan:\n%s", …), errhidestmt(true))`.
  [verified-by-code]
- `check_log_extension_options` / `assign_log_extension_options`
  (auto_explain.c:505-584) — GUC check/assign hooks for the string
  GUC `log_extension_options`. Parses the raw string via
  `auto_explain_split_options` into a flexible-array
  `auto_explain_extension_options *` stored in GUC extra. Retry loop
  enlarges options[] up to one extra time when first parse pass
  finds noptions > maxoptions. [verified-by-code]
- `auto_explain_split_options` (auto_explain.c:662-829) — hand-rolled
  mini-parser that accepts the same flavor of `(name VALUE, ...)`
  syntax the main EXPLAIN parser does: identifiers (optionally
  double-quoted), single-quoted string literals, ints (strtol with
  base 0), floats (strtod). [verified-by-code] [from-comment]

## Notable invariants / details

- All GUCs are `PGC_SUSET` (auto_explain.c:145, 157, 169, ...) — only
  superusers can SET them at session level. Loading the module itself
  requires either being trusted (`session_preload_libraries`) or
  `shared_preload_libraries`. [verified-by-code]
- Sampling decision is taken once per top-level statement; nested
  statements inherit it (auto_explain.c:339-344). So with
  `sample_rate < 1`, a single user query is fully in or fully out;
  this is what `auto_explain_enabled()` (line 104) encodes.
  [verified-by-code]
- `INSTRUMENT_TIMER` is forced on in `query_instr_options` even when
  `log_analyze=false`, because the duration test in ExecutorEnd needs
  `query_instr->total` (auto_explain.c:349-350). The expensive
  *per-node* instrumentation is only added under `log_analyze`.
  [verified-by-code]
- JSON output is post-processed (auto_explain.c:474-479) by replacing
  the first and last bytes with `{` and `}` so the result is a single
  JSON object rather than an array element. This is a fragile
  textual hack that assumes `ExplainBeginOutput`/`ExplainEndOutput`
  produced specific bracket characters. [verified-by-code]
  [ISSUE-style: fragile JSON bracket fix-up (nit)]
- `errhidestmt(true)` (auto_explain.c:490) is used because the plan
  already embeds the query text via `ExplainQueryText`; otherwise
  log_statement output would double-print. [verified-by-code]
  [from-comment]
- `log_min_duration = -1` disables logging entirely; `0` logs every
  query. Sample rate is meaningful only when `log_min_duration >= 0`.
  [verified-by-code]
- Per-extension EXPLAIN options are validated at GUC-check time via
  `GUCCheckExplainExtensionOption(name, value, type)`
  (auto_explain.c:565-566). The option list is applied at log time
  via `ApplyExtensionExplainOption` (auto_explain.c:611).
  [verified-by-code]

## Potential issues

- auto_explain.c:455-456. **Full query text and parameter values are
  logged at the configured `log_level`** via `ExplainQueryText` and
  `ExplainQueryParameters`. With `log_parameter_max_length = -1`
  (the default) parameter values are logged in full. On a busy
  production system with PII columns this is the single biggest
  data-leak surface in auto_explain. The `log_parameter_max_length`
  GUC is the only knob; there is no opt-out per-table or per-role.
  [ISSUE-security: full bind parameter logging by default; PII risk
  on shared loggers (likely)]
- auto_explain.c:483-490. The ereport uses the caller-controlled
  `log_level` GUC. A misconfigured site that sets
  `auto_explain.log_level = warning` or `notice` will surface the
  full plan + parameters to clients over the wire, not just the log.
  `errhidestmt(true)` hides the statement but does NOT hide the
  `errmsg("duration … plan: …")` body. [ISSUE-security:
  client-visible plan leak when log_level >= NOTICE (maybe)]
- auto_explain.c:530-532. `guc_malloc(LOG, …)` returns NULL on OOM
  inside a GUC check hook; the early `return false` propagates that
  as a generic check-failure. There is no `GUC_check_errdetail` for
  the OOM case, so the user sees only "invalid value for parameter".
  [ISSUE-style: silent OOM in GUC check (nit)]
- auto_explain.c:438-449. `es->memory = false` is commented out with
  the bare note "No support for MEMORY". This is a stale TODO — the
  `memory` ExplainState field is not unconditionally zeroed by
  `NewExplainState`; it relies on the calloc-style init. Functionally
  fine, but the dead comment is misleading. [ISSUE-stale-todo:
  "No support for MEMORY" lingering (nit)]
- auto_explain.c:339-345. Sampling uses `pg_global_prng_state`. The
  decision is correlated across all backends sharing that PRNG state
  in the sense that there is no per-query unique seed. For uniform
  sampling this is fine, but a sophisticated probe could detect
  whether their query was sampled by timing the executor's extra
  instrumentation cost. [ISSUE-question: minor timing-side-channel
  via instrument enablement (nit)]

## Cross-references

- `knowledge/issues/auto_explain.md` — per-extension issue register
  (created if absent).
- `knowledge/idioms/executor-hooks.md` for the prev-hook chain
  pattern.
- Companion: `contrib/auto_explain/t/001_auto_explain.pl` for TAP
  coverage of the sample rate and parameter-logging knobs.

<!-- issues:auto:begin -->
- [Issue register — `auto_explain`](../../../issues/auto_explain.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-auto_explain.md](../../../subsystems/contrib-auto_explain.md)
