---
path: src/interfaces/libpq/test/libpq_testclient.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 37
depth: read
---

# `libpq_testclient.c` — minimal libpq public-API smoke-test program

## Purpose

A tiny test executable that exercises libpq's *public* API surface.
Currently it supports a single mode, `--ssl`, which prints the name of the
SSL library libpq was built against (or "SSL is not enabled"). It exists
so the libpq test harness can assert which TLS backend is actually linked
in, without parsing build configuration.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main(int, char **)` | libpq_testclient.c:26 | Dispatches on `--ssl`; any other invocation prints a usage line and returns 1. |
| `print_ssl_library(void)` | libpq_testclient.c:15 | Calls `PQsslAttribute(NULL, "library")` — the `NULL` conn form that reports the *compiled-in* library rather than a per-connection attribute. |

## Invariants & gotchas

- Uses `PQsslAttribute(NULL, …)`: passing a NULL `PGconn` is the
  documented way to query build-time SSL info before any connection
  exists.
- Returns non-zero for unrecognized args, so the harness can distinguish
  "feature absent" from "wrong invocation".

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-secure.c.md` — defines
  `PQsslAttribute` (if present in corpus).
- [[libpq_uri_regress.c]] — sibling test helper in this directory.
