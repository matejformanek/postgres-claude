---
source_url: https://www.postgresql.org/docs/current/libpq-status.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.2 — Connection Status Functions (ConnStatusType, transaction-status state machine, cached ParameterStatus, version encoding)"
maps_to_skill: wire-protocol
---

# libpq §34.2 — Connection Status Functions

The accessor layer over the opaque `PGconn`. The docs are emphatic that
applications must go through these functions and **not** reach into
`libpq-int.h`: "Reference to internal `PGconn` fields using `libpq-int.h` is not
recommended because they are subject to change in the future." [from-docs]

## Non-obvious claims

- **`PQstatus` is only binary at rest, but not monotonic.** Returns
  `CONNECTION_OK` or `CONNECTION_BAD` (`ConnStatusType`,
  `source/src/interfaces/libpq/libpq-fe.h:90-91`, enum closes `:117`). "An OK
  status will remain so until `PQfinish`, but a communications failure might
  result in the status changing to `CONNECTION_BAD` prematurely" — recover with
  `PQreset`. The *other* `ConnStatusType` members (`CONNECTION_STARTED`,
  `CONNECTION_AWAITING_RESPONSE`, …) are only meaningful during the async
  `PQconnectPoll` handshake. [verified-by-code][from-docs]
- **The transaction-status state machine has five states, one meaning
  "in-flight".** `PGTransactionStatusType` = `PQTRANS_IDLE` / `PQTRANS_ACTIVE` /
  `PQTRANS_INTRANS` / `PQTRANS_INERROR` / `PQTRANS_UNKNOWN`
  (`libpq-fe.h:153-157`). The load-bearing caveat: "`PQTRANS_ACTIVE` is reported
  only when a query has been sent to the server and not yet completed."
  `PQTRANS_UNKNOWN` means the connection is bad. `PQTRANS_INERROR` is the
  "failed transaction block" state — the one that only `ROLLBACK` /
  `ROLLBACK TO SAVEPOINT` escapes. [verified-by-code][from-docs]
- **`PQparameterStatus` reads a client-side cache, not the server.** Only a fixed
  GUC allow-list is auto-reported via `ParameterStatus` protocol messages at
  startup and on change: `application_name`, `client_encoding`, `DateStyle`,
  `default_transaction_read_only` (v14+), `in_hot_standby` (v14+),
  `integer_datetimes`, `IntervalStyle`, `is_superuser`, `scram_iterations`
  (v16+), `search_path` (v18+), `server_encoding`, `server_version`,
  `session_authorization`, `standard_conforming_strings`, `TimeZone`. [from-docs]
- **The returned pointer is `const` but points to mutable `PGconn` storage.** "It
  is unwise to assume the pointer will remain valid across queries." A background
  `ParameterStatus` message (e.g. a `SET` from a trigger, or `client_encoding`
  changing) rewrites it. [from-docs]
- **`standard_conforming_strings` absence has a defined default.** "If no value
  for `standard_conforming_strings` is reported, applications can assume it is
  `off`" — i.e. backslashes are escapes. This is the compatibility shim for
  pre-8.1 servers. [from-docs]
- **Two version encodings, both `major*10000 + minor`, but divide by different
  numbers.** `PQserverVersion` and `PQlibVersion` return e.g. `100001` for 10.1,
  `110000` for 11.0; pre-10 three-part versions pack as `90105` for 9.1.5. "For
  purposes of determining feature compatibility, applications should divide the
  result … by **100** not 10000 to determine a logical major version number."
  [from-docs]
- **`PQfullProtocolVersion` is the new (PG18) minor-protocol accessor.**
  `PQprotocolVersion` (`libpq-fe.h:424`) returns only the major (3, or 0 if bad;
  "Prior to release version 14.0, libpq could additionally return 2");
  `PQfullProtocolVersion` (`:425`) encodes `major*10000 + minor` so 3.2 → `30002`
  — needed now that the wire protocol has a live minor version. A feature macro
  at `libpq-fe.h:61` advertises its presence. [verified-by-code][from-docs]
- **`PQbackendPID` is a *remote* PID and the join key for NOTIFY.** "The backend
  PID is useful … for comparison to `NOTIFY` messages (which include the PID of
  the notifying backend process). Note that the PID belongs to a process
  executing on the database server host, not the local host!" (`:429`).
  [verified-by-code][from-docs]
- **`PQconnectionUsedPassword` vs `PQconnectionNeedsPassword` differ on
  timing/intent.** `NeedsPassword` is a *post-failure* probe ("required a
  password, but none was available") → decide whether to prompt.
  `UsedPassword` works after success *or* failure ("the server demanded a
  password"). `PQconnectionUsedGSSAPI` is the parallel GSSAPI probe. [from-docs]
- **`PQsslAttribute(NULL, "library")` works without a connection (v15+).** Returns
  the default SSL library name (e.g. `"OpenSSL"`), or NULL if built without SSL.
  A feature macro at `libpq-fe.h:43` advertises that this NULL-conn form is
  useful. Other attributes (`protocol`, `key_bits`, `cipher`, `compression`,
  `alpn`) require a live SSL connection; enumerate with `PQsslAttributeNames`
  (NULL-terminated array). `PQsslInUse` is the boolean gate. [verified-by-code][from-docs]
- **`PQerrorMessage` is owned by the `PGconn`.** Multi-line, trailing-newline
  convention; "The caller should not free the result directly. It will be freed
  when the associated `PGconn` handle is passed to `PQfinish`" and "should not be
  expected to remain the same across operations." [from-docs]

## Links into corpus

- ParameterStatus / version / cancel-key origin in the startup handshake:
  [[knowledge/docs-distilled/protocol-flow.md]],
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- `PQtransactionStatus` reflects the backend xact state machine:
  [[knowledge/docs-distilled/transactions.md]], the `wal-and-xlog` corpus for
  what INTRANS/INERROR mean server-side.
- `PQbackendPID` ↔ NOTIFY be_pid: [[knowledge/docs-distilled/libpq-notify.md]].
- SSL attribute plumbing: [[knowledge/docs-distilled/libpq-ssl.md]].
- Source: [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]],
  [[knowledge/files/src/interfaces/libpq/fe-connect.c.md]],
  [[knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md]].
- Backend view of the protocol: [[knowledge/subsystems/libpq-backend.md]].
