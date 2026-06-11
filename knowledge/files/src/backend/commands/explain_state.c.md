# `src/backend/commands/explain_state.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~498
- **Source:** `source/src/backend/commands/explain_state.c`

PG18+ split out of `explain.c`: builds and parses `ExplainState`.
Owns the core options list (`ANALYZE`, `VERBOSE`, `COSTS`, `BUFFERS`,
`WAL`, `SETTINGS`, `GENERIC_PLAN`, `TIMING`, `SUMMARY`, `MEMORY`,
`SERIALIZE`, `FORMAT`, `IO`) and the extension registration surface
that lets `pg_overexplain`, `pg_stat_statements`, etc. add their own
options like `(BICYCLE 'red')`. [from-comment, verified-by-code]

## API / entry points

- `NewExplainState(void)` — allocate + default-initialize. Default
  `costs=true`; output `StringInfo` ready. [verified-by-code]
- `ParseExplainOptionList(es, options, pstate)` — main parser. Walks
  the `List *` of `DefElem` and sets fields. Unknown names dispatch
  to `ApplyExtensionExplainOption`; only if that also returns false
  do we ereport syntax error. [verified-by-code]
- `GetExplainExtensionId(extension_name)` — extension acquires an
  integer ID for use with `GetExplainExtensionState`/
  `SetExplainExtensionState`. IDs stable within backend only.
  [from-comment]
- `GetExplainExtensionState(es, id)` / `SetExplainExtensionState(es,
  id, opaque)` — store/retrieve opaque per-extension data on the
  `ExplainState`. Backing array auto-expands using
  `pg_nextpower2_32`. [verified-by-code]
- `RegisterExtensionExplainOption(name, handler, guc_check_handler)` —
  register a new EXPLAIN option name with parser and GUC validator
  hooks. Re-registration overwrites. [from-comment]
- `ApplyExtensionExplainOption(es, opt, pstate)` — linear search for
  registered handler; returns false if not found. [verified-by-code]
- `GUCCheckExplainExtensionOption(name, value, type)` — used by GUC
  validation of `explain_options` defaults. [from-comment]
- `GUCCheckBooleanExplainOption(...)` — pre-built check handler for
  boolean options; matches `defGetBoolean` semantics exactly: NULL,
  `true/false/on/off`, or strict 0/1 (in various bases). [from-comment]

## Notable invariants / details

- `explain_validate_options_hook` (line 43) — public hook called at
  the end of `ParseExplainOptionList`; lets extensions perform
  cross-option validation that the per-option handlers can't.
  [verified-by-code]
- Extension registry is two separate arrays:
  `ExplainExtensionNameArray` (IDs/state slots) and
  `ExplainExtensionOptionArray` (option-name → handler). Distinct
  because an extension may register zero, one, or many options under
  one ID. [from-comment]
- Both arrays grow on demand from initial size 16 using
  `pg_nextpower2_32(needed+1)`; allocated in `TopMemoryContext`.
  [verified-by-code]
- Mutual-exclusion validation (lines 176-210):
  - `WAL`, `TIMING`, `IO`, `SERIALIZE` all require `ANALYZE`.
  - `GENERIC_PLAN` is incompatible with `ANALYZE`.
- `TIMING` and `BUFFERS` and `SUMMARY` default to the value of
  `ANALYZE` if not explicitly set (lines 182-185, 213).
- `SERIALIZE` without arg defaults to `text` (lines 140-144); explicit
  values are `off`/`none`/`text`/`binary`.
- Option strings are case-sensitive in the C code path (`strcmp`
  through `opt->defname` which already arrived lowercased from gram.y).
  [inferred]

## Potential issues

- Lines 182-185. Auto-enabling `buffers` (and `timing`) when `analyze`
  is set silently increases ANALYZE's measurement overhead. User-doc
  drift risk if defaults change. [ISSUE-undocumented-invariant:
  analyze-default cascade (nit)]
- Linear `for` loops over registered options (line 235-237, 342-353,
  391-399, 417-428). Fine while N is small; if a future extension
  registers hundreds of options, becomes O(N) per parse. Probably
  never an issue. [unverified]
- `RegisterExtensionExplainOption` re-registration silently
  overwrites the handler (lines 342-353). No warning. Could mask a
  conflict between two extensions that both want `BICYCLE`.

## Synthesized by
<!-- backlinks:auto -->
