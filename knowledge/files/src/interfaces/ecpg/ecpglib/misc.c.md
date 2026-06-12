---
path: src/interfaces/ecpg/ecpglib/misc.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 599
depth: deep
---

# `misc.c` — ecpglib runtime grab-bag: per-thread sqlca, debug logging, NLS, null sentinels

## Purpose
`misc.c` collects the cross-cutting runtime helpers that the rest of ecpglib
leans on. It owns the per-thread `sqlca` (the SQL Communication Area that carries
SQLCODE/SQLSTATE back to the embedded-SQL program), accessed through a
`pthread_key_t` with a `pthread_once`-guarded key init (`misc.c:58-124`). It
provides the debug-logging facility (`ECPGdebug`/`ecpg_log`, `misc.c:203-289`)
that writes timestamps-free, PID-tagged trace lines to a caller-supplied
`FILE *`, the thread-safe NLS shim `ecpg_gettext` (`misc.c:481-533`), the
per-statement init helpers `ecpg_init`/`ecpg_init_sqlca` (`misc.c:66-93`),
transaction control (`ECPGtrans`, `ECPGstatus`, `ECPGtransactionStatus`,
`misc.c:126-200`), the indicator-less NULL sentinel encode/decode pair
(`ECPGset_noind_null`/`ECPGis_noind_null`, `misc.c:291-425`), a Win32 pthread
shim (`misc.c:427-479`), and the global input-variable list used by
`EXEC SQL ... USING` descriptors (`ECPGset_var`/`ECPGget_var`, `misc.c:535-599`).

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `void ecpg_init_sqlca(struct sqlca_t *)` | misc.c:66 | memcpy the static `sqlca_init` template into the caller's sqlca |
| `bool ecpg_init(const struct connection *, const char *, const int)` | misc.c:72 | per-statement reset of sqlca + NULL-connection check; raises on OOM/no-conn |
| `struct sqlca_t *ECPGget_sqlca(void)` | misc.c:107 | returns the calling thread's sqlca, lazily malloc'd into the TLS key |
| `bool ECPGstatus(int, const char *)` | misc.c:126 | true if named connection is open |
| `PGTransactionStatusType ECPGtransactionStatus(const char *)` | misc.c:144 | delegates to `PQtransactionStatus`; UNKNOWN if no conn |
| `bool ECPGtrans(int, const char *, const char *)` | misc.c:159 | runs a transaction command, auto-`begin` when needed |
| `void ECPGdebug(int, FILE *)` | misc.c:203 | enable/disable trace; `n>100` flips regression mode |
| `void ecpg_log(const char *, ...)` | misc.c:231 | internal printf-style trace writer (PID-tagged) |
| `void ECPGset_noind_null(enum ECPGttype, void *)` | misc.c:291 | write the type-specific "NULL" sentinel into a value buffer |
| `bool ECPGis_noind_null(enum ECPGttype, const void *)` | misc.c:360 | test a buffer against the sentinel |
| `char *ecpg_gettext(const char *)` | misc.c:483 | NLS lookup; one-time `bindtextdomain` under mutex (ENABLE_NLS only) |
| `void ECPGset_var(int, void *, int)` | misc.c:537 | register input variable #n in the global `ivlist` |
| `void *ECPGget_var(int)` | misc.c:592 | look up input variable #n in `ivlist` |
| `bool ecpg_internal_regression_mode` (global) | misc.c:29 | when set, suppresses PID in log output for stable regress diffs |
| `struct var_list *ivlist` (global) | misc.c:535 | head of the input-variable list |

## Internal landmarks
- **Per-thread sqlca via TLS.** `sqlca_key` (`misc.c:58`) plus
  `sqlca_key_once`/`ecpg_sqlca_key_init` (`misc.c:59,101-105`) install a
  `pthread_key_t` whose destructor `ecpg_sqlca_key_destructor` (`misc.c:95-99`)
  `free()`s the per-thread struct at thread exit. `ECPGget_sqlca`
  (`misc.c:107-124`) lazily mallocs and zero-templates one sqlca per thread on
  first access — so each thread carries its own error channel.
  `[verified-by-code]`
- **`sqlca_init` static template** (`misc.c:31-56`) — the zeroed sqlca with the
  `"SQLCA   "` eyecatcher and `"NOT SET "` filler; copied (not re-derived) on
  every init via `memcpy` in `ecpg_init_sqlca`. `[verified-by-code]`
- **Two debug mutexes.** `debug_mutex` (`misc.c:61`) guards the actual write to
  `debugstream`; `debug_init_mutex` (`misc.c:62`) serializes concurrent
  `ECPGdebug` calls. `ECPGdebug` deliberately drops `debug_mutex` before calling
  `ecpg_log` to log its own state change, while still holding `debug_init_mutex`
  (`misc.c:222-228`). `simple_debug` (`misc.c:63`) is `volatile int`. `[verified-by-code]`
- **Lock-free fast path in `ecpg_log`.** Reads `simple_debug` without the mutex
  for performance, rechecking it after taking `debug_mutex` (`misc.c:240-270`).
  The comment (`misc.c:241-243`) admits this assumes int loads are atomic. `[from-comment]`
- **`_check` helper** (`misc.c:350-358`) — byte-scan for all-`0xff`, used to
  detect the float/double/interval/timestamp NULL sentinels. `[verified-by-code]`
- **Win32 pthread shim** (`misc.c:427-479`) — local `pthread_mutex_*` and
  `win32_pthread_once` backed by `CRITICAL_SECTION`; only compiled under WIN32. `[verified-by-code]`
- **One-time NLS bind.** `ecpg_gettext` guards `bindtextdomain` with
  `already_bound` + `binddomain_mutex` and saves/restores errno across the call
  because `bindtextdomain` clobbers it (`misc.c:493-528`). `[from-comment]`

## Invariants & gotchas
- **sqlca is per-thread, never shared.** Each thread's sqlca is allocated on
  first `ECPGget_sqlca` and freed by the TLS destructor; callers must not cache a
  sqlca pointer across threads. `[verified-by-code]` (`misc.c:107-124,95-99`)
- **`pthread_once` makes key init race-free**, but note `ECPGget_sqlca`'s malloc
  failure path returns NULL silently (`misc.c:118-119`); callers
  (`ecpg_init`, `ECPGset_var`) must and do check for NULL and raise OUT_OF_MEMORY.
  `[verified-by-code]`
- **`debugstream` is whatever the caller passed to `ECPGdebug`.** ecpglib never
  opens or closes it; lifetime is the application's responsibility. Logging is
  serialized by `debug_mutex`, so the handle is safe against concurrent ecpglib
  writers — but not against the app writing the same FILE outside ecpglib. `[verified-by-code]` (`misc.c:220,267-286`)
- **Don't call `ECPGdebug` and `ecpg_log` lock-orderings backwards.** `ECPGdebug`
  takes `debug_init_mutex` then `debug_mutex`, and crucially releases
  `debug_mutex` before calling `ecpg_log` (which itself takes `debug_mutex`) — a
  nested acquire would self-deadlock on a non-recursive mutex. The release at
  `misc.c:223` is load-bearing. `[verified-by-code]`
- **The `simple_debug` fast-path read is intentionally unsynchronized** and
  relies on int-load atomicity (`misc.c:240-246`); on exotic platforms a torn
  read is theoretically possible but is the documented, accepted tradeoff. `[from-comment]`
- **NULL sentinels are in-band magic values** (`INT_MIN`, `SHRT_MIN`,
  `LONG_MIN`, all-`0xff` floats, `NUMERIC_NULL` sign): a legitimately-`INT_MIN`
  data value is indistinguishable from NULL when using indicator-less binding.
  This is by design for the no-indicator path. `[verified-by-code]` (`misc.c:291-425`)

## Cross-refs
- [[error.c]] — `ecpg_raise`/`ecpg_log` consumers; sqlca fields filled by error path
- [[connect.c]] — `ecpg_get_connection`, `struct connection`, autocommit flag used by `ECPGtrans`
- [[memory.c]] — `ECPGfree_auto_mem` called from `ECPGset_var` OOM path (`misc.c:581`)
- [[execute.c]] — primary consumer of `ECPGset_var`/`ECPGget_var` input-variable list

## Potential issues
- **[ISSUE-THREADSAFETY: unsynchronized global `ivlist`]** `misc.c:535,553-588,597`
  — `ivlist` is a process-global singly-linked list mutated by `ECPGset_var`
  (insert at head, `misc.c:587-588`) and traversed by `ECPGget_var`
  (`misc.c:597`) with no mutex. Unlike `sqlca`, this list is shared across all
  threads. Concurrent `ECPGset_var` from two threads can corrupt the list
  (lost insert / torn `next` pointer); a concurrent reader can follow a
  half-linked node. In practice ecpg input-variable registration is driven from
  generated single-thread statement sequences, so the window is narrow, but the
  data structure itself offers no thread safety where `sqlca` deliberately does.
  Low-to-medium severity (latent, depends on multithreaded use of the same
  process-global descriptor numbers). `[verified-by-code]`
- **[ISSUE-INFOLEAK: debug trace writes SQL text to caller's FILE]**
  `misc.c:168,231-289` — when `ECPGdebug(n, stream)` is enabled, `ecpg_log`
  writes statement text (e.g. transaction commands at `misc.c:168`, and via
  other ecpglib callers, full query strings) plus sqlca state to the
  application-supplied stream. This is opt-in, caller-controlled, and standard
  for a debug facility — not a vulnerability in itself — but the trace can
  contain query text and literal values; the destination FILE's permissions are
  entirely the application's responsibility. Informational only; no credential
  material is emitted by this file's own code paths. `[verified-by-code]`
