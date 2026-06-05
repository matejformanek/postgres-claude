# `src/fe_utils/cancel.c`

- **File:** `source/src/fe_utils/cancel.c` (243 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Shared frontend query-cancellation machinery: lets a CLI tool (psql, pg_dump, etc.)
turn a SIGINT (Ctrl-C) into a `PQcancel()` against the in-flight query. Maintains a
single process-global `cancelConn` (`cancel.c:43`) that the signal handler reads, plus
predetermined localized message strings so the handler never has to call `gettext()`.
On Windows the same job is done by a `SetConsoleCtrlHandler` callback on a separate
thread, guarded by a `CRITICAL_SECTION` (`cancel.c:192`).

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `CancelRequested` (global) | :59 | `volatile sig_atomic_t`; set true when SIGINT received. No reset provision in-module. |
| `SetCancelConn` | :76 | Replace `cancelConn` with a fresh `PQgetCancel(conn)`; frees the old one. |
| `ResetCancelConn` | :106 | Free `cancelConn` and set NULL. |
| `setup_cancel_handler` | :182 (Unix) / :231 (Win32) | Register SIGINT handler (or console handler) + cache message strings + optional callback. |

## Internal landmarks

- `write_stderr(str)` macro `cancel.c:31-37` — signal-safe `write(2)` to stderr; deliberately
  ignores the result. Used instead of `fprintf`/`stdio` inside the handler. `[from-comment]` (:27-29)
- `cancelConn` `cancel.c:43` — `static PGcancel *volatile`. The `volatile` keeps the signal
  handler from caching a stale pointer. `[verified-by-code]`
- `cancel_sent_msg` / `cancel_not_sent_msg` `cancel.c:49-50` — pre-translated via `_()` at
  `setup_cancel_handler` time so the handler avoids `gettext()`. `[from-comment]` (:46-48)
- `cancel_callback` `cancel.c:68` — optional extra hook fired from the handler (e.g. psql uses it). `[verified-by-code]`
- `handle_sigint` `cancel.c:152-175` — sets `CancelRequested`, runs `cancel_callback`, and if
  `cancelConn != NULL` calls `PQcancel()` straight from the handler. Comment at `:130-135`
  asserts this is safe because `PQcancel()` is written to be signal-safe (unlike the older
  `PQrequestCancel`). `[from-comment]`
- The `SetCancelConn`/`ResetCancelConn` swap idiom `cancel.c:86-92`, `:115-121`: read old pointer,
  null `cancelConn` *first*, then free the old one — so the handler can never see a pointer
  that is mid-free. `[from-comment]` (:88, :117)
- Win32 `consoleHandler` `cancel.c:194-229` — same logic on a separate thread; `cancelConnLock`
  `CRITICAL_SECTION` (`:62`) serializes against `SetCancelConn`/`ResetCancelConn`. `[verified-by-code]`

## Invariants & gotchas

- **Async-signal-safety of `handle_sigint`:** the body only does (a) plain assignments to a
  `sig_atomic_t`, (b) an indirect call through `cancel_callback`, (c) `PQcancel()`, and (d)
  `write()`. `PQcancel` is documented signal-safe; `write` is async-signal-safe. The *risk* is
  `cancel_callback` — safety depends entirely on what the application registers. `[inferred]`
- **`cancelConn` mutation race (non-Win32):** on Unix there is no lock around `cancelConn`
  on the main-thread side; correctness relies on the null-then-free ordering plus the fact
  that the handler runs on the same thread that is between syscalls. Win32 needs the explicit
  CRITICAL_SECTION because the handler runs on a *different* thread. `[inferred]`
- **Memory:** `PGcancel` objects come from `PQgetCancel` and are released with `PQfreeCancel`
  — libpq-owned, not `pg_malloc`. No leak as long as every `SetCancelConn` is balanced by a
  later `SetCancelConn`/`ResetCancelConn`. `[verified-by-code]` (:92, :121)
- `CancelRequested` is never auto-reset; the comment notes applications may clear it after a
  recovered cancel. `[from-comment]` (:54-58)
- No secrets pass through this file — `PGcancel` carries the cancel key, not the password.

## Cross-references

- `knowledge/files/src/fe_utils/connect_utils.c.md` — `disconnectDatabase` uses the newer
  `PQcancelCreate`/`PQcancelBlocking` API rather than this signal-path `PQcancel`.
- libpq cancel internals: `source/src/interfaces/libpq/fe-cancel.c` (`PQcancel`, `PQgetCancel`).
- `source/src/include/fe_utils/cancel.h` — declares these symbols.

## Confidence tag tally

- `[verified-by-code]` × 5
- `[from-comment]` × 4
- `[inferred]` × 2
