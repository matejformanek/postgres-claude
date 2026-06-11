# `src/backend/utils/misc/guc_internal.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~26
- **Source:** `source/src/backend/utils/misc/guc_internal.h`

Header private to the GUC implementation in
`src/backend/utils/misc/`. Declares three symbols shared between
`guc.c`/`guc-file.l`/`guc_funcs.c` (and the auto-generated lex output)
that are not part of the public `utils/guc.h` API. [verified-by-code]
[from-comment]

## Declarations

- `guc_name_compare(const char *namea, const char *nameb)` —
  case-insensitive name comparison used by the GUC hash table and
  qsort comparator. Definition in `guc.c`. [verified-by-code]
- `ProcessConfigFileInternal(GucContext context, bool applySettings,
  int elevel)` — the workhorse that reads `postgresql.conf` (after
  `guc-file.l`'s lexer has tokenised it) and either reports parse
  errors at `elevel` or applies the parsed values to the running
  GUCs. Called from `ProcessConfigFile` and from the postmaster
  startup path. [verified-by-code]
- `record_config_file_error(errmsg, config_file, lineno, head_p,
  tail_p)` — append-style error logging used by the lexer to chain
  per-line errors onto a linked list so the caller can decide to
  report many lines at once. [verified-by-code]

## Notable invariants / details

- The header is intentionally tiny: anything not used by
  `guc-file.l` belongs in `guc.c` `static`. The split exists because
  the lexer output is a separate translation unit. [inferred]
- `ConfigVariable` (the linked-list node type) is forward-declared via
  `utils/guc.h`. [verified-by-code]
- No issue tags — pure declaration header. [verified-by-code]
