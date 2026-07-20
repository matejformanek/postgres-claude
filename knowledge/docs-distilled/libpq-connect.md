---
source_url: https://www.postgresql.org/docs/current/libpq-connect.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.1 — Database Connection Control Functions (async connect state machine, multi-host failover)"
maps_to_skill: wire-protocol
---

# libpq §34.1 — Database Connection Control Functions

How a libpq client opens a connection — including the non-blocking
`PQconnectPoll` state machine that mirrors the cancel/pipeline poll loops, and
the comma-separated multi-host failover + load-balancing rules.

## Non-obvious claims

- **The non-blocking connect is a poll loop with a fixed initial state.** Call
  `PQconnectStartParams` (or `PQconnectStart`), then drive `PQconnectPoll`:
  "On the first iteration, i.e., if you have yet to call `PQconnectPoll`, behave
  as if it last returned `PGRES_POLLING_WRITING`" — i.e. **start by waiting for
  write-readiness.** Loop until `PGRES_POLLING_OK` or `PGRES_POLLING_FAILED`;
  select for read on `PGRES_POLLING_READING`, write on `PGRES_POLLING_WRITING`.
  `PQconnectStartParams` at `source/src/interfaces/libpq/fe-connect.c:877`,
  `PQconnectPoll` at `:2930`. [verified-by-code] Enum
  `PGRES_POLLING_FAILED=0 / READING / WRITING / OK / ACTIVE(unused)` at
  `libpq-fe.h:121-125`. [verified-by-code]
- **The socket can change between poll calls.** "Do not assume that the socket
  remains the same across `PQconnectPoll` calls." Always re-fetch via
  `PQsocket`. This happens precisely because a single host may be retried against
  multiple addresses (IPv4/IPv6) or hosts. [from-docs]
- **`connect_timeout` is ignored under `PQconnectPoll`.** The application must
  track elapsed time itself; `PQsocketPoll(sock, forRead, forWrite, end_time)`
  (end_time = µs since epoch, `-1` infinite, `0` immediate) abstracts the
  `select`/`poll` setup. [from-docs]
- **Auth failure does NOT fall through to the next host.** "When multiple hosts
  are specified, or when a single host name is translated to multiple addresses,
  all the hosts and addresses will be tried in order, until one succeeds… If a
  connection is established successfully, but authentication fails, the remaining
  hosts in the list are not tried." [from-docs]
- **`load_balance_hosts=random` shuffles at two levels and can skew load.**
  "First the hosts will be resolved in random order. Then secondly, before
  resolving the next host, all resolved addresses for the current host will be
  tried in random order. This behaviour can skew the amount of connections each
  node gets greatly… when some hosts resolve to more addresses than others."
  Option registered at `fe-connect.c:388`. [verified-by-code]
- **`target_session_attrs` drives the CONNECTION_CHECK_* handshake states.**
  `read-write` / `read-only` / `primary` / `standby` / `prefer-standby` / `any`;
  libpq issues `SHOW transaction_read_only` / `pg_is_in_recovery()` probes,
  surfacing as `CONNECTION_CHECK_WRITABLE` / `CONNECTION_CHECK_STANDBY` in the
  poll status. Option at `fe-connect.c:383`. [verified-by-code] The intermediate
  `CONNECTION_*` statuses are explicitly *not* stable: "An application should
  never rely upon these occurring in a particular order, or at all." [from-docs]
- **`host` (not `hostaddr`) is the password-file lookup key.** "when both `host`
  and `hostaddr` are specified, `host` is used to identify the connection in a
  password file." You can have different `.pgpass` passwords per host, but "All
  the other connection options are the same for every host in the list" — no
  per-host username. [from-docs]
- **DNS resolution can block `PQconnectPoll` for a long time.** "the lookup
  occurs when `PQconnectPoll` first considers this host name, and it may cause
  `PQconnectPoll` to block for a significant amount of time." Use `hostaddr` to
  suppress DNS. [from-docs]
- **`expand_dbname` only expands the *first* `dbname`.** If the first `dbname`
  value contains `=` or a `postgresql://` / `postgres://` URI prefix it is parsed
  as a full conninfo; "any subsequent `dbname` parameter is processed as a plain
  database name." Repeated keys: "the last value (that is not NULL or empty) is
  used." [from-docs] `PQconnectdbParams` at `fe-connect.c:775`. [verified-by-code]
- **You must `PQfinish` even on failure.** "when `PQconnectStart` or
  `PQconnectStartParams` returns a non-null pointer, you must call `PQfinish`…
  This must be done even if the connection attempt fails or is abandoned." [from-docs]
- **`ssl=true` is silently rewritten to `sslmode=require`** for JDBC-URI
  compatibility. [from-docs]

## Links into corpus

- Backend side of the startup handshake (SSL/GSS negotiation codes, BackendKeyData):
  [[knowledge/docs-distilled/protocol-flow.md]],
  [[knowledge/docs-distilled/sasl-authentication.md]],
  [[knowledge/docs-distilled/auth-pg-hba-conf.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-connect.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-int.h.md]].
- Same poll-loop pattern reused by: `libpq-cancel.md` (PQcancelPoll).
