# `src/backend/utils/misc/help_config.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~120
- **Source:** `source/src/backend/utils/misc/help_config.c`

Implements the `postgres --describe-config` startup mode: walks the
GUC table, filters out hidden/sample-only/disallowed entries, and
prints one tab-separated record per visible variable. Used by
documentation tooling (`doc/src/sgml/config.sgml` is partly generated
from this). [verified-by-code] [from-comment]

## API

- `GucInfoMain(void)` — entry point invoked from `main.c` when the
  postmaster is launched with the describe-config flag. Builds the
  GUC hash via `build_guc_variables()`, fetches the sorted array via
  `get_guc_variables(&numOpts)`, prints each via `printMixedStruct`,
  and `exit(0)`s. Never returns. [verified-by-code]

## Internals

- `displayStruct(var)` — returns true if `flags` has *none* of
  `GUC_NO_SHOW_ALL | GUC_NOT_IN_SAMPLE | GUC_DISALLOW_IN_FILE`. So
  variables intended only as command-line flags or for internal use
  are silently dropped from the listing. [verified-by-code]
- `printMixedStruct(var)` — prints `name<TAB>context<TAB>group<TAB>`
  then a type-discriminated trailer (BOOLEAN/INTEGER/REAL/STRING/ENUM
  with reset_val and min/max where applicable) then
  `short_desc<TAB>long_desc<\n>`. Descriptions go through `_()`
  (gettext). [verified-by-code]

## Notable invariants / details

- The output format is a stable contract used by external doc
  generators; changing column count or order would break those.
  No explicit format-version marker. [inferred] [ISSUE-undocumented-invariant:
  output format is stable interface but undocumented as such (nit)]
- `default` branch of the switch writes to stderr ("internal error:
  unrecognized run-time parameter type\n") and falls through without
  printing the trailer or newline — produces a malformed row that the
  preceding tab-separated header makes ambiguous. Shouldn't happen
  in practice (vartype is set by `DefineCustom*Variable`). [verified-by-code]
  [ISSUE-correctness: malformed output line on unknown vartype (nit)]
- Comment block above the function says "It will print out a
  different format, depending on what the user wants to see." — the
  current implementation has no "what the user wants" knob; the
  comment is stale. [verified-by-code] [ISSUE-stale-todo: comment
  references nonexistent user-mode switch (nit)]
- `boot_val` for STRING is dereferenced with a NULL check inline at
  line 103, but ENUM doesn't NULL-check `boot_val` — assumes every
  enum GUC has a default. Verified by inspection: `DefineCustomEnumVariable`
  requires non-null `bootValue`. [inferred]

## Potential issues

- File-line: help_config.c:113-114. `write_stderr` on unknown vartype
  doesn't `exit(1)` — describes-config returns 0 even after the
  error, which a script consuming stdout would treat as success.
  [ISSUE-correctness: misleading exit status on internal error (nit)]
- File-line: help_config.c:66-69. Stale comment about user-selectable
  output mode. [ISSUE-stale-todo: dead documentation (nit)]
