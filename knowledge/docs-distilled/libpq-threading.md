---
source_url: https://www.postgresql.org/docs/current/libpq-threading.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.22 — Behavior in Threaded Programs (one-PGconn-per-thread rule, always thread-safe on v17+, cooperative locks)"
maps_to_skill: wire-protocol
---

# libpq §34.22 — Behavior in Threaded Programs

libpq is reentrant, with one hard boundary: a `PGconn` is a single-threaded
object. Everything else is about cooperatively locking libraries libpq shares
with the application (Kerberos, libcurl).

## Non-obvious claims

- **libpq is always thread-safe as of PG17.** `PQisthreadsafe()` returns 1 on
  v17+ (the `--disable-thread-safety` build option is gone); on older libpq it
  could return 0. So new code can assume reentrancy but should still call it if
  it might link an ancient libpq. [from-docs]
- **The one rule: never touch a `PGconn` from two threads at once.** "no two
  threads attempt to manipulate the same `PGconn` object at the same time. In
  particular, you cannot issue concurrent commands from different threads through
  the same connection object. (If you need to run concurrent commands, use
  multiple connections.)" Different `PGconn`s in different threads is fine and
  fully parallel. [from-docs]
- **`PGresult`s are read-only and freely shareable — with two exceptions.** A
  result can be handed between threads safely *unless* you call a result-*mutating*
  function on it (the `PQsetvalue`/`PQsetResultAttrs` builders of §34.13, or the
  escape-into-result helpers), which then needs the same one-thread-at-a-time
  discipline as a `PGconn`. [from-docs]
- **The still-unsafe functions are the deprecated globals.** `PQrequestCancel`
  (use `PQcancelBlocking`, the PG17 object API) and `PQoidStatus` (use
  `PQoidValue`) are "not thread-safe" — they touch or overwrite shared/`PGconn`
  state. This is a headline reason the new cancel API exists (see
  [[knowledge/docs-distilled/libpq-cancel.md]]). [from-docs]
- **Third-party library locking is the caller's job.** Kerberos "functions are not
  thread-safe" — register a cooperative lock via `PQregisterThreadLock`. libcurl
  (for OAuth) "must cooperatively lock around initialization unless libcurl was
  globally initialized before threads started, or a newer thread-safe version is
  used." [from-docs]
- **OpenSSL/libcrypto init is a shared-global hazard libpq will manage for you —
  unless told not to.** `PQinitOpenSSL(do_ssl, do_crypto)` / `PQinitSSL(bool)`
  let the application declare whether libpq should initialize the SSL library and
  libcrypto locking callbacks, so a program that *also* uses OpenSSL directly can
  own that init once and stop libpq from double-initializing. (Referenced from the
  threading discussion; call these before any connection.) [from-docs][inferred]

## Links into corpus

- The deprecated-unsafe cancel path this replaces:
  [[knowledge/docs-distilled/libpq-cancel.md]].
- SSL library init pairs with the SSL config page:
  [[knowledge/docs-distilled/libpq-ssl.md]].
- Per-connection state that must not be shared:
  [[knowledge/docs-distilled/libpq-async.md]] (the send/PQgetResult state machine
  is inherently single-thread-per-conn).
- OAuth/libcurl path: [[knowledge/files/src/interfaces/libpq/fe-auth-oauth.c.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-connect.c.md]] (PQisthreadsafe,
  PQregisterThreadLock, PQinitOpenSSL),
  [[knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md]].
