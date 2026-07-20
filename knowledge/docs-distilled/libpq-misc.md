---
source_url: https://www.postgresql.org/docs/current/libpq-misc.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.13 — Miscellaneous Functions (PQfreemem Windows heap rule, hand-built PGresults, PQencryptPasswordConn SCRAM)"
maps_to_skill: wire-protocol
---

# libpq §34.13 — Miscellaneous Functions

The grab-bag: memory freeing, application-constructed `PGresult`s, runtime
version, and client-side password encryption. The `PQfreemem` heap rule and the
`PGresult`-builder set are the two that bite people.

## Non-obvious claims

- **`PQfreemem` exists for the Windows DLL heap boundary.** Frees anything libpq
  malloc'd for you (`PQescapeByteaConn`, `PQunescapeBytea`, `PQnotifies`, …). "It
  is particularly important that this function, rather than `free()`, be used on
  Microsoft Windows. This is because allocating memory in a DLL and releasing it
  in the application works only if multithreaded/single-threaded, release/debug,
  and static/dynamic flags are the same for the DLL and the application." On
  non-Windows it's plain `free()`. [from-docs]
- **`PQconninfoFree`, not `PQfreemem`, for conninfo arrays.** The
  `PQconninfoOption*` returned by `PQconndefaults`/`PQconninfoParse` holds
  references to subsidiary strings, so it needs its own recursive free. [from-docs]
- **Applications can *fabricate* `PGresult`s.** `PQmakeEmptyPGresult(conn,
  status)` (`source/src/interfaces/libpq/fe-exec.c:160`) allocates an empty
  result; if `conn` is non-NULL it copies the current error message (for error
  statuses) **and the registered event procedures**. Then
  `PQsetResultAttrs(res, n, attDescs)` defines columns (fails if attrs already
  exist), and `PQsetvalue(res, tup, field, value, len)`
  (`fe-exec.c:453`) fills cells, auto-growing the tuple array;
  `len == -1` or `value == NULL` sets SQL NULL, and the value is *copied* into the
  result's private storage. This is how proxies/FDWs/mock layers synthesize
  results the application code can't tell from real ones. Free with `PQclear`.
  [verified-by-code][from-docs]
- **`PQresultAlloc` / `PQresultMemorySize` manage result-tied storage.**
  `PQresultAlloc(res, nBytes)` gives malloc-aligned memory that's auto-freed by
  `PQclear`; `PQresultMemorySize(res)` reports the total bytes the result owns —
  useful for capping memory when caching many results. [from-docs]
- **`PQlibVersion()` reports the *linked-library* version, distinct from
  `PQserverVersion`.** Same `major*10000 + minor` encoding (`170004` = 17.4);
  "divide by **100** not 10000 to determine a logical major version number."
  Appeared in 9.1 (`libpq-fe.h:726`). Use it to gate on client-library features;
  use `PQserverVersion` to gate on server features — they can differ. [verified-by-code][from-docs]
- **`PQencryptPasswordConn` picks the algorithm, and can silently query the
  server.** `PQencryptPasswordConn(conn, passwd, user, algorithm)` encrypts
  before an `ALTER USER … PASSWORD` so cleartext never hits the logs. `algorithm`:
  `scram-sha-256` (v10+), `md5`, `on`/`off` (aliases for `md5`), or **`NULL` →
  read the server's `password_encryption` GUC** — and that NULL path "can block;
  may fail if transaction aborted or connection busy." Result is malloc'd → free
  with `PQfreemem`. [from-docs]
- **`PQencryptPassword` (no `Conn`) is deprecated and MD5-only.** No connection
  object, always `md5`; superseded by `PQencryptPasswordConn` for SCRAM support.
  [from-docs]
- **`PQgetCurrentTimeUSec` returns `pg_usec_time_t` microseconds since the Unix
  epoch** — paired with `PQsocketPoll` for computing async connect/query
  timeouts. [from-docs]

## Links into corpus

- `PGresult` status/field accessors these builders populate:
  [[knowledge/docs-distilled/libpq-exec.md]].
- `PQfreemem` obligations from other pages:
  [[knowledge/docs-distilled/libpq-notify.md]] (PGnotify),
  [[knowledge/docs-distilled/libpq-connect.md]] (conninfo).
- SCRAM verifier construction server-side: `fe-auth-scram.c` corpus,
  [[knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md]]; the
  `wire-protocol` skill for the SASL exchange.
- Version-gating counterpart: [[knowledge/docs-distilled/libpq-status.md]]
  (PQserverVersion).
- Source: [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]],
  [[knowledge/files/src/interfaces/libpq/fe-misc.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
