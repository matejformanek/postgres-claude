# src/include/commands/copyapi.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 105 [verified-by-code]

## Role

Extension API for pluggable COPY TO/FROM **formats**. Pre-PG16 only `text`,
`csv`, `binary` were built in; this header exposes the callback structs that a
custom format (or a contrib like a JSON/Parquet COPY) implements.

## Public API

- `CopyToRoutine` — four callbacks: `CopyToOutFunc`, `CopyToStart`,
  `CopyToOneRow`, `CopyToEnd`. Server-lifetime-allocated, typically
  `static const`. (`copyapi.h:23-55` [verified-by-code])
- `CopyFromRoutine` — four callbacks: `CopyFromInFunc`, `CopyFromStart`,
  `CopyFromOneRow`, `CopyFromEnd`. (`copyapi.h:61-103` [verified-by-code])
- `CopyFromOneRow` returns `bool` (false = EOF) and fills `Datum *values` /
  `bool *nulls`. (`copyapi.h:96-97` [verified-by-code])

## Invariants

- INV-COPYAPI-STATIC: routine struct **must** be server-lifetime allocated
  (header comment line 21 [from-comment]). A per-query allocation would dangle
  across multi-stmt COPY usage.
- The format implementation registers via `pg_proc` SQL handler returning
  `internal` (parallel to `subscripting_function` pattern in `subscripting.h`).
- IN-func and OUT-func `FmgrInfo` is filled by the format if it overrides the
  per-attribute I/O function; otherwise core falls back to type I/O.

## Trust boundary / Phase D surface

- **A14 echo (COPY = privileged file I/O).** `COPY ... FROM '/path'` is gated
  by `pg_read_server_files`; `COPY ... PROGRAM` by superuser. The format
  callbacks here are pure data transform — they DO NOT cross the file/program
  trust boundary themselves. But a buggy/malicious format extension loaded via
  `shared_preload_libraries` could leak file contents through `OneRow`
  callbacks, or interpret bytes from a `PROGRAM` source unsafely.
- **No bounds checking in the API contract.** `CopyFromOneRow` receives
  arbitrary input bytes; format implementer is responsible for length /
  encoding validation before producing Datums. A buggy format could synthesize
  Datums that bypass varlena length sanity checks elsewhere in the backend.
- **PG18 new attack surface.** Extension custom formats can run inside a
  non-superuser COPY (e.g. `COPY t FROM STDIN WITH (FORMAT myfmt)`); auditing
  needs to follow each format's callback closure.

## Notable internals

- The `_strict` / `_leakproof` flags of `subscripting.h` have no analogue here
  — COPY formats are not invoked from expression contexts.
- `econtext` may be NULL for `CopyFromOneRow` if no DEFAULT columns are in play
  (`copyapi.h:90-94` [verified-by-code]); format must NOT dereference it
  blindly.

## Cross-references

- `commands/copy.h` — `CopyToState` / `CopyFromState` opaque structs whose
  pointers thread through every callback.
- `commands/copyfrom_internal.h` — internal state used by core `text`/`csv`
  format implementations.
- `commands/progress.h` — `PROGRESS_COPY_*` constants the format may want to
  advance via `pgstat_progress_update_param`.

## Issues / drift

- `[ISSUE-DOC: comment block on CopyFromOneRow has typo "use the DEFAULT option of COPY FROM" reads OK but indentation of econtext desc could be clearer (low)] — source/src/include/commands/copyapi.h:88-94`
- `[ISSUE-TRUST: header lacks an explicit warning that a format extension runs with backend privilege; trust contract is in commit log not header (low)] — source/src/include/commands/copyapi.h:19-22`
