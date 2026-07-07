# BufferTag — buffer-cache identity key

`BufferTag` is the 5-field identifier PostgreSQL uses to name a
disk page inside the shared buffer cache. Every entry in the
shared `BufferDesc` array carries one; the buffer-mapping hash
table uses it as the key. Pure value type — no pointers, no
allocations, sized to be a cheap hash-key.

Anchors:
- `source/src/include/storage/buf_internals.h:161-168` — the
  struct definition [verified-by-code]
- `source/src/include/storage/buf_internals.h:170-238` — the
  helper inlines (Init / Get / Equal / Match)
- `knowledge/subsystems/storage-buffer.md` — the buffer manager
  that owns this struct
- `knowledge/data-structures/bufferdesc-state.md` — the
  partner state field on each buffer

## Definition

```c
typedef struct buftag
{
    Oid           spcOid;       /* tablespace oid */
    Oid           dbOid;        /* database oid */
    RelFileNumber relNumber;    /* relation file number */
    ForkNumber    forkNum;      /* fork number */
    BlockNumber   blockNum;     /* blknum relative to begin of reln */
} BufferTag;
```

[verified-by-code `buf_internals.h:161-168`]

Five fields: tablespace, database, relation-file-number, fork
(main / vm / fsm / init), and block number. Together they
uniquely identify any 8KB page across the entire cluster.

## Why these five fields (and not pg_class.oid)?

[from-comment `buf_internals.h:152-156`]

> Note: the BufferTag data must be sufficient to determine where
> to write the block, **without reference to pg_class or
> pg_tablespace entries**. It's possible that the backend
> flushing the buffer doesn't even believe the relation is
> visible yet (its xact may have started before the xact that
> created the rel). The storage manager must be able to cope
> anyway.

The crucial constraint: the buffer cache must work without
catalog lookups. Backends evict and flush dirty pages even when
the page belongs to a relation they can't see in their MVCC
snapshot. So the tag references the **file-level** identity
(`RelFileNumber`), not the **logical-relation** identity
(`pg_class.oid`).

The `RelFileNumber` is what the smgr layer uses to construct
the on-disk filename. After a rewrite-rewriting DDL (REINDEX,
CLUSTER, VACUUM FULL), the same `pg_class.oid` gets a new
`RelFileNumber`, so old BufferTags become stale and are evicted
naturally.

## The padding rule

[from-comment `buf_internals.h:158-159`]

> if there's any pad bytes in the struct, `InitBufferTag` will
> have to be fixed to zero them, since this struct is used as a
> hash key.

Padding bytes hold whatever-was-in-memory; an unzeroed pad byte
makes two logically-equal tags compare unequal at the byte
level. The current layout has no pad bytes on common
architectures, but if a field is added, the order matters.

## Helper inlines

[verified-by-code `buf_internals.h:170-238`]

| Inline | Purpose |
|---|---|
| `BufTagGetRelNumber(tag)` | Extract `relNumber` |
| `BufTagGetForkNum(tag)` | Extract `forkNum` |
| `BufTagSetRelForkDetails(tag, rel, fork)` | Set both atomically |
| `BufTagGetRelFileLocator(tag)` | Construct a full `RelFileLocator` |
| `ClearBufferTag(tag)` | Set to invalid (the "empty slot" pattern) |
| `InitBufferTag(tag, rl, fork, blk)` | Fill from a locator + fork + block |
| `BufferTagsEqual(t1, t2)` | Field-by-field equality |
| `BufTagMatchesRelFileLocator(tag, rl)` | All fields except fork+block |

Direct field access is permitted but discouraged — use the
inlines so that future tag-layout changes don't break call
sites.

## The buffer-mapping hash table

Buffers live in two tables:

- `BufferDesc[]` — fixed-size array indexed by buffer ID; the
  raw slots.
- A hash table keyed on `BufferTag` → buffer ID. This is
  partitioned (`NUM_BUFFER_PARTITIONS`, power-of-2) for
  contention reduction.

The partition for a tag:

```c
BufTableHashCode(tag) → uint32
BufMappingPartitionLock(hashcode) → LWLock partition
```

[verified-by-code `buf_internals.h:241-249` partition header comment]

`NUM_BUFFER_PARTITIONS` must be a power of 2; the hash partition
is `hashcode & (NUM_BUFFER_PARTITIONS - 1)`.

## Cleared / "empty slot" semantics

`ClearBufferTag(tag)` sets all fields to their `Invalid*`
constants:
- `spcOid = InvalidOid` (0)
- `dbOid = InvalidOid` (0)
- `relNumber = InvalidRelFileNumber` (0)
- `forkNum = InvalidForkNumber` (-1)
- `blockNum = InvalidBlockNumber` (0xFFFFFFFF)

A cleared tag is "no relation"; `BM_TAG_VALID` in the
companion `buf_state` reflects this — the tag is meaningful
only when that flag is set.

## Why fork number matters

The `forkNum` field discriminates the 4 forks of a relation:
- `MAIN_FORKNUM` — the heap / index data.
- `FSM_FORKNUM` — Free Space Map.
- `VISIBILITYMAP_FORKNUM` — VM bits (heap only).
- `INIT_FORKNUM` — for unlogged relations, the "after-crash
  reset" template.

Same `(spcOid, dbOid, relNumber, blockNum)` but different fork
= different page. A buffer-cache hit on the wrong fork is one
of the subtle bugs the tag prevents.

## Common review-time concerns

- **Don't compare with `memcmp` if padding might exist.** Use
  `BufferTagsEqual`. Even if the current layout has no pad,
  future-you adding a field could break this assumption.
- **`InitBufferTag` zeroes pad if any.** Always go through it
  for new-buffer initialization; never compose tags ad-hoc.
- **`RelFileLocator` is the constructor source.** Don't try to
  build a tag without one — the per-field-set inlines are for
  surgical mutation of existing tags only.
- **Don't cache `BufferTag` across DDL boundaries.** A REINDEX
  / VACUUM FULL invalidates the `relNumber`; any cached tag is
  stale.

## Invariants

- **[INV-1]** All 5 fields together uniquely identify a disk
  page; no two distinct pages share a tag.
- **[INV-2]** Cleared tag (all `Invalid*`) means "no relation";
  the slot's `BM_TAG_VALID` flag MUST be off.
- **[INV-3]** The struct must have no padding bytes; if a
  field is added, `InitBufferTag` MUST zero any new pad.
- **[INV-4]** The tag is the buffer-mapping hash key; equal
  tags MUST hash to the same partition.
- **[INV-5]** Tag uses `RelFileNumber`, NOT `pg_class.oid` —
  catalog visibility is irrelevant to flush correctness.

## Useful greps

- All BufferTag readers/writers:
  `grep -RIn 'BufferTag\b' source/src/backend/storage/buffer | head -30`
- Hash-table partition usage:
  `grep -n 'BufTableHashCode\|BufMappingPartitionLock' source/src/backend/storage/buffer/buf_table.c`
- All tag-mutating call sites:
  `grep -RIn 'InitBufferTag\|ClearBufferTag\|BufTagSetRelForkDetails' source/src/backend`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/buffer/buf_table.c`](../files/src/backend/storage/buffer/buf_table.c.md) | — | buffer mapping hashtable implementation |
| [`src/backend/storage/buffer/bufmgr.c`](../files/src/backend/storage/buffer/bufmgr.c.md) | — | primary consumer (every read / write) |
| [`src/include/storage/buf_internals.h`](../files/src/include/storage/buf_internals.h.md) | 161 | the struct definition |
| [`src/include/storage/buf_internals.h`](../files/src/include/storage/buf_internals.h.md) | 170 | the helper inlines (Init / Get / Equal / Match) |
| [`src/include/storage/buf_internals.h`](../files/src/include/storage/buf_internals.h.md) | — | definition + helper inlines |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/subsystems/storage-buffer.md` — the buffer manager
  uses this tag as the hash key.
- `knowledge/data-structures/bufferdesc-state.md` — the partner
  state field; `BM_TAG_VALID` gates tag interpretation.
- `.claude/skills/locking/SKILL.md` — buffer-mapping partition
  locks; this tag determines which partition.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL records reference
  `RelFileLocator` + block (same fields as the tag minus fork).
- `source/src/backend/storage/buffer/buf_table.c` — the buffer
  mapping hashtable implementation.
- `source/src/backend/storage/buffer/bufmgr.c` — primary
  consumer (every read / write).
- `source/src/include/storage/buf_internals.h` — definition +
  helper inlines.
