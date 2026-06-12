---
path: src/interfaces/libpq-oauth/oauth-utils.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 155
depth: read
---

# `oauth-utils.c` — glue providing libpq internals to the dynamic OAuth module

## Purpose

`libpq-oauth` is built as a **separate dynamic library** that is loaded by
libpq on demand. To avoid baking libpq's private ABI (`libpq-int.h`) into
that module — which would risk inadvertent ABI breaks on minor-version
bumps — the module is compiled *without* `libpq-int.h` (the
`USE_DYNAMIC_OAUTH` build). This file supplies hand-copied replacements
for the few internal libpq APIs [[oauth-curl.c]] needs: the thread-lock
accessor, the NLS `libpq_gettext` shim, and the SIGPIPE block/reset pair.
The header guards at lines 23-29 hard-`#error` if this file is reached in
a static build or if `libpq-int.h` leaked in.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `libpq_oauth_init(libpq_gettext_func)` | oauth-utils.c:45 | Injection point libpq calls once: captures `PQgetThreadLock()` into `pg_g_threadlock` and stores the host's `libpq_gettext` implementation. |
| `libpq_gettext(const char *)` | oauth-utils.c:57 | (NLS builds only) Defers to the injected impl; falls back to `unconstify`-passthrough if libpq's own build didn't enable NLS. |
| `pq_block_sigpipe(sigset_t *, bool *)` | oauth-utils.c:93 | Verbatim copy of libpq's internal SIGPIPE blocker; reports a pending SIGPIPE so the caller can decide whether to drain it. |
| `pq_reset_sigpipe(sigset_t *, bool, bool)` | oauth-utils.c:129 | Companion: optionally `sigwait`s a synthetic SIGPIPE and restores the saved signal mask. |
| `pg_g_threadlock` (global) | oauth-utils.c:35 | Function pointer the `pglock_thread()`/`pgunlock_thread()` macros call. |

## Invariants & gotchas

- **Callers must treat `libpq_gettext()`'s return as const** — in non-NLS
  builds it passes the argument straight through (oauth-utils.c:64-70).
- `libpq_oauth_init()` must run before any threadlock or gettext use;
  `pg_start_oauthbearer` relies on libpq having called it during library
  load. `pg_g_threadlock` being NULL would crash `pglock_thread()`.
- `SOCK_ERRNO`/`SOCK_ERRNO_SET` are re-`#define`d here (oauth-utils.c:82)
  because they live in `libpq-int.h`, which this file can't include — a
  small but real duplication-drift risk if libpq's definitions change.
- The SIGPIPE helpers use `pthread_sigmask`, so they are per-thread; this
  is what makes `CURLOPT_NOSIGNAL` safe in multithreaded clients.

## Cross-refs

- [[oauth-utils.h]] — declarations + the `PGTernaryBool` enum.
- [[oauth-curl.c]] — the sole consumer (`pglock_thread`, `libpq_gettext`,
  `pq_block_sigpipe`).
- `knowledge/files/src/interfaces/libpq/fe-misc.c.md` — libpq's *original*
  `pqsignal`/SIGPIPE handling that these copies mirror (if present).
