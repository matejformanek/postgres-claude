# MultiXactId — packed multi-transaction lock identity

- **Source path:** `source/src/include/access/multixact.h`,
  `source/src/backend/access/transam/multixact.c`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Companion docs:** `knowledge/subsystems/access-transam.md`,
  `knowledge/data-structures/heap-tuple-layout.md`,
  `knowledge/subsystems/access-heap.md`, `.claude/skills/locking/SKILL.md` §2.6

## 1. What it is

A `MultiXactId` is a single 32-bit id that **packs the identities of
multiple transactions** along with their **lock modes** on a single row.
When more than one session needs a non-conflicting lock on the same
tuple simultaneously, the tuple's `xmax` becomes a MultiXactId; the
real member xids + their modes live in a separate SLRU.

```c
typedef MultiXactId TransactionId;             /* same width as xid */

#define InvalidMultiXactId  ((MultiXactId) 0)
#define FirstMultiXactId    ((MultiXactId) 1)
#define MaxMultiXactId      ((MultiXactId) 0xFFFFFFFF)
```

[verified-by-code `source/src/include/access/multixact.h:25-30`]

A multixact is keyed by ascending allocation order, two SLRUs back the
data:

- `pg_multixact/offsets/` — one entry per multixact id giving the
  offset into `members/` and the number of members.
- `pg_multixact/members/` — variable-length blob of `MultiXactMember`
  records.

`pg_multixact/` is on-disk persistent state — it survives crashes and
participates in `pg_upgrade`.

## 2. Member representation

Each member is one xid + one lock mode:

```c
typedef struct MultiXactMember {
    TransactionId xid;
    MultiXactStatus status;
} MultiXactMember;
```

[verified-by-code `source/src/include/access/multixact.h:53-58`]

The six lock modes (`MultiXactStatus` enum,
`source/src/include/access/multixact.h:36-46`):

| Value | Name | Meaning |
|---|---|---|
| `0x00` | `MultiXactStatusForKeyShare` | `FOR KEY SHARE` row lock |
| `0x01` | `MultiXactStatusForShare` | `FOR SHARE` row lock |
| `0x02` | `MultiXactStatusForNoKeyUpdate` | `FOR NO KEY UPDATE` row lock |
| `0x03` | `MultiXactStatusForUpdate` | `FOR UPDATE` row lock |
| `0x04` | `MultiXactStatusNoKeyUpdate` | actual non-key-touching update |
| `0x05` | `MultiXactStatusUpdate` | actual update / delete |

`ISUPDATE_from_mxstatus(status)` is the macro for "is this an update,
not a lock?" (status > `MultiXactStatusForUpdate`).
[verified-by-code `multixact.h:50-52`]

## 3. When `xmax` is a MultiXactId vs a plain xid

A heap tuple's `xmax` field is a `TransactionId`. Two infobits tell
how to interpret it:

- `HEAP_XMAX_IS_MULTI` set → `xmax` is a `MultiXactId`; resolve with
  `GetMultiXactIdMembers(xmax, &members, ...)`.
- `HEAP_XMAX_IS_MULTI` unset → `xmax` is a plain xid (the locker / updater).

**[INV-1] Forgetting to check `HEAP_XMAX_IS_MULTI`** before treating
`xmax` as a plain xid is the classic "I checked xmax but the row was
still locked" bug. Every heap-touching path must dispatch on this bit
first.

## 4. Lifecycle — allocation, members lookup, freeze

### Allocation

`MultiXactIdCreate(xid1, status1, xid2, status2)` and
`MultiXactIdExpand(multi, xid, status)` allocate fresh multixacts
when two or more sessions want to lock the same row in non-conflicting
modes (or when a session wants to escalate / piggyback on an existing
multi).

### Member lookup

`GetMultiXactIdMembers(multi, &members, allow_old_xact, false)`
returns the count + a `palloc`'d array of `MultiXactMember`. Caller
walks the array.

**[INV-2]** Don't call `GetMultiXactIdMembers` while holding a
spinlock. Member resolution may need SLRU page I/O.

### Freeze

`pg_multixact/` is bounded by `multixact_freeze_*` parameters
(GUCs `vacuum_multixact_freeze_min_age`,
`vacuum_multixact_freeze_table_age`, `autovacuum_multixact_freeze_max_age`).
Vacuum removes multixacts whose members are all committed and old
enough; the `relminmxid` per-relation marker tracks the oldest
multixact a relation's tuples can reference.

`relminmxid` advancing is a vacuum responsibility; falling behind
risks the cluster running out of multixact id space ("multixact
wraparound") — same family of problems as xid wraparound.

## 5. Cross-version interaction — `MultiXactStatus` upgrades

Older PG versions had fewer status codes. A tuple frozen long ago
may carry an interpretation that wasn't a status at the time. The
freeze path normalizes these.

When introducing a new `MultiXactStatus` value: **must** bump
`CATALOG_VERSION_NO` and write a freeze-path patch for older
clusters' multixacts — the on-disk multixact-members SLRU survives
`pg_upgrade`.

## 6. Hot-standby

Hot Standby **cannot create new MultiXactId members.** Row-level
lock requests on a hot-standby fall through to a no-op there. This is
a well-known limitation, not a bug. The standby relays multixact
operations from the primary's WAL but doesn't allocate its own.

## 7. WAL records

[verified-by-code `multixact.h:64-68`]

- `XLOG_MULTIXACT_ZERO_OFF_PAGE` (0x00)
- `XLOG_MULTIXACT_ZERO_MEM_PAGE` (0x10)
- `XLOG_MULTIXACT_CREATE_ID` (0x20) — allocate a fresh multi
- `XLOG_MULTIXACT_TRUNCATE_ID` (0x30) — vacuum advances bounds

These are decoded into `comparison.md`-style descriptions by
`source/src/backend/access/rmgrdesc/multixactdesc.c`.

## 8. SLRU layout

The two SLRUs:

- **Offsets SLRU**: 4 bytes per multixact id → offset into Members SLRU
  + member count. Page size = `BLCKSZ` (8 KB), so ~2048 multis per page.
- **Members SLRU**: variable per multi (8 bytes per member: xid + status
  bits packed).

SLRU pages are in shared memory; misses cause synchronous disk reads
into the SLRU buffer pool. The relevant LWLocks:
`MultiXactOffsetSLRULock`, `MultiXactMemberSLRULock`,
`MultiXactGenLock`, `MultiXactTruncationLock` (see
`source/src/include/storage/lwlocknames.h`).

## 9. Invariants

- **[INV-1]** Check `HEAP_XMAX_IS_MULTI` before treating `xmax` as a
  plain xid.
- **[INV-2]** Don't call `GetMultiXactIdMembers` while holding a
  spinlock (SLRU I/O possible).
- **[INV-3]** `pg_multixact/` files survive `pg_upgrade` and must be
  readable by every supported back-version code path.
- **[INV-4]** New `MultiXactStatus` values require freeze-path
  patches for old multixacts already on disk.
- **[INV-5]** Hot-standby NEVER allocates multixacts; row-locks on
  standby are no-ops.

## 10. Useful greps

- All multixact creations:
  `grep -RIn 'MultiXactIdCreate\|MultiXactIdExpand' source/src/backend/access/heap`
- Members consumers:
  `grep -RIn 'GetMultiXactIdMembers' source/src/backend`
- Status enum changes (cross-version migration risk):
  `git -C source log -S 'MultiXactStatus' --oneline`

## Cross-references

- `.claude/skills/locking/SKILL.md` §2.6 — MultiXact interaction with tuple locks; HEAP_XMAX_IS_MULTI dispatch rule.
- `.claude/skills/wal-and-xlog/SKILL.md` — XLOG_MULTIXACT_* records; replay rules.
- `.claude/skills/access-method-apis/SKILL.md` — heapam tuple_lock callback consumes MultiXactId.
- `knowledge/data-structures/heap-tuple-layout.md` — `xmax` field bit-layout, infomask bits.
- `knowledge/subsystems/access-transam.md` — the surrounding xact / xid infrastructure.
- `knowledge/subsystems/access-heap.md` — tuple-lock path that allocates / consumes multixacts.
- `source/src/backend/access/heap/README.tuplock` — canonical tuple-lock + multixact discussion.
