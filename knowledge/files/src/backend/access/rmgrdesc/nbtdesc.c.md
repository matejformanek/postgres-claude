---
path: src/backend/access/rmgrdesc/nbtdesc.c
anchor_sha: 4b0bf0788b0
loc: 254
depth: deep
---

# nbtdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/nbtdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 254

## Purpose

rmgr descriptor routines for the nbtree resource manager (`RM_BTREE_ID`,
record types defined in `access/nbtree/nbtxlog.c` /
`access/nbtxlog.h`). Renders the 15 btree WAL opcodes into the
human-readable text `pg_waldump` shows and feeds
`pg_get_wal_resource_managers()`. The most complex of the index
descriptors because of the packed delete/vacuum offset+update arrays.
[from-comment, nbtdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `btree_desc(buf, record)` | `nbtdesc.c:23` | render one btree record's payload |
| `btree_identify(info)` | `nbtdesc.c:138` | opcode → short name |

## Internal landmarks

- **`delvacuum_desc` (nbtdesc.c:195)** — static helper shared by the
  `XLOG_BTREE_VACUUM` (nbtdesc.c:58) and `XLOG_BTREE_DELETE`
  (nbtdesc.c:70) cases. Decodes the block-0 data, which is a packed
  layout: a `deletedoffsets[ndeleted]` array, then an
  `updatedoffsets[nupdated]` array, then a variable run of
  `xl_btree_update` objects (each followed by its `ndeletedtids`
  `uint16` posting-list TID indexes). The pointer arithmetic at
  nbtdesc.c:216-251 is the definitive spec of that on-disk run.
- **`XLOG_BTREE_SPLIT_L` / `_SPLIT_R` (nbtdesc.c:41)** dump
  `level / firstrightoff / newitemoff / postingoff` — the four numbers
  that reconstruct where the split landed and whether a posting tuple
  was involved.
- **`XLOG_BTREE_UNLINK_PAGE[_META]` (nbtdesc.c:92)** prints the
  `safexid` as an `Epoch:Xid` pair via `EpochFromFullTransactionId` /
  `XidFromFullTransactionId` — the GlobalVisState horizon that gates
  page reuse on standbys.

## Invariants & gotchas

- **Array data is only present when the page was not a full-page
  image.** Both array-bearing cases guard with
  `if (XLogRecHasBlockData(record, 0))` (nbtdesc.c:65, 79) before
  calling `delvacuum_desc`; an FPI carries no separate block data.
- **`XLOG_BTREE_META_CLEANUP` reads block-0 data unconditionally**
  (nbtdesc.c:129) — it casts `XLogRecGetBlockData(...,0)` straight to
  `xl_btree_metadata` with no `HasBlockData` guard, because that record
  always registers block 0 with the metapage delta. A malformed record
  here would dereference whatever the cast lands on.
- **`btree_desc` has no `default:`** — an unknown opcode yields an empty
  description rather than an error (the same convention as the other
  index descs). `btree_identify` likewise returns `NULL` for unknowns,
  which `pg_waldump` renders as `UNKNOWN`.
- **`delvacuum_desc` walks the update run by stride**
  `SizeOfBtreeUpdate + ndeletedtids * sizeof(uint16)` (nbtdesc.c:249) —
  it trusts `ndeletedtids` from the record; the two `Assert`s
  (nbtdesc.c:225-226) only fire in assert-enabled builds.

## Cross-refs

- Record structs + `XLOG_BTREE_*` opcodes: `[[src/include/access/nbtxlog.h]]`.
- Array-rendering helpers (`array_desc`, `offset_elem_desc`):
  `[[src/backend/access/rmgrdesc/rmgrdesc_utils.c]]`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
- Companion WAL skill: `.claude/skills/wal-and-xlog/SKILL.md` §6.
