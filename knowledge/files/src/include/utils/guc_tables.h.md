# `utils/guc_tables.h` — config_generic and per-type GUC records

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/guc_tables.h`)

## Role

Defines the in-memory layout of a GUC variable: `config_generic` (header
fields common to all types) plus an anonymous-union per-type record
(`config_bool` / `config_int` / `config_real` / `config_string` /
`config_enum`). Also defines `config_group` (the SHOW-grouping enum used
in `pg_settings.category`) and `GucStack` (the per-nesting-level undo
record for SET / SET LOCAL inside a transaction).

## Public API

- `enum config_type { PGC_BOOL, PGC_INT, PGC_REAL, PGC_STRING, PGC_ENUM }`
  — `source/src/include/utils/guc_tables.h:23-30`.
- `union config_var_val { boolval, intval, realval, stringval, enumval }`
  — `:32-39`.
- `typedef struct config_var_value { val, extra }` — `:45-49`.
- `enum config_group` — `:55-106`. 50+ entries grouping GUCs for SHOW.
  Notable: `DEVELOPER_OPTIONS`, `PRESET_OPTIONS`, `CUSTOM_OPTIONS`,
  `ERROR_HANDLING_OPTIONS`, plus connection/replication/vacuum/etc. buckets.
- `enum GucStackState { GUC_SAVE, GUC_SET, GUC_LOCAL, GUC_SET_LOCAL }` —
  `:112-119`. Four states because SET-then-SET-LOCAL needs to remember
  both values.
- `struct guc_stack { prev, nest_level, state, source, scontext,
  masked_scontext, srole, masked_srole, prior, masked }` — `:121-134`.
- `struct config_bool/int/real/string/enum { variable, boot_val, ...,
  check_hook, assign_hook, show_hook, reset_val }` — `:139-212`.
- `struct config_generic { name, context, group, short_desc, long_desc,
  flags, vartype, status, source, reset_source, scontext, reset_scontext,
  srole, reset_srole, stack, extra, reset_extra, nondef_link, stack_link,
  report_link, last_reported, sourcefile, sourceline, [union of
  per-type structs] }` — `:250-292`.
- Status bits `GUC_IS_IN_FILE`, `GUC_PENDING_RESTART`, `GUC_NEEDS_REPORT`
  — `:295-301`.
- Lookups: `find_option`, `get_explain_guc_options`, `ShowGUCOption`,
  `ConfigOptionIsVisible`, `get_guc_variables`, `build_guc_variables`,
  `config_enum_lookup_by_value/by_name`, `config_enum_get_options` —
  `:314-338`.
- `ConfigureNames[]` exported as `PGDLLIMPORT struct config_generic` —
  `:311`. The actual built-in GUC array.

## Invariants

- `config_var_value.extra` is a `void *` that, if non-NULL, was malloc'd
  by a check hook. PG manages its lifetime tied to the value being
  active. [from-comment, `:42-44`]
- `boot_val` for strings is allowed to be NULL → reset_val and variable
  are NULL too, but **no API can later set NULL**; SHOW renders NULL as
  empty string. Callers using a NULL boot_val must overwrite during
  startup OR accept that NULL behaves like "". [from-comment, `:179-188`]
- `srole == BOOTSTRAP_SUPERUSERID` is the marker for "value came from
  internal source / config file". [from-comment, `:236-238`]
- `sourcefile` / `sourceline` are populated only when `source == PGC_S_FILE`;
  they live on `config_generic`, not on stacked values, to avoid bloating
  stack entries. [from-comment, `:245-249`]
- `nondef_link` / `stack_link` / `report_link` use `dlist_node` /
  `slist_node` linkages from `lib/ilist.h` to make lookups O(1)
  for the "GUCs with non-default value", "GUCs with stack", "GUCs needing
  client report" passes. [verified-by-code, `:271-275`]
- `GUC_IS_IN_FILE` is transient — only valid during `ProcessConfigFile`.
  Don't read it elsewhere. [from-comment, `:295-299`]
- `GucStackState`: `GUC_SET_LOCAL` is "SET followed by SET LOCAL in same
  txn" — needs both the prior value AND the masked value so SET LOCAL
  can be popped on subtxn end while keeping the SET that's still
  conceptually active. [from-comment, `:113-118`]
- `last_reported` is the value last sent to the client via the GUC_REPORT
  mechanism, or NULL if not yet sent. [from-comment, `:277-278`]

## Notable internals

- `struct config_generic` is the on-disk-stable layout? NO — explicitly
  not on-disk. `pg_settings` is a view computed from this in-memory table.
  Add a field freely. [verified-by-comment in guc.h `:212-213`]
- The `union` at `:284-291` is the discriminated body — `vartype` field
  says which member is active. Extensions add custom variables by
  allocating their own `config_bool` / etc. and pointing at them via
  `DefineCustomBoolVariable`.
- The `extra` malloc'd by a check hook is the canonical channel for a
  check hook to pass "preprocessed form" data to its assign hook (e.g.,
  parsed regex, looked-up OID). The lifetime is tied to the value being
  active in the GUC variable; PG frees old `extra` after a successful
  assign.

## Trust-boundary / Phase D surface

- `extra` is `void *` — a check hook can stash arbitrary state. If the
  assign hook reads `extra` without the discipline of "match the check
  hook's struct layout", you get type-confusion. No header-level
  protection. [ISSUE-correctness: `config_var_value.extra` is an
  untyped void* shared between check and assign hooks; nothing enforces
  layout agreement (maybe)]
- `ConfigureNames[]` is exported `PGDLLIMPORT` and **NOT const** —
  extensions can in principle mutate the built-in GUC table at runtime
  (changing flags, check hooks). Defence-in-depth would mark it const.
  [ISSUE-defense-in-depth: ConfigureNames[] is mutable PGDLLIMPORT (nit)]
- `srole == BOOTSTRAP_SUPERUSERID` is used both as a sentinel ("internal
  source") and as a real role (the bootstrap superuser). Callers that
  want to distinguish "user-set by bootstrap superuser" from "internal
  default" must also examine `source`. [ISSUE-api-shape:
  BOOTSTRAP_SUPERUSERID is both a sentinel and a real role (nit)]
- `GUC_NEEDS_REPORT` status bit + `report_link` slist mean every GUC
  marked `GUC_REPORT` adds to per-transaction reporting overhead — a
  malicious extension that adds 1000 GUC_REPORT GUCs would flood every
  connection's startup ReadyForQuery. [ISSUE-resource: extensions can
  add unbounded GUC_REPORT vars, each costing per-txn reporting work
  (nit)]
- `find_option(name, create_placeholders=true, ...)` (`:314`) lazily
  creates placeholders for `foo.bar` unknown GUCs — this is how
  extension GUCs survive being SET before the extension is loaded. An
  attacker can SET a placeholder, then convince another session to load
  the extension and see the value applied as a real GUC. Mitigated by
  `MarkGUCPrefixReserved`, but only if the extension calls it.
  [ISSUE-correctness: placeholder GUC propagation across extension-load
  boundary requires MarkGUCPrefixReserved discipline (maybe)]
- `GucStack` chain depth is bounded only by transaction nesting depth;
  pathological savepoints could push large stacks per variable.
  [ISSUE-resource: GucStack depth unbounded in this header (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/guc.h.md` — public API consumers
  of this layout.
- `knowledge/files/src/include/utils/guc_hooks.h.md` — declarations of
  the check/assign/show function pointers stored in these structs.
- `source/src/backend/utils/misc/README` — design notes (referenced
  at `:6`).

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-correctness: `config_var_value.extra` is untyped void*; no
   layout agreement between check and assign hook (maybe)] —
   `source/src/include/utils/guc_tables.h:42-49`.
2. [ISSUE-defense-in-depth: `ConfigureNames[]` is mutable PGDLLIMPORT;
   extensions can mutate flags / hooks (nit)] —
   `source/src/include/utils/guc_tables.h:311`.
3. [ISSUE-api-shape: `BOOTSTRAP_SUPERUSERID` doubles as a sentinel and a
   real role; distinguishing requires examining `source` (nit)] —
   `source/src/include/utils/guc_tables.h:236-238`.
4. [ISSUE-resource: extensions can add unbounded `GUC_REPORT` vars
   causing per-txn reporting overhead (nit)] —
   `source/src/include/utils/guc_tables.h:275-278`.
5. [ISSUE-correctness: placeholder GUCs across extension-load boundary
   require `MarkGUCPrefixReserved` discipline (maybe)] —
   `source/src/include/utils/guc_tables.h:314`.
6. [ISSUE-resource: `GucStack` chain depth unbounded (nit)] —
   `source/src/include/utils/guc_tables.h:121-134`.
