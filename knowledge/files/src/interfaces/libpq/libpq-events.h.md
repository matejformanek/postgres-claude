# libpq-events.h

- **Source path:** `source/src/interfaces/libpq/libpq-events.h`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 95 lines

## Purpose

> "Definitions that are useful to applications that invoke the libpq 'events' API, but are not interesting to ordinary users of libpq." [`libpq-events.h:4-6`, from-comment]

A plugin-registration API: callers register a `PGEventProc` function with a `PGconn`, and libpq calls it on connection/result lifecycle events. Used by postgres_fdw (e.g. for transaction callback bookkeeping) and various ORM driver wrappers.

## Event IDs (lines 27-35)

`PGEventId` enum:

- `PGEVT_REGISTER` — fires on `PQregisterEventProc`. Plugin can refuse registration by returning 0.
- `PGEVT_CONNRESET` — fires after a successful `PQreset` (and once on initial connect).
- `PGEVT_CONNDESTROY` — fires from `PQfinish` before the conn is freed.
- `PGEVT_RESULTCREATE` — fires when a new PGresult is constructed from server data; plugin can attach per-result instance data here.
- `PGEVT_RESULTCOPY` — fires from `PQcopyResult` when copying events between results.
- `PGEVT_RESULTDESTROY` — fires from `PQclear` before the result is freed.

## Event-info structs (lines 37-67)

Each event delivers a typed `evtInfo` pointer:

- `PGEventRegister { PGconn *conn; }`
- `PGEventConnReset { PGconn *conn; }`
- `PGEventConnDestroy { PGconn *conn; }`
- `PGEventResultCreate { PGconn *conn; PGresult *result; }`
- `PGEventResultCopy { const PGresult *src; PGresult *dest; }`
- `PGEventResultDestroy { PGresult *result; }`

## Callback signature

```c
typedef int (*PGEventProc) (PGEventId evtId, void *evtInfo, void *passThrough);
```

Returns non-zero on success, zero on failure. The `passThrough` pointer is the one given to `PQregisterEventProc`.

## API (lines 72-88)

- `PQregisterEventProc(conn, proc, name, passThrough)` — register; fires `PGEVT_REGISTER` synchronously. The `name` is copied (used in error messages).
- `PQsetInstanceData(conn, proc, data)` / `PQinstanceData(conn, proc)` — per-conn opaque pointer indexed by proc address.
- `PQresultSetInstanceData(result, proc, data)` / `PQresultInstanceData(result, proc)` — per-result opaque pointer.
- `PQfireResultCreateEvents(conn, res)` — manually fire RESULTCREATE for an app-built result (e.g. one made via `PQmakeEmptyPGresult`).

## Cross-references

- `libpq-events.c` — implementation.
- `libpq-int.h` — `PGEvent` struct (the per-event record stored on conn/result) at lines 156-163.
- Public via `libpq-fe.h` since the header `#include`s it (line 19).

## Tally

`[verified-by-code]=3 [from-comment]=1`
