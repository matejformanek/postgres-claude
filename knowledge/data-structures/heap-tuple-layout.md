# HeapTuple — on-disk and in-memory layouts

- **Source path:** `source/src/include/access/htup.h`, `htup_details.h`
- **Last verified commit:** `e18b0cb7344` (cites re-anchored 2026-06-12 by
  pg-quality-auditor; previously `ef6a95c7c64`)
- **Companion docs:** `knowledge/files/src/include/access/htup.h.md`,
  `knowledge/files/src/include/access/htup_details.h.md`,
  `knowledge/files/src/backend/access/heap/heapam.c.md`

## 1. Two layers

The word "tuple" gets used for two different things and confusing them is the
single biggest source of bugs in new heap code:

- **`HeapTupleHeaderData`** — the on-disk header. Always followed in memory
  by a null bitmap (optional) + an OID (optional, legacy) + the actual user
  data. This is what's stored on a heap page. Defined in `htup_details.h`.
  [verified-by-code source/src/include/access/htup_details.h:153]

- **`HeapTupleData`** — a thin in-memory wrapper. Carries the TID
  (`t_self`), the heap relation's OID (`t_tableOid`), a length (`t_len`),
  and a pointer to the on-disk `HeapTupleHeaderData` (`t_data`). Defined in
  `htup.h`. [verified-by-code source/src/include/access/htup.h:62]

When you see `HeapTuple` (capital H) you're usually working with the wrapper.
When you see `HeapTupleHeader` you're looking at the actual storage.

## 2. HeapTupleHeader bit layout

```
                            offset    size
t_xmin                          0       4    inserting xact xid
t_xmax                          4       4    deleting/locking xact xid (or 0)
t_cid / t_xvac (union)          8       4    command id of inserter (cmin in
                                              the standard case) OR vac-full xid
t_ctid                         12       6    pointer to next tuple in HOT chain
                                              or self
t_infomask2                    18       2    natts + flag bits (see below)
t_infomask                     20       2    flag bits (see below)
t_hoff                         22       1    header size (>= 24, padded to MAXALIGN)
t_bits                         23      ...   null bitmap, present iff
                                              t_infomask & HEAP_HASNULL
```

After `t_bits` (and optional OID, if `t_infomask & HEAP_HASOID` — legacy,
removed in PG12+), the actual user data starts at offset `t_hoff`.
[verified-by-code `htup_details.h:153-205`]

## 3. The two infomasks

`t_infomask` (low byte significance) carries MVCC and storage hints. The
load-bearing bits:

```
HEAP_HASNULL       0x0001   has nulls (t_bits present)
HEAP_HASVARWIDTH   0x0002   has at least one variable-length attribute
HEAP_HASEXTERNAL   0x0004   has a TOAST pointer
HEAP_XMIN_COMMITTED 0x0100  xmin known committed (hint bit)
HEAP_XMIN_INVALID   0x0200  xmin known aborted (hint bit)
HEAP_XMAX_COMMITTED 0x0400  xmax known committed (hint bit)
HEAP_XMAX_INVALID   0x0800  xmax known aborted (hint bit)
HEAP_XMAX_IS_MULTI  0x1000  xmax holds a MultiXactId
HEAP_UPDATED        0x2000  this is the older of an UPDATE pair
HEAP_MOVED_OFF      0x4000  rejected by VACUUM FULL (pre-9.0, legacy)
HEAP_MOVED_IN       0x8000  inserted by VACUUM FULL (pre-9.0, legacy)
```

`t_infomask2` carries the natts count in its low 11 bits plus row-lock bits:

```
HEAP_NATTS_MASK    0x07FF   natts (11 bits — limits tuples to 2047 columns)
HEAP_KEYS_UPDATED  0x2000   key columns were updated by xmax (matters for FKs)
HEAP_HOT_UPDATED   0x4000   tuple was HOT-updated (skip index updates)
HEAP_ONLY_TUPLE    0x8000   tuple is in a HOT chain, not reachable from index
```

[verified-by-code `htup_details.h:188-217` (t_infomask bits), `htup_details.h:288-298` (t_infomask2 bits)]

## 4. The hint bits — performance, not correctness

`HEAP_XMIN_COMMITTED`, `HEAP_XMIN_INVALID`, `HEAP_XMAX_COMMITTED`, and
`HEAP_XMAX_INVALID` are **hints**. They speed up the visibility check
(`HeapTupleSatisfiesMVCC` and friends) by avoiding a `pg_xact` SLRU lookup,
but the source of truth is always `pg_xact`. A tuple read from a fresh
backup, a streaming replica, or a base copy may have stale or absent hint
bits — the visibility code checks `pg_xact` and then OR's the bit in for
future readers.

Setting a hint bit dirties the page **only "softly"** — `MarkBufferDirtyHint`
not `MarkBufferDirty` — because the page can be re-derived on restart from
the same `pg_xact` lookup that would set it again. Soft-dirty pages can be
discarded by checksums-disabled redo without losing correctness.
[verified-by-code `bufmgr.c` `MarkBufferDirtyHint` + `htup_details.h:284-353`]

## 5. xmin/xmax/cmin/cmax — the MVCC visibility quad

- `t_xmin`: inserting transaction's xid.
- `t_xmax`: deleting/locking transaction's xid (or 0 if alive and unlocked).
- `t_cid`: union — by default holds the inserter's `cmin`, but if the row
  was both inserted AND deleted in the same xact, the `combocid.c` mapping
  squeezes both `cmin` and `cmax` into one CID slot. The mapping is
  per-backend and lost at commit.
- `t_xvac`: the same union slot, repurposed during VACUUM FULL operations
  (pre-PG14). Modern PG uses `cluster.c` (now via `repack.c`) and this slot
  is essentially dead.

The visibility ordering rule (from `heapam_visibility.c`): **always check
`TransactionIdIsInProgress` BEFORE `TransactionIdDidCommit`**, because
`xact.c` records the pg_xact commit *before* clearing `MyProc->xid`. The
reverse order can read pg_xact-committed but still-in-procarray and decide
"crashed". The cite for this is the long comment block at
`heapam_visibility.c:13-35`.

## 6. The HOT chain via t_ctid

For non-HOT updates, `t_ctid` of the old version points to the new version's
TID. For HOT updates (where the new version lives on the same page and no
indexed columns changed), the index entries don't need to be re-emitted —
the index points at the head of the HOT chain, and the chain is followed via
`t_ctid` on the heap page itself.

The flags `HEAP_HOT_UPDATED` (on the old version) and `HEAP_ONLY_TUPLE` (on
the new version) drive HOT-aware visibility. `t_ctid` of a HOT chain end
points to itself (`t_ctid == t_self`).

A redirect line pointer (line-pointer flag `LP_REDIRECT`) is used instead of
a tombstone when a HOT chain head is removed by pruning — the redirect points
forward to the next live tuple in the chain so the original index entry
still resolves. [verified-by-code `pruneheap.c.md`]

## 7. Where 24 comes from

The minimum `t_hoff` is `MAXALIGN(SizeofHeapTupleHeader)` = 24 on 64-bit
platforms. Add null bitmap (1 bit per attr, rounded up to 1 byte minimum,
MAXALIGN-padded) if `HEAP_HASNULL`. Then user data starts. A "small" tuple
with no nulls + a single int4 is therefore 24 + 4 = 28 bytes on disk, with
4 bytes of padding to MAXALIGN, for 32 bytes total — page overhead per tuple
is significant for narrow tables. This is why TOAST + array-as-jsonb-column
patterns help with wide tables but hurt with narrow ones.

## 8. Reading and writing checklist

When you're touching tuple memory in C code, in order:

1. Did you call `GetMultiXactIdMembers` on an xmax marked
   `HEAP_XMAX_IS_MULTI` rather than treating it as an xid?
2. Did you check `HeapTupleHeaderXminCommitted(htup)` (with hint-bit
   fast-path) before reading data?
3. If you're emitting the tuple back to a client / WAL / index, did you
   account for HOT (`HEAP_ONLY_TUPLE` means it's not reachable from any index
   — emitting it via the index path would be wrong)?
4. If you're computing visibility, did you check IsInProgress before
   DidCommit (§5 rule)?
5. Did you call `HeapTupleHeaderSetCmin` / `HeapTupleHeaderSetCmax` via the
   `combocid.c` API rather than writing the union slot directly?

## 9. Glossary

- **HeapTuple**: in-memory wrapper carrying TID + table OID + ptr to header.
- **HeapTupleHeader**: on-disk header (24 bytes minimum) + null bitmap + data.
- **HOT (Heap-Only Tuple)**: an update where no indexed columns changed, so
  the new tuple lives on the same page and is reachable only via the heap
  chain — not via an independent index entry.
- **infomask / infomask2**: the two flag fields. Mostly hint bits + storage
  flags + MultiXactId encoding + HOT flags.
- **Hint bit**: a `t_infomask` flag set by readers to speed up future
  visibility checks. Always re-derivable from pg_xact, so loss is OK.
- **xmin / xmax**: inserting / deleting (or locking) transaction xids.
- **cmin / cmax**: command-id within the inserting / deleting transaction.
  Shared in the `t_cid` slot via the `combocid.c` mapping.
- **t_ctid**: pointer to the next tuple in a chain — usually the next version
  via UPDATE, or self for the latest version.
- **MAXALIGN**: alignment of `Datum`/`double` on the platform, typically 8.
