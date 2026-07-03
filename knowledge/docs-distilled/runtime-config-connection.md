---
source_url: https://www.postgresql.org/docs/current/runtime-config-connection.html
fetched_at: 2026-07-02T20:54:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Connections and Authentication (§20.3)

The postmaster-time connection/auth GUCs. Sections: Connection Settings, TCP
Settings, Authentication, SSL. Companion: `knowledge/docs-distilled/connect-estab.md`,
skill `debugging` (max_connections + shmem sizing).

## max_connections couples to shared memory AND to the standby

- **`max_connections` (~100, POSTMASTER)** directly sizes shared memory — the
  lock table, PGPROC array, and predicate-lock table are all
  `max_connections`-derived (see `runtime-config-locks.md`
  `max_locks_per_transaction` formula). **A standby's `max_connections` must be
  ≥ the primary's**, or the standby refuses queries — because the primary's
  known-transaction bookkeeping (KnownAssignedXids) is sized from it. This is
  the recurring "standby won't start after lowering max_connections on primary"
  footgun. [from-docs]

## The three-tier connection reserve

- Free slots are guarded in layers: **`reserved_connections` (0)** for roles
  with `pg_use_reserved_connections`, then **`superuser_reserved_connections`
  (3)** as the final emergency reserve for superusers only. Both must stay below
  `max_connections` minus the other. When free slots ≤ the reserve, only the
  privileged tier connects — which is why a runaway app can lock everyone out
  *except* a superuser rescue session. [from-docs]

## Unix-socket details a hacker trips on

- **`unix_socket_directories` (default `/tmp`, POSTMASTER)** — comma-list;
  a leading **`@` makes an abstract-namespace socket (Linux only)**. Each
  directory also gets a `.s.PGSQL.NNNN.lock` file — **do not delete it
  manually**. **`unix_socket_permissions` (0777)** — for Unix sockets **only
  write permission matters**; `0770`/`0700` narrow access (ignored on Solaris /
  abstract sockets). [from-docs]

## listen_addresses / port geometry

- **`listen_addresses` (default `localhost`, POSTMASTER)** — `*` = all
  interfaces, empty string = **TCP disabled, Unix-socket only**. Server starts
  if it binds ≥1 address (warns on the rest). **`port` (5432)** is the same for
  every bound address — it cannot vary per interface. [from-docs]

## TCP keepalive knobs are no-ops on Unix sockets

- **`tcp_keepalives_idle` / `_interval` / `_count`, `tcp_user_timeout` (all 0 =
  OS default, SIGHUP)** are **ignored on Unix-domain sockets** (read back as 0).
  **`client_connection_check_interval` (0, SIGHUP)** polls the socket mid-query
  to abort sooner when the client vanishes — **Linux/macOS/illumos/BSD only**.
  Together these are the "detect a dead client before the query finishes"
  surface. [from-docs]

## Authentication essentials

- **`password_encryption` (default `scram-sha-256`, SIGHUP)** — algorithm for
  *new* passwords; `md5` is deprecated. **`scram_iterations` (4096, SIGHUP)**
  raises SCRAM cost but **does not touch existing passwords** (the iteration
  count is baked in at encryption time — a re-`ALTER ROLE ... PASSWORD` is
  needed to adopt a new value). **`md5_password_warnings` (on)** warns on new
  MD5 passwords. **`authentication_timeout` (1m, POSTMASTER)** frees a slot from
  a client that never finishes the auth handshake. [from-docs]
- SSL block (all POSTMASTER): **`ssl` (off)**, `ssl_min_protocol_version`
  (`TLSv1.2` — SSL 2/3 always off), `ssl_ciphers`
  (`HIGH:MEDIUM:+3DES:!aNULL`), and in PG18 **`ssl_groups`** (renamed from
  `ssl_ecdh_curve`, default `X25519:prime256v1`). `ssl_crl_dir` picks up new
  CRLs immediately where `ssl_crl_file` is load-once-at-startup. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/connect-estab.md]] — the postmaster fork/backend-startup path these GUCs gate.
- [[knowledge/docs-distilled/runtime-config-locks.md]] — the shmem-sizing formula max_connections feeds.
- [[knowledge/subsystems/storage-lmgr.md]] — PGPROC / lock table sized from max_connections.
- Skill: `debugging` — max_connections vs shmem, standby-mismatch startup failures.

## Confidence note

All `[from-docs]` (Connections and Authentication chapter, fetched 2026-07-02;
page rendered §19.3 numbering — docs-version skew, slug stable). SSL cipher
defaults and `ssl_groups` rename are as the PG18 page states; not re-verified
against source this run. `db_user_namespace` / `huge_pages` /
`dynamic_shared_memory_type` are NOT on this page (Resource Consumption §20.4 /
File Locations §20.2 respectively).
