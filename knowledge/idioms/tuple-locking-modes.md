# Tuple locking modes — KEY SHARE / SHARE / NO KEY UPDATE / UPDATE

PostgreSQL supports 4 row-level lock modes that the SQL layer
exposes as `SELECT FOR KEY SHARE / FOR SHARE / FOR NO KEY UPDATE
/ FOR UPDATE`. The split between "key" and "no-key" matters for
foreign-key enforcement: updating a non-key column doesn't
conflict with a foreign-key check. The 4 modes are encoded in
the heap tuple header bits, and a per-tuple lock interaction
matrix decides whether a new locker conflicts with existing
ones.

Anchors:
- `source/src/include/access/htup_details.h:195-293` — flag
  definitions + decoder inlines [verified-by-code]
- `source/src/backend/access/heap/heapam.c` — `heap_lock_tuple`
- `knowledge/idioms/heaptuple-update-chain.md` — adjacent;
  HOT chain + lock interaction
- `.claude/skills/locking/SKILL.md` — heavyweight + row-lock
  decision tree

## The 4 modes

| Mode | SQL syntax | Conflict surface |
|---|---|---|
| KEY SHARE | `SELECT FOR KEY SHARE` | Conflicts with key updates; allows non-key SHARE/UPDATE |
| SHARE | `SELECT FOR SHARE` | Conflicts with key OR non-key updates; allows other SHARE |
| NO KEY UPDATE | `SELECT FOR NO KEY UPDATE` | Conflicts with SHARE; allows KEY SHARE |
| UPDATE | `SELECT FOR UPDATE` | Conflicts with all of the above |

The hierarchy is **strictly increasing in restrictiveness**:
KEY SHARE < SHARE < NO KEY UPDATE < UPDATE.

## The encoding bits

[verified-by-code `htup_details.h:195-293`]

Row-lock state lives in the `t_infomask` (lower) and
`t_infomask2` (upper) header bits:

| Flag | Bit | Meaning |
|---|---|---|
| `HEAP_XMAX_KEYSHR_LOCK` | infomask | KEY SHARE locked |
| `HEAP_XMAX_SHR_LOCK` | infomask | SHARE locked |
| `HEAP_XMAX_EXCL_LOCK` | infomask | EXCLUSIVE (NO KEY UPDATE / UPDATE) locked |
| `HEAP_LOCK_MASK` | infomask | union of the 3 above |
| `HEAP_XMAX_LOCK_ONLY` | infomask | xmax is a locker, NOT an updater |
| `HEAP_KEYS_UPDATED` | infomask2 | If updated, key columns changed |

The `HEAP_LOCK_MASK` is the per-bit summary
[verified-by-code `htup_details.h:202`]. The 2-bit lock-mode
field encodes 4 states (no-lock / key-share / share /
exclusive) within `infomask`.

## The KEY vs NO-KEY split

`HEAP_KEYS_UPDATED` distinguishes:

- **Key-updating UPDATE** — a column in the **replica identity**
  (or a unique index) changed. The new tuple version has a
  different identity from the old; foreign keys, RI triggers,
  logical replication care.
- **Non-key-updating UPDATE** — only non-key columns changed.
  Identity preserved; foreign keys / RI not affected.

`SELECT FOR KEY SHARE` blocks **only** key-updating UPDATEs and
DELETEs. Non-key UPDATEs proceed. This is how
foreign-key checks acquire just-enough lock without blocking
ordinary writes.

## HEAP_XMAX_LOCK_ONLY — locker vs updater

[from-comment `htup_details.h:197, 223-243`]

> A tuple is "locker only" if HEAP_XMAX_LOCK_ONLY bit is set;
> or, for pg_upgrade's sake, if the Xmax is...
> ...HEAP_XMAX_EXCL_LOCK without HEAP_XMAX_IS_MULTI.

A tuple's xmax can mean two things:

1. **The xmax transaction UPDATEd or DELETEd the tuple.** The
   tuple has a new version somewhere; chain walk follows
   `t_ctid`.
2. **The xmax transaction only LOCKED the tuple.** The tuple's
   data is unchanged; it's just held against concurrent
   modification.

`HEAP_XMAX_LOCK_ONLY` discriminates. Without it, visibility
checks assume "the xmax transaction modified the tuple."

The decoder inline `HEAP_XMAX_IS_LOCKED_ONLY(infomask)`
checks both the explicit flag AND the legacy
EXCL-without-MULTI heuristic for pg_upgrade compatibility
[verified-by-code `htup_details.h:230-234`].

## MultiXact: multiple lockers at once

If multiple transactions lock the same tuple at different
modes (KEY SHARE + KEY SHARE, SHARE + KEY SHARE, etc.), xmax
points to a **MultiXact ID** instead of a single XID.
MultiXact membership encodes the per-member lock mode.

`HEAP_XMAX_IS_MULTI` flag indicates this case. The MultiXact
machinery (see `knowledge/data-structures/multixactid.md`)
resolves the membership on visibility check.

`heap_lock_tuple` may need to allocate a new MultiXact when a
new locker arrives — wraps the existing single-locker XID +
the new XID into a fresh MultiXact ID.

## The conflict matrix

| New locker → / Existing ↓ | KEY SHARE | SHARE | NO KEY UPD | UPDATE |
|---|---|---|---|---|
| **KEY SHARE** | ✓ | ✓ | ✓ | ✗ |
| **SHARE** | ✓ | ✓ | ✗ | ✗ |
| **NO KEY UPD** | ✓ | ✗ | ✗ | ✗ |
| **UPDATE** | ✗ | ✗ | ✗ | ✗ |

✓ = both can hold; ✗ = new waits.

The asymmetry KEY SHARE vs NO KEY UPDATE is the foreign-key
optimization: an FK check on a row (which takes KEY SHARE)
doesn't block an UPDATE that changes only non-key columns
(NO KEY UPDATE). Without this split, FK-heavy schemas would
serialize all updates through their referenced rows.

## When non-key UPDATE auto-locks

A regular UPDATE statement implicitly takes:

- **NO KEY UPDATE** if no key columns are in the SET clause.
- **UPDATE** if any key column is being modified.

This is why a non-key UPDATE on a parent table doesn't block an
FK-checking child INSERT, but a key-changing UPDATE does.

`heap_update`'s logic [verified-by-code `heapam.c:3200-3300`]
computes `key_attrs` bitmapset; if any modified column is in it,
key-update path; otherwise no-key path.

## Common review-time concerns

- **Adding a new lock mode** requires updating the 2-bit
  encoding (which is full); use existing modes or design
  carefully.
- **Foreign-key-checking code paths** should use `KEY SHARE`
  not `SHARE` — picking SHARE blocks legitimate non-key
  updates.
- **MultiXact creation is expensive** — `pg_multixact/` SLRU
  reads + atomic counter bumps. Lock-heavy workloads can
  pessimize on this.
- **`HEAP_XMAX_LOCK_ONLY` MUST be checked** on chain walks —
  otherwise a locker tuple is mistaken for an updater.
- **The visibility-decision tree** is in `heapam_visibility.c`
  + `combocid.c`; changes affect chain walks AND vacuum
  decisions.

## Invariants

- **[INV-1]** Lock-mode hierarchy: KEY SHARE < SHARE
  < NO KEY UPDATE < UPDATE.
- **[INV-2]** `HEAP_KEYS_UPDATED` distinguishes key-changing
  UPDATEs.
- **[INV-3]** `HEAP_XMAX_LOCK_ONLY` distinguishes lockers
  from updaters.
- **[INV-4]** Multiple lockers → MultiXact xmax with
  per-member modes.
- **[INV-5]** Regular UPDATE auto-picks NO KEY UPDATE or
  UPDATE based on which columns changed.

## Useful greps

- All lock-mode flags:
  `grep -n 'HEAP_XMAX_KEYSHR\|HEAP_XMAX_SHR\|HEAP_XMAX_EXCL\|HEAP_LOCK_MASK' source/src/include/access/htup_details.h`
- heap_lock_tuple callers:
  `grep -RIn 'heap_lock_tuple\b' source/src/backend | head -20`
- The conflict-check function:
  `grep -n 'DoesMultiXactIdConflict\|HeapTupleSatisfiesUpdate' source/src/backend/access/heap/heapam.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | — | heap_lock_tuple |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) | 195 | flag definitions + decoder inlines |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) | — | flag definitions + decoder inlines |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/heaptuple-update-chain.md` — chain
  semantics; `HEAP_XMAX_LOCK_ONLY` is a key distinguisher.
- `knowledge/data-structures/multixactid.md` — MultiXact
  encoding for multi-locker cases.
- `knowledge/subsystems/contrib-pgrowlocks.md` — surfaces
  these locks to SQL.
- `.claude/skills/locking/SKILL.md` — heavyweight + row-lock
  decision tree.
- `knowledge/subsystems/access-heap.md` — heap_lock_tuple +
  heap_update interaction.
- `source/src/include/access/htup_details.h` — flag definitions
  + decoder inlines.
- `source/src/backend/access/heap/heapam.c` — heap_lock_tuple.
