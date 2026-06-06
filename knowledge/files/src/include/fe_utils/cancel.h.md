---
path: src/include/fe_utils/cancel.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 32
depth: read
---

# `src/include/fe_utils/cancel.h`

- **File:** `source/src/include/fe_utils/cancel.h` (32 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Declares the frontend query-cancellation support: the `CancelRequested` flag (set from the
SIGINT handler), the functions to register/clear which `PGconn` a Ctrl-C should cancel, and
the installer for the signal handler plus an optional user callback. Implementation in
[[knowledge/files/src/fe_utils/cancel.c]]. `[from-comment]` (:1-12)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `CancelRequested` | :21 | `volatile sig_atomic_t` global: set true when a cancel was requested. |
| `SetCancelConn` | :23 | Designate the connection that Ctrl-C should send a cancel request to. |
| `ResetCancelConn` | :24 | Clear the designated connection (after a command completes). |
| `setup_cancel_handler` | :30 | Install the SIGINT handler + an optional `query_cancel_callback`. |

## Internal landmarks

- `CancelRequested` (`:21`) is the public, `volatile sig_atomic_t` flag tools poll in their row
  loops to abort cooperatively; it is the signal-safe half of the cancel mechanism, set inside
  the handler that `setup_cancel_handler` installs. `[verified-by-code]`
- `SetCancelConn`/`ResetCancelConn` (`:23-24`) bracket each command: the handler can only send
  a cancel to the *currently registered* connection, so a tool sets it before issuing a query
  and resets it after, to avoid cancelling the wrong (or a closed) connection. `[inferred]`
- `setup_cancel_handler`'s optional `query_cancel_callback` (`:30`) lets a tool run extra
  cleanup at cancel time beyond sending the libpq cancel request. `[from-comment]` (:26-29)

## Invariants & gotchas

- Everything reachable from the signal handler must be async-signal-safe; `CancelRequested` is
  `volatile sig_atomic_t` precisely so the handler can set it and the main loop can read it
  without a lock. The actual cancel request to the backend is sent from the handler against the
  registered conn (not from the main loop). `[verified-by-code]`
- Note `print.h` separately exports a similar `cancel_pressed` flag (`print.h:198`) used by the
  formatter; the two flags live in different headers and serve the formatter vs the command
  loop respectively — don't conflate them. `[verified-by-code]`

## Cross-refs

- Implementation: [[knowledge/files/src/fe_utils/cancel.c]].
- The formatter's separate cancel flag: [[knowledge/files/src/include/fe_utils/print.h]] (`cancel_pressed`).

## Potential issues

None — small, correct signal-safe cancellation surface. The only subtlety (two distinct cancel
flags across `cancel.h` and `print.h`) is noted above for future readers.
