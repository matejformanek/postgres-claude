# `src/include/postgres.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~576
- **Source:** `source/src/include/postgres.h`

The primary include for every PostgreSQL **backend** .c file — the
counterpart to `postgres_fe.h` for frontend code. Re-exports `c.h`,
`utils/elog.h`, and `utils/palloc.h` (the three things every backend
needs), and adds backend-only declarations whose representations
"never escape the backend" — primarily `Datum` plus the
DatumGet*/`*GetDatum` conversion functions. [verified-by-code]

The TOC splits the file into (1) Datum type + support functions and
(2) miscellaneous (`pg_ternary`, `NON_EXEC_STATIC`). [from-comment]

## API / declarations

### Section 1 — Datum + GetDatum/DatumGet conversions

- `typedef uint64_t Datum` (`postgres.h:70`). Always 8 bytes — the
  comment at `postgres.h:60-65` says "standardizing on Datum being
  exactly 8 bytes has advantages in reducing cross-platform
  differences". [from-comment]
- `#define SIZEOF_DATUM 8` (`postgres.h:76`) — explicitly vestigial,
  kept for extension code. [from-comment]
- `NullableDatum { Datum value; bool isnull; }` (`postgres.h:84-91`) —
  with `FIELDNO_NULLABLE_DATUM_DATUM` / `FIELDNO_NULLABLE_DATUM_ISNULL`
  exposed for JIT field-offset lookups. Comment notes the padding
  byte could be used for flags. [from-comment]
- Conversion functions, all `static inline` (`postgres.h:99-525`):
  - `DatumGetBool` / `BoolGetDatum` — non-zero is true.
  - `DatumGetChar` / `CharGetDatum`.
  - `DatumGetUInt8` / `UInt8GetDatum`.
  - `DatumGetInt16` / `Int16GetDatum`; `DatumGetUInt16` /
    `UInt16GetDatum`.
  - `DatumGetInt32` / `Int32GetDatum`; `DatumGetUInt32` /
    `UInt32GetDatum`.
  - `DatumGetObjectId` / `ObjectIdGetDatum`.
  - `DatumGetObjectId8` / `ObjectId8GetDatum` — 8-byte OID family.
  - `DatumGetTransactionId` / `TransactionIdGetDatum`,
    `MultiXactIdGetDatum`, `DatumGetCommandId` / `CommandIdGetDatum`.
  - `DatumGetPointer` / `PointerGetDatum`. The latter is a MACRO
    (`postgres.h:354`) using `true ? (X) : NULL` to force pointer
    type-checking, plus the load-bearing comment at `postgres.h:340-351`
    explaining why this isn't `static inline Datum
    PointerGetDatum(const void *X)` — the compiler would assume
    constness through Datum round-trip.
  - `DatumGetCString` / `CStringGetDatum` — C-string passthrough; note
    "CString is pass-by-reference; caller must ensure the pointed-to
    value has adequate lifetime" (`postgres.h:378-380`).
  - `DatumGetName` / `NameGetDatum`.
  - `DatumGetInt64` / `Int64GetDatum`, `DatumGetUInt64` /
    `UInt64GetDatum`.
  - `DatumGetFloat4` / `Float4GetDatum`, `DatumGetFloat8` /
    `Float8GetDatum` — implemented as inline functions, not macros,
    using union-trick to avoid the int-vs-float register split on
    some ABIs (`postgres.h:451-457`).
- `Int64GetDatumFast(X)` / `Float8GetDatumFast(X)` (`postgres.h:538-541`)
  — wrap regular `*GetDatum` with `StaticAssertVariableIsOfTypeMacro`.
  Comment at `postgres.h:528-536` says they "are no longer different
  from the regular functions, though we keep the assertions to protect
  code that might get back-patched into older branches." [from-comment]

### Section 2 — miscellaneous

- `pg_ternary { PG_TERNARY_FALSE=0, PG_TERNARY_TRUE=1, PG_TERNARY_UNSET=-1 }`
  (`postgres.h:556-561`).
- `NON_EXEC_STATIC` (`postgres.h:570-574`) — `static` normally,
  `extern` under `EXEC_BACKEND`. Used by postmaster.c to transfer
  state between processes on Windows / forced EXEC_BACKEND builds.
  [from-comment]

## Notable invariants / details

- `sizeof(Datum) >= sizeof(void *)` is the foundation of the entire
  pass-by-value/pass-by-reference machinery (`postgres.h:62-64`). On
  hypothetical >8-byte-pointer systems PG would not compile;
  `Datum` is hard-coded as `uint64_t`. [verified-by-code]
- `BoolGetDatum` clamps to `0`/`1` (`postgres.h:114`), but
  `DatumGetBool` accepts any non-zero (`postgres.h:102`). Asymmetry is
  intentional and noted in the comment.
  [ISSUE-undocumented-invariant: callers that round-trip
  `BoolGetDatum(DatumGetBool(x))` lose the "any nonzero" property; a
  custom Datum holding `0x42` becomes `0x01` (nit)]
- `PointerGetDatum` is a MACRO (only one in the family) precisely so
  that the `true ? (X) : NULL` type-check fires at the call site.
  Converting to inline would silently strip the check. [from-comment]
  [ISSUE-undocumented-invariant: PointerGetDatum-macro contract not
  flagged at the alternative inline-function-form rejected at
  `postgres.h:340-351` (nit)]
- `Float4GetDatum`/`Float8GetDatum` union trick (`postgres.h:466-490`)
  — required for ABIs where int and float function-args live in
  different register classes (x86_64 sysv, aarch64 AAPCS). Direct
  casts would corrupt. [from-comment]
- The header includes `utils/elog.h` and `utils/palloc.h` — so
  `ereport`, `palloc` are universally available with a single
  `#include "postgres.h"`. [verified-by-code]
- `NameGetDatum` ultimately calls `CStringGetDatum(NameStr(*X))` —
  it does NOT copy. `NameData` is a fixed-size embedded struct (the
  64-byte slot from `c.h`), so this is safe only while the source
  remains live (`postgres.h:404-409`).
- `NON_EXEC_STATIC` under `EXEC_BACKEND` exposes symbols that are
  normally file-static. ASLR + non-static = predictable layout, which
  is intentional for the EXEC_BACKEND postmaster→child handoff.
  [ISSUE-defense-in-depth: NON_EXEC_STATIC turns module-private state
  into linker-visible symbols under `EXEC_BACKEND`; a load-time
  attacker on Windows can locate them (nit)]

## Potential issues

- `postgres.h:76` — `SIZEOF_DATUM` is documented as "vestigial" but
  extension code may still consult it. If PG ever widens `Datum`
  (e.g. for 128-bit nullable datums), this symbol becomes a hazard.
  [ISSUE-stale-todo: SIZEOF_DATUM is vestigial; should be `#define
  DEPRECATED 1` or commented hostilely (nit)]
- `postgres.h:288-294` — `MultiXactIdGetDatum` exists but
  `DatumGetMultiXactId` does not — readers must use
  `DatumGetTransactionId` and rely on the typedef equivalence.
  [ISSUE-api-shape: asymmetric GetDatum/DatumGet pair for
  MultiXactId (nit)]
- `postgres.h:556-561` — `pg_ternary` uses signed enum with `-1`
  for UNSET. Switches that forget the UNSET case won't get
  exhaustiveness warnings unless compiled with
  `-Wswitch-enum`. [ISSUE-api-shape: `pg_ternary` "unset" easy to
  miss in switch (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/datum-nullabledatum.md](../../../data-structures/datum-nullabledatum.md)
