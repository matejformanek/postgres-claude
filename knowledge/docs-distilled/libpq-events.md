---
source_url: https://www.postgresql.org/docs/current/libpq-events.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.14 — Event System (per-connection/per-result callback hooks for wrapper libraries)"
maps_to_skill: extension-development
---

# libpq §34.14 — libpq Event System

A hook mechanism for libraries layered on top of libpq (ODBC drivers, language
bindings): register a callback on a `PGconn` and it fires across the connection
and every `PGresult`'s lifecycle, with per-callback private "instance data" that
follows results through copies.

## Non-obvious claims

- **The callback signature and the six event ids are fixed in the public header.**
  `typedef int (*PGEventProc)(PGEventId evtId, void *evtInfo, void *passThrough)`
  at `source/src/interfaces/libpq/libpq-events.h:69`; the `PGEventId` enum is
  `PGEVT_REGISTER, PGEVT_CONNRESET, PGEVT_CONNDESTROY, PGEVT_RESULTCREATE,
  PGEVT_RESULTCOPY, PGEVT_RESULTDESTROY` at `libpq-events.h:29-34`. [verified-by-code]
- **The proc *address* is the lookup key, so it can register only once per
  `PGconn`.** `PQregisterEventProc(conn, proc, name, passThrough)` — "A particular
  event procedure can be registered only once in any `PGconn`. This is because the
  address of the procedure is used as a lookup key to identify the associated
  instance data." [from-docs]
- **The `passThrough` pointer is immortal and shared; instance data is not
  inherited.** passThrough "never changes for the life of the `PGconn` and all
  `PGresult`s generated from it." But "instance data of a `PGconn` is not
  automatically inherited by `PGresult`s created from it" — that is exactly what
  the `PGEVT_RESULTCREATE` hook is for. [from-docs]
- **Firing points, precisely:**
  - `PGEVT_REGISTER` — at `PQregisterEventProc` time; "the ideal time to
    initialize any instanceData"; **"If the event procedure fails (returns zero),
    the registration is canceled."**
  - `PGEVT_CONNRESET` — after a *successful* `PQreset`/`PQresetPoll` only.
  - `PGEVT_CONNDESTROY` — on `PQfinish`, *before* other cleanup; return value
    ignored (PQfinish can't fail).
  - `PGEVT_RESULTCREATE` — after any result-producing call, including
    `PQgetResult`. **If it returns zero, "that event procedure will be ignored for
    the remaining lifetime of the result… it will not receive `PGEVT_RESULTCOPY`
    or `PGEVT_RESULTDESTROY` events for this result or results copied from it."**
  - `PGEVT_RESULTCOPY` — on `PQcopyResult`; only procs that *succeeded* at
    `RESULTCREATE`/`RESULTCOPY` on the source receive it; "can be used to provide
    a deep copy of instanceData, since `PQcopyResult` cannot do that."
  - `PGEVT_RESULTDESTROY` — on `PQclear`, *before* other cleanup. [from-docs]
- **Two instance-data namespaces, keyed by proc address.** Connection-level:
  `PQsetInstanceData(conn, proc, data)` / `PQinstanceData(conn, proc)`.
  Result-level: `PQresultSetInstanceData(res, proc, data)` /
  `PQresultInstanceData(res, proc)`. [from-docs]
- **Result instance data should be allocated with `PQresultAlloc`.** Otherwise
  "any storage represented by `data` will not be accounted for by
  `PQresultMemorySize`" and must be freed explicitly on
  `PGEVT_RESULTDESTROY`; using `PQresultAlloc` ties it to the result's lifetime. [from-docs]
- **`PQcopyResult` only copies events when asked.** Event procs propagate to a
  copied result only with the `PG_COPYRES_EVENTS` flag; that is when
  `PGEVT_RESULTCOPY` fires. [from-docs]
- **Return-value contract:** non-zero = success. Zero is meaningful only for
  `REGISTER` / `RESULTCREATE` / `RESULTCOPY` (disables the proc); ignored for the
  two DESTROY events. [from-docs]

## Links into corpus

- Consumers of this hook are exactly the "wrapper library" case the
  `extension-development` skill covers (out-of-tree code layered on libpq).
- Result lifecycle these hooks bracket: [[knowledge/docs-distilled/libpq-async.md]],
  [[knowledge/docs-distilled/libpq-single-row-mode.md]].
- Source: [[knowledge/files/src/interfaces/libpq/libpq-events.h.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-events.c.md]],
  [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]].
