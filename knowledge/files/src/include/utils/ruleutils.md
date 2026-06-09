# `src/include/utils/ruleutils.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

C-callable entry points into the deparse machinery in
`backend/utils/adt/ruleutils.c`. Used by EXPLAIN, pg_dump, and
catalog SRFs to convert internal parse trees / index defs / partition
defs / constraint defs back to SQL text.

**Header-level finding (A7 cross-link):** `pg_get_viewdef` and most
other `pg_get_*` SQL-callable functions are *not* declared here —
they are PG_FUNCTION_INFO_V1 entry points inside `ruleutils.c`,
exported only via `pg_proc.dat`. This header exposes only the
C-callable helpers used by the rest of the backend (mostly EXPLAIN
and pg_dump support functions).

## Public API

### Pretty-print flags [verified-by-code: lines 24-25]

```c
#define RULE_INDEXDEF_PRETTY     0x01
#define RULE_INDEXDEF_KEYS_ONLY  0x02   /* ignore included attributes */
```

### Functions [verified-by-code: lines 27-56]

- `pg_get_indexdef_string(indexrelid)` — single-line form for
  CREATE INDEX (used by pg_dump).
- `pg_get_indexdef_columns(indexrelid, pretty)`,
  `pg_get_indexdef_columns_extended(indexrelid, flags)`.
- `pg_get_querydef(Query *query, pretty)` — deparse an internal
  Query.
- `pg_get_partkeydef_columns(relid, pretty)`,
  `pg_get_partconstrdef_string(partitionId, aliasname)`.
- `pg_get_constraintdef_command(constraintId)`.
- `deparse_expression(expr, dpcontext, forceprefix, showimplicit)`
  — the core single-expression deparser.
- `deparse_context_for(aliasname, relid)`,
  `deparse_context_for_plan_tree(pstmt, rtable_names)`,
  `set_deparse_context_plan(dpcontext, plan, ancestors)`,
  `select_rtable_names_for_explain(rtable, rels_used)` — used by
  EXPLAIN.
- `get_window_frame_options_for_explain(...)`.
- `generate_collation_name(collid)`, `generate_opclass_name(opclass)`.
- `get_range_partbound_string(bound_datums)`.
- `get_reloptions(StringInfo, Datum reloptions)` — appends WITH (..)
  form.
- `pg_get_statisticsobjdef_string(statextid)`.

## Invariants

- **INV-NO-PUBLIC** [verified-by-code: full file] No SQL-callable
  `pg_get_*` symbol is declared here; they're discovered by fmgr via
  `pg_proc.dat` only. This is deliberate — the deparse functions
  exposed here are *C-callers'* API, not the SQL API.

## Trust boundary (Phase D — A7 cross-finding)

This header is part of the A7 "view re-emission gap" finding. The
gap is in `ruleutils.c`'s `pg_get_viewdef_*` family, not in this
header — but the header-level observation is that:

- `get_reloptions(buf, reloptions)` exists and is exposed; in
  principle it could be called by `pg_get_viewdef` to re-emit the
  WITH (security_barrier, security_invoker, check_option) clause
  of a view's `pg_class.reloptions`. The omission is a `.c`-level
  policy decision; the header machinery is there.
- `pg_get_constraintdef_command(constraintId)` is used by pg_dump
  for FKs / CHECK constraints; same surface as `pg_get_viewdef`.
- `deparse_expression` runs over arbitrary node trees from catalogs
  (defaults, CHECK quals, partition bounds). A malformed
  `pg_node_tree` in the catalog (only writable by superuser) can
  crash the deparser — same posture as `rel.h` `rd_indpred`.

## Cross-refs

- `backend/utils/adt/ruleutils.c` — implementation, including the
  SQL-callable `pg_get_viewdef`, `pg_get_ruledef`,
  `pg_get_triggerdef`, `pg_get_functiondef` etc.
- `utils/rel.h` — view options (`ViewOptions`) that *should* be
  re-emitted.
- A7 finding (corpus: `pg_get_viewdef` omits security clauses).

## Issues

- [ISSUE-PHASE-D-A7: header exposes `get_reloptions(buf, Datum)`
  but no `pg_get_viewdef`-equivalent that calls it; the SQL-level
  `pg_get_viewdef` (declared only in pg_proc.dat, defined in
  ruleutils.c) does NOT re-emit `WITH (security_barrier, …)` —
  pg_dump rescues itself by reading pg_class.reloptions directly,
  but SQL users invoking `pg_get_viewdef()` get a view definition
  that loses security clauses (high)] — line 54 (`get_reloptions`).
- [ISSUE-API: the boundary between "C-callable helpers here" and
  "SQL-callable pg_get_* in ruleutils.c" is invisible; new
  contributors easily believe `pg_get_viewdef` is declared
  somewhere in headers (low)] — full file.
