# `src/backend/utils/adt/pseudotypes.c`

- **File:** `source/src/backend/utils/adt/pseudotypes.c` (377 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

I/O functions for the **system pseudo-types** — `anyelement`, `internal`,
`trigger`, `void`, `cstring`, `pg_node_tree`, etc. A pseudo-type isn't
really a type and never has any operations of its own, but `pg_type`
still requires non-NULL `typinput`/`typoutput`. This file provides
mostly-dummy entry points that `ereport(ERROR, "cannot accept/display a
value of type X")` when invoked. (`pseudotypes.c:1-12` [from-comment])

## Macros

- `PSEUDOTYPE_DUMMY_INPUT_FUNC(typname)` (`:34`) — generates
  `typname##_in` that errors.
- `PSEUDOTYPE_DUMMY_IO_FUNCS(typname)` (`:47`) — both in + out.
- `PSEUDOTYPE_DUMMY_RECEIVE_FUNC` (`:68`), `..._BINARY_IO_FUNCS` (`:81`).
- All four emit `ERRCODE_FEATURE_NOT_SUPPORTED`.

## Real I/O kept for some pseudo-types

- **`cstring`** — full working I/O (`:106-142`). Marked pseudo only to
  keep users from declaring columns of it; functionally it's a
  perfectly fine type, and `cstring_in/out/recv/send` are used for
  manual `foo_in('blah')` invocations.
- **`anyarray`** — input rejected, but `anyarray_out` delegates to
  `array_out` (`:158-167`) so that `pg_statistic` columns of type
  anyarray can be displayed. Similarly `anyenum_out → enum_out`,
  `anyrange_out → range_out`, `anymultirange_out → multirange_out`, and
  the `anycompatible*` variants (`:194-251`).
- **`void`** (`:262-292`) — `void_in` returns void (lets PLs return
  VOID without special-casing), `void_out` returns `""`, `void_send`
  writes an empty bytea.
- **`shell`** (`:302-320`) — dummy IO for shell types (pg_type rows
  that haven't been filled in yet).
- **`pg_node_tree`** (`:334-347`) — input rejected (comment: "the SQL
  functions that operate on the type are not secure against malformed
  input" `:330-332`); `pg_node_tree_out → textout`.
- **`pg_ddl_command`** (`:358-359`) — fully dummy in both directions.

## Phase D notes

- The comment at `pseudotypes.c:330-332` is a **load-bearing security
  claim**: `pg_node_tree_in` is disallowed because downstream consumers
  of a `pg_node_tree` Datum trust the structure. Allowing user input
  would expose `stringToNode()` to attacker-controlled trees, which the
  parser is not hardened against. This is the documented reason that
  `pg_rewrite.ev_action` etc. can be read but not written by SQL.
- All the dummy `*_in` paths `ereport(ERROR, …)` immediately, so they
  cannot be used to smuggle untrusted bytes in.

## Potential issues

- [ISSUE-undocumented-invariant: `cstring_recv` (`:122-131`) accepts
  arbitrary bytes (via `pq_getmsgtext`) as a C string. Since cstring is
  marked pseudo and not usable as a table column, the surface is the
  binary protocol wire path; pq_getmsgtext should already enforce
  encoding validity. (maybe)]
- [ISSUE-stale-todo: XXX at `:11`: "the error messages here cover the
  most common case, but might be confusing in some contexts" — open
  for years (maybe)]
- [ISSUE-undocumented-invariant: `anyarray_recv` is dummy; comment at
  `:148-152` notes "could actually be made to work" but is intentionally
  left disabled for type-safety (maybe)]

## Cross-references

- `source/src/backend/utils/adt/arrayfuncs.c` — `array_out`, `array_send`.
- `source/src/backend/nodes/read.c` — `stringToNode`, the function
  whose hardening status is the reason for `pg_node_tree_in` rejection.
- `source/src/include/catalog/pg_type.dat` — pseudo-type entries
  pointing at these functions.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 3
