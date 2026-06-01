# `src/backend/utils/adt/oid.c`

- **File:** `source/src/backend/utils/adt/oid.c` (418 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The `oid` scalar type and the `oidvector` array-like helper used by
system catalogs (e.g. `pg_proc.proargtypes`, `pg_index.indkey`).
Provides I/O, comparison, and the small handful of operators registered
for them.

## Top of file (verbatim)

```
 * oid.c
 *    Functions for the built-in type Oid ... also oidvector.
```
(`:1-13` [from-comment])

## Public surface

- **oid I/O:** `oidin` (`:35`), `oidout` (`:43`), `oidrecv` (`:60`),
  `oidsend` (`:71`). I/O delegates to `uint32in_subr`
  (`common/int.c`) — `oid` is wire-equivalent to `uint32`.
- **oid comparison:** `oideq/ne/lt/le/gt/ge` (`PG_FUNCTION_INFO_V1`
  blocks throughout), `oidlarger`/`oidsmaller`.
- **oidvector I/O:** `oidvectorin` (`:138`), `oidvectorout` (`:182`),
  `oidvectorrecv` (`:209`), `oidvectorsend`. The
  `buildoidvector(oids, n)` (`:87`) and
  `check_valid_oidvector` (`:118`) helpers are extern, used by
  catalog code that synthesizes oidvectors directly.
- **oidvector comparison:** `oidvectoreq/ne/lt/le/gt/ge` —
  element-wise.
- **oidparse** (`:~370`) — converts a `parser/value.h` `Value` node
  to Oid; used by GUC parsing.

## Key invariants

- **`Oid` is `uint32`.** No SQL null distinction inside the value
  domain; the *catalog convention* is that OID 0 means "unassigned"
  (`[inferred]`, see e.g. `InvalidOid`).
- **`oidvector` has lower-bound 0, not 1.** Unlike a regular int[]
  array (`:96-98` [verified-by-code]: "For historical reasons, we
  set the index lower bound to 0 not 1."). Must be remembered when
  indexing from SQL.
- **`oidvector` cannot contain nulls.** `dataoffset == 0` is
  enforced and `check_valid_oidvector` rejects any oid[] cast that
  would violate this (`:120-131` [verified-by-code]). This is the
  reason there's a separate type at all rather than reusing oid[].
- **`oidvector` is always 1-dimensional.** Enforced same check.

## Functions of note

- **`uint32in_subr`** (called by `oidin` and `oidvectorin`, defined
  in `src/common/int.c`) — handles soft-error reporting via
  `escontext`; rejects negative literals and detects overflow. This
  is why `'-1'::oid` errors rather than wrapping to MAXUINT.
- **`oidparse`** — accepts `T_Integer` and `T_Float` Value nodes
  (the latter to handle OIDs that bison parsed as float because they
  exceed INT_MAX), and rejects anything else.
- **`oidvectoreq`** — used by syscache lookups (especially the
  `PROCOID` / `PROCNAMEARGSNSP` caches) to match argument-type
  signatures; performance-critical.

## Cross-references

- `source/src/include/c.h` / `source/src/include/postgres_ext.h` —
  `Oid` typedef and `InvalidOid`.
- `source/src/backend/utils/cache/syscache.c` — biggest consumer
  of `oidvectoreq`.
- `source/src/common/int.c` — `uint32in_subr`.

## Open questions

- `oidvectorsend` wire format is `n × int32` with no element count
  header (count comes from varlena length); cross-version
  compatibility is implicit. `[inferred]`

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 1
- `[inferred]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
