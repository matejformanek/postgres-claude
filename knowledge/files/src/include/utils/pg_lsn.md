# utils/pg_lsn.h — LSN type Datum wrappers

Source: `source/src/include/utils/pg_lsn.h` (41 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Datum-layer wrappers for `XLogRecPtr` (the WAL pointer) as a SQL-visible type (`pg_lsn`).

## Public API

- `DatumGetLSN` / `LSNGetDatum` (`pg_lsn.h:24-34`).
- `PG_GETARG_LSN` / `PG_RETURN_LSN` (`pg_lsn.h:36-37`).
- `pg_lsn_in_safe(str, escontext)` (`pg_lsn.h:39`) — soft-error parse.

## Invariants

- **INV-XLogRecPtr-is-int64** [verified-by-code, `pg_lsn.h:24-28`]: `DatumGetLSN` casts via `DatumGetInt64`. LSN is unsigned but Datum-as-int64 is fine since the encoding is bit-equivalent.
- **INV-zero-is-InvalidXLogRecPtr** [inferred from xlogdefs.h]: LSN 0/0 is the "not set" sentinel; comparisons treat it as less-than everything.

## Trust-boundary / Phase-D surface

- **`pg_lsn_in_safe` is the recv/parse path** — old `pg_lsn_in` (ereport-on-error) should not be reached from user input parse paths.

## Cross-refs

- `source/src/include/access/xlogdefs.h` — `XLogRecPtr`, `InvalidXLogRecPtr`.
- `source/src/backend/utils/adt/pg_lsn.c` — implementation.

## Issues

- None — header is a thin datum bridge.
