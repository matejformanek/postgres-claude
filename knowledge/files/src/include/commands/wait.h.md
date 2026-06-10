# src/include/commands/wait.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 23 [verified-by-code]

## Role

PG18+ `WAIT` SQL statement — synchronous wait for some condition (the
exact semantics are defined in the CF / commit log; header is bare).
Tiny header exposing the executor entry point and result-descriptor.

## Public API

- `ExecWaitStmt(ParseState *pstate, WaitStmt *stmt, bool isTopLevel,
  DestReceiver *dest)` (`:19-20`).
- `WaitStmtResultDesc(WaitStmt *stmt) -> TupleDesc` (`:21`) — used by
  the portal layer to set up the result tupledesc before execution.

## Invariants

- INV-WAIT-DEST: `dest` may receive rows (the WAIT statement returns a
  result set — hence the TupleDesc accessor); the DestReceiver is
  initialized by the caller (portal code).
- `isTopLevel` — gates use inside a transaction block (likely
  forbidden for "fully synchronous" waits, by analogy with VACUUM).
  Verify against `pgsql-hackers` thread that landed the feature.

## Trust boundary / Phase D surface

- **PG18 new feature — limited fuzz exposure.** WAIT semantics not yet
  battle-tested. If the wait condition can reference shared resources
  (LSN, replication slot, named-event), the implementation may hold
  process-level state that an attacker can interrogate via crafted
  long waits (DoS).
- **DoS surface.** A non-privileged user issuing `WAIT` with a
  pathological condition could pin a backend indefinitely. Whether
  `statement_timeout` interrupts cleanly needs verification (CFR
  the implementation in `backend/commands/wait.c`).

## Cross-references

- `nodes/parsenodes.h` — `WaitStmt` parse node.
- `tcop/dest.h` — `DestReceiver` interface.
- `parser/parse_node.h` — `ParseState`.

## Issues / drift

- `[ISSUE-DOC: header is bare 3 prototypes — no semantic description of WAIT's wait condition family or interruption rules (medium)] — source/src/include/commands/wait.h:14-22`
- `[ISSUE-TRUST: PG18 new — no documented privilege gate; non-superuser DoS surface needs review (medium)] — source/src/include/commands/wait.h:19-20`
