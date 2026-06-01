# discard.c

- **Source path:** `source/src/backend/commands/discard.c`
- **Lines:** 79
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"The implementation of the DISCARD command." [from-comment, discard.c:3-4] Tiny dispatcher for `DISCARD { ALL | PLANS | SEQUENCES | TEMP }`.

## Public surface

- `DiscardCommand` — switch on the discard target.
- `DiscardAll` (static) — implements DISCARD ALL by sequencing: reset session GUCs (`ResetAllOptions`), drop all prepared statements (`DropAllPreparedStatements`), drop sequences-state (`ResetSequenceCaches`), drop temp tables (`ResetTempTableNamespace`), release advisory locks (`LockReleaseAll(USER_LOCKMETHOD, true)`), unlisten everything (`Async_UnlistenAll`).

## Why connection poolers care

Connection poolers (pgbouncer in transaction-pooling mode) issue `DISCARD ALL` between client sessions to scrub leftover state. If DISCARD ALL ever forgets a piece of session state (a new GUC class, a new advisory-lock-table, a new temp-object kind), pooled connections leak that state to the next user. So additions to backend session-local state must update `DiscardAll` here.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
