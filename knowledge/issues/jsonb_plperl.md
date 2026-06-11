# Issues — `contrib/jsonb_plperl`

Per-subsystem issue register for **jsonb_plperl**, the jsonb ↔ Perl
scalar/array/hash transform extension. Single-file extension, ~309 LOC.

**Parent docs:** `knowledge/files/contrib/jsonb_plperl/jsonb_plperl.c.md`

**Source:** sweep A21-D, 2026-06-11.

## Headlines

1. **Boolean round-trip is lossy.** jsonb `true`/`false` → Perl 1.0/0.0
   (float, via `SvNV` of immortal SV) → on return becomes jsonb
   numeric `1`/`0`, not jbvBool. Documented behaviour, but easy to
   trip over; Perl lacks a native boolean.

2. **Numeric round-trip lifts through Perl float.** `numeric_out` →
   cstring → `cstr2sv` → `SvNV` → `newSVnv`. PG `numeric` values
   outside IEEE 754 double range silently truncate.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | jsonb_plperl.c:49-50 | correctness | maybe | jsonb bool → Perl float (not Perl bool); round-trip silently changes type to numeric | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |
| 2026-06-11 | jsonb_plperl.c:29-37 | correctness | nit | Numeric round-trip through Perl `SvNV` loses precision for large/precise PG numerics | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |
| 2026-06-11 | jsonb_plperl.c:33,50 | leak | nit | `cstr2sv` intermediate SVs leak per scalar conversion into Perl arena (bounded by interpreter lifetime) | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |
| 2026-06-11 | jsonb_plperl.c (whole file) | leak | nit | No PG_TRY around recursive SV traversal; ereport mid-recursion leaks intermediate SVs into Perl arena | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |
| 2026-06-11 | jsonb_plperl.c:209-216 | correctness | nit | UV → text → numeric path inherits `numeric_in` errors; user sees generic "invalid input syntax for numeric" rather than UV-range hint | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |
| 2026-06-11 | jsonb_plperl.c:257-261 | stale-todo | nit | `XXX` comment requesting better error detail (Perl type name in error message); comment-only since at least PG 11 | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |
| 2026-06-11 | jsonb_plperl.c:267-281 | style | nit | Top-level (palloc result) vs nested (stack JsonbValue + copy via pushJsonbValue) allocation asymmetry warrants a comment | open | files/contrib/jsonb_plperl/jsonb_plperl.c.md |

## Notes

Larger than hstore_plperl because jsonb has recursive structure +
four scalar types, vs hstore's flat string→string map. No
`_PG_init` is needed because the bridge calls only core symbols
(jsonb infrastructure + numeric I/O); contrast with hstore_plperl
which must `load_external_function` from the hstore module.

Trusted/untrusted: this extension installs only for `plperl`; the
parallel `jsonb_plperlu` packages the same `.so` for untrusted Perl.
