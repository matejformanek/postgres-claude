# Subtransaction stack — savepoint accounting

PostgreSQL implements savepoints (SQL `SAVEPOINT`, `ROLLBACK TO`,
`RELEASE`) and PL/pgSQL `BEGIN ... EXCEPTION` blocks via a stack
of nested **TransactionState** records. Each level tracks its own
XID, command-counter, ResourceOwner, snapshot stack, and
predicate-lock state. Commit/rollback of a subtransaction rolls
its state up to the parent or discards it. The stack is
backend-local; the WAL records what happened, not the stack
structure itself.

Anchors:
- `source/src/include/access/xact.h:440-484` — public API
  [verified-by-code]
- `source/src/backend/access/transam/xact.c` — `TransactionState`
  struct + push/pop machinery
- `knowledge/data-structures/resourceowner.md` — per-subxact
  ResourceOwner tied to each level
- `knowledge/subsystems/access-transam.md` — xact subsystem

## The stack model

```
TopTransactionState (depth 0)
  └─ SubTransactionState (depth 1, "SAVEPOINT s1")
      └─ SubTransactionState (depth 2, "SAVEPOINT s2")
          └─ CurrentTransactionState ◄── current
```

Each level carries:

- **Subtransaction ID** (`SubTransactionId`) — a 32-bit
  per-transaction-tree counter, NOT an XID. Allocated even when
  no XID is needed.
- **XID** — possibly `InvalidTransactionId` for read-only
  subxacts; allocated lazily when the subxact does a write.
- **ResourceOwner** — owns locks, snapshots, buffers acquired in
  this subxact level.
- **Snapshot stack** — pushed snapshots within this level.
- **Predicate-lock state** — SSI state for this level.

[verified-by-code via xact.c `TransactionStateData`]

## The 3 entry points

```c
extern SubTransactionId GetCurrentSubTransactionId(void);
extern void BeginInternalSubTransaction(const char *name);
extern void ReleaseCurrentSubTransaction(void);
extern void RollbackAndReleaseCurrentSubTransaction(void);
```

[verified-by-code `xact.h:447, 479-481`]

- **`BeginInternalSubTransaction(name)`** — push a new level. The
  name is informational (shows up in `pg_locks`, error contexts).
  Called from C code; `SAVEPOINT name` at the SQL layer calls
  it.
- **`ReleaseCurrentSubTransaction()`** — pop the current level,
  promoting its resources to the parent. SQL `RELEASE SAVEPOINT
  s` invokes this.
- **`RollbackAndReleaseCurrentSubTransaction()`** — pop, discarding
  everything done at this level. SQL `ROLLBACK TO s` (or PL/pgSQL
  EXCEPTION block) invokes this.

## What "release" actually does

A "released" subtransaction's effects are **promoted to the
parent**. Its writes become the parent's writes. Its XID (if
allocated) gets added to the parent's list of subxact XIDs. On
the top-level commit, all the surviving subxact XIDs are
recorded in the WAL commit record so recovery can correctly
identify "everyone who shares this transaction's atomic fate."

The parent doesn't "see" the subxact's writes in any
catalog-visible way before its own commit — externally, the
distinction is invisible. Internally, the per-subxact accounting
matters for VACUUM (which-xids-still-live) and SSI (which-xids-
caused-the-conflict).

## What "rollback" actually does

A rolled-back subxact:

1. Its ResourceOwner is released — locks, buffers, snapshots
   freed.
2. Its XID (if allocated) is recorded in `pg_subtrans` as
   aborted-rolled-back. Other backends checking visibility for
   this XID see "aborted."
3. Its writes are visible to NO ONE (they were always invisible
   externally; now they become invisible internally too —
   re-scans don't see them).
4. SSI's edge graph drops contributions from this XID.

The parent transaction CONTINUES. Subsequent commands run as if
the subxact never happened.

## The SubTransactionId vs XID distinction

[from-comment context throughout `xact.c`]

- **SubTransactionId** is a per-transaction-tree counter starting
  at 1. Every subxact level gets one, including read-only ones.
  Used for in-backend bookkeeping.
- **XID** (TransactionId) is the cluster-global transaction
  identifier. Allocated only when the subxact writes (and
  needs to be visible-to-other-backends-as-having-modified).
  Read-only subxacts never consume an XID.

This is why a deeply-nested transaction tree may have 100s of
levels but only handful of XIDs — only the writing ones cost.

## The TBLOCK_* states

[verified-by-code `xact.h` enums]

PostgreSQL tracks the transaction-block state with a state
machine:

- `TBLOCK_DEFAULT` — no transaction open.
- `TBLOCK_STARTED` — implicit (autocommit) transaction running.
- `TBLOCK_BEGIN` / `TBLOCK_INPROGRESS` — explicit
  `BEGIN`-started transaction.
- `TBLOCK_SUBINPROGRESS` — inside a savepoint.
- `TBLOCK_END` / `TBLOCK_ABORT` — committing / aborting.
- `TBLOCK_SUBABORT_PENDING` — subxact aborted, waiting for
  `ROLLBACK TO` / `RELEASE`.

`SAVEPOINT` legal only in `TBLOCK_INPROGRESS` or
`TBLOCK_SUBINPROGRESS`. Calling from `TBLOCK_STARTED`
auto-promotes to a real transaction.

## Common review-time concerns

- **Don't call `BeginInternalSubTransaction` outside a
  transaction.** Pre-check with `IsTransactionState()`.
- **Released subxact writes are still attributable** to the
  parent commit. If you need "this writer didn't survive",
  rollback the subxact, don't release.
- **XID allocation is lazy.** Code that needs the current XID
  must call `GetCurrentTransactionId()`, which forces
  allocation if not yet done.
- **Each subxact level adds memory + ProcArray pressure.**
  Deep PL/pgSQL exception-block nesting can hit
  `max_subtransaction_xact_blocks` (effectively unbounded but
  RAM-pressured).
- **Parallel workers don't push subxact stacks** — they
  inherit the leader's snapshot and can't create their own
  subxacts. Code that runs under parallel must check
  `IsParallelWorker()` before BeginInternal.

## The "subxact overflow" path

When a top-level transaction accumulates more than 64 child
subxact XIDs (the per-PGPROC inline-storage limit), the
overflow is tracked in `pg_subtrans` files on disk. Other
backends performing visibility checks fall through to disk
reads of `pg_subtrans`, which is slower.

Workloads with deeply-nested PL/pgSQL or long-running
transactions with many savepoints are the canonical victims;
the fix is "don't do that" — flatten the structure.

## Invariants

- **[INV-1]** Every subxact level has a `SubTransactionId`;
  XID is allocated lazily on write.
- **[INV-2]** Release promotes effects to parent; rollback
  discards.
- **[INV-3]** ResourceOwner mirrors the stack; release/rollback
  triggers cleanup.
- **[INV-4]** `pg_subtrans` overflow when >64 subxacts; disk
  reads on visibility check.
- **[INV-5]** Parallel workers cannot push subxacts; check
  `IsParallelWorker()` first.

## Useful greps

- All subxact entry points:
  `grep -RIn 'BeginInternalSubTransaction\|ReleaseCurrentSubTransaction\|RollbackAndReleaseCurrentSubTransaction' source/src/backend`
- TBLOCK_* state transitions:
  `grep -n 'TBLOCK_' source/src/backend/access/transam/xact.c | head -30`
- The TransactionStateData struct:
  `grep -A30 'typedef struct TransactionStateData' source/src/backend/access/transam/xact.c | head -35`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/subtrans.c`](../files/src/backend/access/transam/subtrans.c.md) | — | pg_subtrans SLRU |
| [`src/backend/access/transam/xact.c`](../files/src/backend/access/transam/xact.c.md) | — | TransactionState struct + push/pop machinery |
| [`src/include/access/xact.h`](../files/src/include/access/xact.h.md) | 440 | public API |
| [`src/include/access/xact.h`](../files/src/include/access/xact.h.md) | — | public API |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/data-structures/resourceowner.md` — per-subxact
  ResourceOwner; the cleanup hook on rollback / release.
- `knowledge/data-structures/snapshot-lifecycle.md` — snapshot
  stack pushed at each level.
- `knowledge/idioms/snapshot-acquisition.md` — Push/Pop semantics
  inside subxact.
- `knowledge/idioms/predicate-locks.md` — SSI predicate-lock
  state tracked per subxact.
- `.claude/skills/error-handling.md` — PL/pgSQL EXCEPTION block
  uses subxact for catching.
- `source/src/include/access/xact.h` — public API.
- `source/src/backend/access/transam/xact.c` — TransactionState
  + state machine.
- `source/src/backend/access/transam/subtrans.c` —
  `pg_subtrans` SLRU.
