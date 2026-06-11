---
path: src/interfaces/libpq-oauth/oauth-utils.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 52
depth: read
---

# `oauth-utils.h` — declarations for the OAuth module's libpq-internal shims

## Purpose

Declares the API surface implemented by [[oauth-utils.c]]: the
`libpq_oauth_init` injection hook, the duplicated SIGPIPE helpers, the
`libpq_gettext` shim, and the `pg_g_threadlock`-backed
`pglock_thread()`/`pgunlock_thread()` macros. Also defines `PGTernaryBool`
(used by [[oauth-curl.c]]'s `initialize_curl` to cache curl-global-init
state across calls without a separate "is it set" flag).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `typedef … libpq_gettext_func` | oauth-utils.h:21 | Type of the gettext impl libpq injects. |
| `libpq_oauth_init(libpq_gettext_func)` | oauth-utils.h:24 | `PGDLLEXPORT` init hook. |
| `enum PGTernaryBool` | oauth-utils.h:31 | `PG_BOOL_UNKNOWN/YES/NO`; UNKNOWN is 0 so a zeroed/`static` var starts "unknown". |
| `pq_block_sigpipe` / `pq_reset_sigpipe` | oauth-utils.h:38-39 | SIGPIPE helpers (copied from libpq). |
| `libpq_gettext(const char *)` | oauth-utils.h:42 | NLS builds; `#define`d to identity otherwise (oauth-utils.h:44). |
| `pg_g_threadlock` + `pglock_thread`/`pgunlock_thread` | oauth-utils.h:47-50 | Thread-lock accessor and the lock/unlock macros. |

## Invariants & gotchas

- Includes `libpq-fe.h` and `pqexpbuffer.h` only — the whole point is to
  *avoid* `libpq-int.h` in the dynamic build (see [[oauth-curl.c]] header
  block).
- The comment at oauth-utils.h:26-29 flags these as *duplicated* APIs and
  a future deduplication target — a standing doc-drift watch item against
  libpq's real `libpq-int.h` definitions.

## Cross-refs

- [[oauth-utils.c]] — the implementation.
- [[oauth-curl.c]] — consumer of every symbol here.
