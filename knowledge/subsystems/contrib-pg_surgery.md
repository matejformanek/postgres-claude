# contrib-pg_surgery (dangerous heap manipulation)

- **Source path:** `source/contrib/pg_surgery/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `pg_surgery.control`)
- **Trusted:** **no** (superuser-only by default; per-function
  REVOKE FROM PUBLIC)

## 1. Purpose

**Forcibly modify heap tuple visibility** when corruption has
created a state that VACUUM can't repair: a tuple whose xmin
is from a transaction the clog has lost, an
HEAP_XMAX_COMMITTED tuple whose xmax actually aborted, etc.
Two operations:

- **`heap_force_kill(rel, tids[])`** — mark each TID as
  unused (effectively a forced DELETE without WAL semantics
  that VACUUM would normally emit).
- **`heap_force_freeze(rel, tids[])`** — set xmin to
  FrozenTransactionId and xmax to InvalidTransactionId,
  forcing the tuple to appear live to all transactions.

This is the **emergency surgery** extension. Every documented
use is a corruption-recovery scenario. **Misuse produces
silent data corruption** — there's no recoverable backup once
you've forced a tuple's visibility.

## 2. SQL surface

```sql
SELECT heap_force_kill('mytable', ARRAY['(5,1)'::tid, '(5,3)'::tid]);
SELECT heap_force_freeze('mytable', ARRAY['(7,2)'::tid]);
```

[verified-by-code `heap_surgery.c:38-39, 58, 73`]

Both functions take a relation OID + an array of TIDs. They
walk the array, modify each tuple in-place, emit a WAL record
for the modification, and return void.

## 3. The shared implementation

```c
static Datum
heap_force_common(FunctionCallInfo fcinfo,
                  HeapTupleForceOption heap_force_opt);
```

[verified-by-code `heap_surgery.c:42-43, 85`]

Both entry points delegate to `heap_force_common`, which:

1. Open the heap with `RowExclusiveLock`.
2. For each TID in the array:
   - Pin the buffer, take content-lock-exclusive.
   - Find the line pointer.
   - For `HEAP_FORCE_KILL`: clear the line pointer, decrement
     live-tuple count.
   - For `HEAP_FORCE_FREEZE`: set xmin = FrozenTransactionId,
     clear HEAP_XMAX_*, mark all bits FROZEN.
   - WAL-log the change (so replicas see it too).
3. Release locks; close the relation.

## 4. The all-visible interaction

[verified-by-code `heap_surgery.c:239`]

```c
if (heap_force_opt == HEAP_FORCE_KILL && PageIsAllVisible(page))
```

Force-killing a tuple on an all-visible page is a special case
— the page's PD_ALL_VISIBLE flag must be cleared, and the
visibility-map bit must be cleared too. `heap_force_common`
handles this; you don't have to think about it as a caller.
But it's a reminder that even surgery has to be "consistent"
with surrounding state.

## 5. Production-use guidance — the rules

The extension's README is famously stern. Paraphrasing:

- **Take a backup first.** This is the one extension that can
  silently break a database. Once you've forced a tuple's
  visibility, there's no UNDO.
- **Test on a copy.** Restore the corrupt cluster onto a
  test machine. Verify the surgery on the test instance
  before touching production.
- **Verify the diagnosis** with `amcheck` + `pg_visibility`.
  If you don't have a corruption indicator from another
  tool, you have no reason to be running this.
- **Force-freeze is for "this tuple should be live but xmin
  isn't reachable."** Force-kill is for "this tuple is
  silently invisible due to xmax bit corruption."
- **Don't run on indexes.** Force-kill on a heap tuple
  leaves the index entries dangling — you must also
  REINDEX the affected indexes.

## 6. WAL & replication semantics

Both operations emit a standard heap WAL record:
- `heap_force_kill` emits an `XLOG_HEAP_DELETE`-shaped record.
- `heap_force_freeze` emits an `XLOG_HEAP_VISIBLE` /
  `XLOG_HEAP_INPLACE` shaped record.

So replicas see the same surgery. The result is consistent
on standbys, just as forced.

## 7. Permission model

The extension's SQL grants:

```sql
REVOKE EXECUTE ON FUNCTION heap_force_kill(regclass, tid[]) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION heap_force_freeze(regclass, tid[]) FROM PUBLIC;
```

Effectively superuser-only by default. Granting EXECUTE to
non-superusers is documented as "consider whether you want
them able to delete arbitrary data." Most production
deployments don't grant it at all; surgery is a
DBA-only operation done in single-user mode.

## 8. Invariants

- **[INV-1]** Both functions are PARALLEL UNSAFE — they hold
  per-page locks during the loop.
- **[INV-2]** Force-kill clears PD_ALL_VISIBLE and the VM
  bit; force-freeze sets HEAP_XMIN_FROZEN.
- **[INV-3]** WAL records are emitted; replicas observe the
  surgery.
- **[INV-4]** Indexes are NOT updated; caller must REINDEX
  affected indexes after force-kill.
- **[INV-5]** Force-freeze on a tuple with non-zero
  HEAP_XMAX_LOCK_ONLY bit is undefined — surgery is on
  visibility bits only, not lock states.

## 9. Useful greps

- The two entry points:
  `grep -n 'heap_force_kill\|heap_force_freeze' source/contrib/pg_surgery/heap_surgery.c`
- Per-tuple processing:
  `grep -n 'HEAP_FORCE_KILL\|HEAP_FORCE_FREEZE' source/contrib/pg_surgery/heap_surgery.c`

## 10. Cross-references

- `knowledge/subsystems/contrib-amcheck.md` — diagnoses
  the corruption that motivates surgery.
- `knowledge/subsystems/contrib-pg_visibility.md` — companion
  diagnostic; `pg_check_frozen` / `pg_check_visible` reports
  the violations surgery would address.
- `knowledge/subsystems/access-heap.md` — heap layout +
  HEAP_XMIN_FROZEN, HEAP_XMAX_INVALID semantics.
- `knowledge/idioms/heaptuple-update-chain.md` — chain
  bits that surgery does NOT touch.
- `.claude/skills/debugging/SKILL.md` — surgery is the
  last-resort tool after amcheck + pg_visibility confirm
  corruption.
- `source/contrib/pg_surgery/heap_surgery.c` — implementation.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/pg_surgery/heap_surgery.c`](../files/contrib/pg_surgery/heap_surgery.c.md) |

<!-- /files-owned:auto -->
