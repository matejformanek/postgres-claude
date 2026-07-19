# libpq-be-fe.h

- **Source path:** `source/src/include/libpq/libpq-be-fe.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Wrapper functions for using libpq in extensions" — backend code can't
directly link against libpq, but extensions can. The main risk extensions
face is leaking malloc'd `PGresult`s across PG_CATCH boundaries; this
header wraps `PGresult` in a MemoryContext-attached object that gets
`PQclear`-ed automatically when the context is reset [from-comment].

## Public API surface (all `static inline`)

- `libpqsrv_PGresult` — wrapper struct: `{PGresult *res; MemoryContext ctx;
  MemoryContextCallback cb;}`. The callback runs `PQclear` on the wrapped
  `res`.
- `libpqsrv_PQwrap(PGresult *)` — wrap a raw libpq result; passes NULL
  through; uses `MCXT_ALLOC_NO_OOM` so it can free the result if the
  wrapper allocation fails [verified-by-code].
- `libpqsrv_PQclear`, `libpqsrv_PGresultSetParent` — explicit free and
  reparent.
- `libpqsrv_PQgetResult(PGconn *)` — wraps `PQgetResult` result.
- Accessor wrappers (`libpqsrv_PQresultStatus`, `libpqsrv_PQresultErrorMessage`,
  `libpqsrv_PQresultErrorField`, `libpqsrv_PQcmdStatus`, `libpqsrv_PQntuples`,
  `libpqsrv_PQnfields`, `libpqsrv_PQgetvalue`, `libpqsrv_PQgetlength`,
  `libpqsrv_PQgetisnull`, `libpqsrv_PQfname`, `libpqsrv_PQcmdTuples`) —
  each emulates the underlying libpq function for NULL input
  (e.g. `PGRES_FATAL_ERROR`, `""`, `0`, `NULL`) [verified-by-code].

## Macro takeover

The bottom of the header `#define`s the bare libpq names (`PGresult`,
`PQclear`, `PQgetResult`, `PQresultStatus`, `PQresultErrorMessage`,
`PQresultErrorField`, `PQcmdStatus`, `PQntuples`, `PQnfields`, `PQgetvalue`,
`PQgetlength`, `PQgetisnull`, `PQfname`, `PQcmdTuples`) to point at the
wrapper functions, so extension code can use the familiar libpq spelling
and transparently get the leak-safe wrappers [from-comment].

## Internal landmarks

- `#ifdef BUILDING_DLL` `#error` at top — refuses to compile if the file
  is pulled into core backend code [verified-by-code].
- Forced include of `libpq-fe.h` — frontend libpq header is the source of
  the underlying types.

## Cross-refs

- Companion: `knowledge/files/src/include/libpq/libpq-be-fe-helpers.h.md`
  (built on this header).
- Frontend: `src/interfaces/libpq/libpq-fe.h`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-correctness: macro takeover hides function-pointer assignments]**
  `libpq-be-fe.h:244-257` — once `#define PQclear libpqsrv_PQclear` is in
  scope, any extension code that takes `&PQclear` as a function pointer
  (for callback registration, e.g. `PQsetNoticeReceiver` paired with a
  custom cleanup) will silently get the wrapper, which expects a
  `libpqsrv_PGresult *`, not the libpq `PGresult *` libpq will hand it.
  The notice-receiver path in `libpq-be-fe-helpers.h` already documents
  why this matters; other call sites could fail less visibly. Severity:
  maybe.
- **[ISSUE-undocumented-invariant: SetParent raises on OOM, but PQwrap doesn't]**
  `libpq-be-fe.h:69-80,116-119` — `libpqsrv_PQwrap` uses
  `MCXT_ALLOC_NO_OOM` + explicit `PQclear`+`ereport` on failure;
  `libpqsrv_PGresultSetParent` uses plain `MemoryContextAlloc` which throws
  on OOM. On the throw path the old wrapper is still registered on its old
  context — no leak — but the asymmetry is undocumented. Severity: maybe.

## Tally

`[verified-by-code]=5 [from-comment]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
