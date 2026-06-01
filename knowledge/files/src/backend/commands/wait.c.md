# wait.c

- **Source path:** `source/src/backend/commands/wait.c`
- **Lines:** 362
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/transam/xlogwait.c` (the LSN-wait primitive), `commands/wait.h`.
- **Heritage:** This file replaces the older `waitlsn.c` (PG 17 name); WAIT FOR statement debuted in PG 18.

## Purpose

"Implements WAIT FOR, which allows waiting for events such as time passing or LSN having been replayed, flushed, or written." [from-comment, wait.c:3-5]

## Public surface

- `ExecWaitStmt` — top-level entry. Parses the options (`LSN '0/123'`, `TIMEOUT n`, `NOTHROW`, `MODE replay|flush|write`), then calls `WaitForLSN` in `access/transam/xlogwait.c`. Returns a one-row result with the actual LSN reached and status.

## Use case

`WAIT FOR LSN '0/12345' TIMEOUT 5000` on a standby waits until replay (default) has reached that LSN, or until 5 seconds pass. On a primary, waits for flush. Useful for read-your-writes consistency in primary/standby setups: an application that wrote on the primary captures `pg_current_wal_lsn()` and tells the standby `WAIT FOR LSN <that>` before issuing the read.

## Not a transaction-level statement

WAIT FOR must run at top level (`isTopLevel` check at the start). It would not make sense inside a transaction because waiting for replay implies waiting for something the current xact hasn't committed yet.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
