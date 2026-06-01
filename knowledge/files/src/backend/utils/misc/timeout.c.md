# `src/backend/utils/misc/timeout.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~820
- **Source:** `source/src/backend/utils/misc/timeout.c`

Multiplexes a single `SIGALRM` source across many logical timeout reasons.
The kernel only gives us one `setitimer(ITIMER_REAL)` per process; this
module schedules N timeouts on top of it. [from-comment] (`timeout.c:1-7`)

## Mental model

- A `TimeoutId` enum lists every reason: `STATEMENT_TIMEOUT`,
  `LOCK_TIMEOUT`, `IDLE_IN_TRANSACTION_SESSION_TIMEOUT`, `DEADLOCK_TIMEOUT`,
  `STANDBY_*_TIMEOUT`, `WALSND_*_TIMEOUT`, `IDLE_STATS_UPDATE_TIMEOUT`,
  ... plus a few user-registrable slots (`USER_TIMEOUT`).
- Each entry has `(active, fin_time, indicator, callback)`. `indicator`
  is set true when the timeout fires; the callback (run in the signal
  handler) is typically tiny — sets a global volatile flag the backend
  checks at its next CHECK_FOR_INTERRUPTS.
- The handler chooses the earliest `fin_time` across all active timeouts
  as the next `setitimer` deadline. Fired timeouts are deactivated; the
  rescheduling logic walks the array and arms `setitimer` for the next.

## API

- `RegisterTimeout(id, callback)` — first-time registration.
- `enable_timeout_after(id, delay_ms)`, `enable_timeout_at(id, fin_time)`,
  `enable_timeouts(...)` — arm.
- `disable_timeout(id, keep_indicator)`, `disable_timeouts(...)`,
  `disable_all_timeouts(keep_indicator)`.
- `get_timeout_indicator(id, reset_indicator)` — has it fired?
- Signal-safe — handlers must be `pg_noinline` and only set sig-atomic
  flags. The actual error report happens later from the main loop.

## Tag tally

`[from-comment]` 2
