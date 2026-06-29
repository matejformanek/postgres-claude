# `contrib/pg_plan_advice/pg_plan_advice.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~457
- **Source:** `source/contrib/pg_plan_advice/pg_plan_advice.c`

Main entry points and `_PG_init` for the `pg_plan_advice` contrib module.
This is the public surface of an extension that implements a mini-language
("plan advice") for steering planner decisions — both round-trip generating
advice from a finished plan and enforcing advice during a subsequent planning
cycle. The file wires up five custom GUCs, registers the `EXPLAIN (PLAN_ADVICE)`
option via `RegisterExtensionExplainOption`, installs the
`explain_per_plan_hook`, and forwards planner-side hook installation to
`pgpa_planner_install_hooks()`. Heavy lifting lives in sibling files. [from-README] [verified-by-code]

## API / entry points

- `_PG_init` (line 64): module init. Defines GUCs `pg_plan_advice.advice`
  (string, parsed at SET time via `pg_plan_advice_advice_check_hook`),
  `always_explain_supplied_advice` (bool, default true), `always_store_advice_details`
  (bool, default false), `feedback_warnings` (bool), `trace_mask` (bool).
  Reserves the `pg_plan_advice.` GUC prefix, grabs an ExplainExtensionId, registers
  the `plan_advice` EXPLAIN option, installs planner hooks, and chains
  `explain_per_plan_hook`. [verified-by-code]
- `pg_plan_advice_get_mcxt` (line 143): lazily creates an `AllocSetContext`
  child of `TopMemoryContext` named "pg_plan_advice"; used to hold advisor-hook
  list across queries. [verified-by-code]
- `pg_plan_advice_should_explain` (line 157): returns whether
  `EXPLAIN (PLAN_ADVICE)` was specified and not set to false. Consults
  `GetExplainExtensionState(es, es_extension_id)`. [verified-by-code]
- `pg_plan_advice_get_supplied_query_advice` (line 170): public — runs registered
  advisor hooks in order, returning the first non-NULL string; falls back to the
  `pg_plan_advice.advice` GUC. [verified-by-code]
- `pg_plan_advice_add_advisor` / `pg_plan_advice_remove_advisor` (lines 205, 218):
  PGDLLEXPORT — allow other loadable modules to push per-query advice via a
  function pointer. [verified-by-code]
- `pg_plan_advice_request_advice_generation` (line 242): PGDLLEXPORT — increments
  a shared counter (`pgpa_planner_generate_advice`, lives in `pgpa_planner.c`)
  to force advice-string generation. Idempotent only via balanced calls.
  [verified-by-code]
- `pg_plan_advice_explain_option_handler` (line 257): EXPLAIN-option callback;
  stores the user-supplied bool on the ExplainState as extension state.
  [verified-by-code]
- `pg_plan_advice_explain_per_plan_hook` (line 344): chained after any previous
  `explain_per_plan_hook`. Pulls "feedback" and "advice_string" DefElems stashed
  in `plannedstmt->extension_state` by `pgpa_planner_shutdown` and renders them
  under the labels "Supplied Plan Advice" and "Generated Plan Advice".
  [verified-by-code]
- `pg_plan_advice_advice_check_hook` (line 413): GUC check hook — parses the
  candidate advice string into a temporary `AllocSet` context (then destroyed),
  reports parse errors via `GUC_check_errdetail`. The parse tree is thrown away
  because `*extra` is limited to a single `guc_malloc` chunk. [verified-by-code]

## Notable invariants / details

- The `pg_plan_advice` extension state stashed in `PlannedStmt->extension_state`
  is a `DefElem` with `defname = "pg_plan_advice"` whose arg is a `List` of
  child `DefElem`s. Children seen: `"advice_string"` (`String` node) and
  `"feedback"` (`List` of `DefElem`s, each mapping advice-text to integer flags).
  [verified-by-code]
- `pg_plan_advice_explain_text_multiline` (line 278) only does fancy per-line
  indentation when `es->format == EXPLAIN_FORMAT_TEXT`; non-text formats just go
  through `ExplainPropertyText`. The trailing newline is dropped instead of
  producing a blank line. [verified-by-code]
- `pg_plan_advice_advice_check_hook` does *not* reject empty strings — the
  empty-string case is handled later in `pgpa_planner_setup` (which guards with
  `supplied_advice[0] != '\0'`). [verified-by-code]
- The advice-string GUC's check hook intentionally re-parses every SET, even
  though parsing memory is discarded; documented inline that the parse tree
  cannot be passed through `*extra`. Plan advice strings are re-parsed at
  query-plan time too. [from-comment]
- Advisor hooks are kept in `advisor_hook_list` allocated in
  `pg_plan_advice_get_mcxt()` (lives across queries). `lappend`/`list_delete_ptr`
  are switched into the module memory context. [verified-by-code]

## Potential issues

- `pg_plan_advice.c:36` — `pg_plan_advice_always_explain_supplied_advice` is
  `static`; the `extern` declaration in the header is unused by this file.
  This is fine but the asymmetry with the other four GUCs (which are non-static
  and externally visible) is undocumented. [ISSUE-style: GUC-visibility asymmetry
  not noted in header (nit)]
- `pg_plan_advice.c:248` — `pg_plan_advice_request_advice_generation(false)`
  asserts `pgpa_planner_generate_advice > 0` then decrements. A misbalanced
  caller will trip an assert in cassert builds and silently underflow in release
  builds. Worth a `WARNING` instead, or at least an `elog(ERROR)`.
  [ISSUE-correctness: silent underflow on unbalanced advisor activate/revoke (maybe)]
- `pg_plan_advice.c:67-76` — the `advice` GUC has no `boot_val`; it defaults to
  NULL, which is handled by `get_supplied_query_advice`. [from-comment]
- `pg_plan_advice.c:182-190` — `advisor_hook_list` traversal: first hook to
  return non-NULL wins. There is no way for a later-registered hook to override
  an earlier one short of removing the earlier hook. This is documented in the
  function header. [from-comment]
- `pg_plan_advice.c:402` — `strVal(advice_string_item->arg)` assumes the arg is
  a `String` Node. Safe by construction (only `pgpa_planner_shutdown` writes this
  key) but undocumented invariant. [ISSUE-undocumented-invariant: extension_state
  shape contract is informal (nit)]
- `pg_plan_advice.c:65-136` — `_PG_init` does *not* check
  `process_shared_preload_libraries_in_progress`, nor does it call
  `MarkGUCPrefixReserved` before any of the `DefineCustom*` calls. The
  prefix reservation comes after the variable defines, which is fine but unusual.
  [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../subsystems/contrib-pg_plan_advice.md)
