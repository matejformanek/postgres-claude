# libpq-fs.h

- **Source path:** `source/src/include/libpq/libpq-fs.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions for using Inversion file system routines (ie, large objects)."
The minimal public header for the LO mode flags; named after the abandoned
"Inversion" filesystem ancestor of the LO subsystem [from-comment].

## Public API surface

- `INV_WRITE 0x00020000` — open LO for writing.
- `INV_READ 0x00040000` — open LO for reading.

These bit values are passed across the SQL/wire boundary to `lo_open()`
and friends; clients (psql `\lo_*`, `libpq` LO helpers, JDBC's `LargeObject`,
psycopg2's `lobject`) hardcode the same values. **Wire-protocol-equivalent
constants — changing them breaks every LO client.** The header does not
warn of this [verified-by-code].

## Cross-refs

- Related backend: `src/backend/libpq/be-fsstubs.c`,
  `src/backend/storage/large_object/inv_api.c`.
- Related: `knowledge/files/src/include/libpq/be-fsstubs.h.md`.
- Frontend: `src/interfaces/libpq/fe-lobj.c` (uses the same flag values).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: INV_READ/INV_WRITE are part of the LO ABI]**
  `libpq-fs.h:21-22` — the file has no "do not change" warning, yet these
  bit values cross process boundaries (SQL function arg into `lo_open(oid,
  mode)`) and are baked into every external LO client. The unusual bit
  positions (`0x00020000`, `0x00040000`) are themselves a historical
  artifact that nothing in the header explains. Severity: likely.

## Tally

`[verified-by-code]=2 [from-comment]=1 [inferred]=1`
