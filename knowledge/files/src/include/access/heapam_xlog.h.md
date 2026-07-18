# heapam_xlog.h

- **Source path:** `source/src/include/access/heapam_xlog.h`
- **Lines:** 529
- **Last verified commit:** `5174d157a038`
- **Companion files:** `heapam_xlog.c` (redo), `heapam.c` (emitters), `heapdesc.c` (deserialization, shared frontend/backend)

## Purpose

Defines every WAL record type emitted by the heap access method, the opcode numbering for two RmgrIDs (`RM_HEAP_ID` and `RM_HEAP2_ID` — heap ran out of opcodes), all the flag bits inside each record, and the redo/desc/identify/mask function prototypes that `xlog.c`'s resource-manager table dispatches to. [from-comment, heapam_xlog.h:27-66]

## Top-of-file comment
> "POSTGRES heap access XLOG definitions." Plus a long comment block at lines 27-66 explaining the opcode encoding and why there are two RmgrIDs.

## Public surface

**RM_HEAP_ID opcodes (heapam_xlog.h:33-47):** `XLOG_HEAP_INSERT 0x00`, `XLOG_HEAP_DELETE 0x10`, `XLOG_HEAP_UPDATE 0x20`, `XLOG_HEAP_TRUNCATE 0x30`, `XLOG_HEAP_HOT_UPDATE 0x40`, `XLOG_HEAP_CONFIRM 0x50` (speculative insertion), `XLOG_HEAP_LOCK 0x60`, `XLOG_HEAP_INPLACE 0x70`. Mask `XLOG_HEAP_OPMASK 0x70`; high bit `XLOG_HEAP_INIT_PAGE 0x80` for full-page restore.

**RM_HEAP2_ID opcodes (heapam_xlog.h:59-66):** `XLOG_HEAP2_REWRITE 0x00`, three flavours of `_PRUNE_*` (`_ON_ACCESS`, `_VACUUM_SCAN`, `_VACUUM_CLEANUP` — identical semantics, distinguished only for analysis), `XLOG_HEAP2_MULTI_INSERT 0x50`, `XLOG_HEAP2_LOCK_UPDATED 0x60`, `XLOG_HEAP2_NEW_CID 0x70`. Old `0x40` was `XLOG_HEAP2_VISIBLE` (now folded into prune records). [from-comment, heapam_xlog.h:53-66]

**Insert/multi-insert flags (heapam_xlog.h:71-79):** `XLH_INSERT_ALL_VISIBLE_CLEARED`, `_LAST_IN_MULTI`, `_IS_SPECULATIVE`, `_CONTAINS_NEW_TUPLE`, `_ON_TOAST_RELATION`, `_ALL_FROZEN_SET` (always implies all-visible).

**Update flags (heapam_xlog.h:84-96):** `XLH_UPDATE_OLD_ALL_VISIBLE_CLEARED`, `_NEW_ALL_VISIBLE_CLEARED`, `_CONTAINS_OLD_TUPLE`, `_CONTAINS_OLD_KEY`, `_CONTAINS_NEW_TUPLE`, `_PREFIX_FROM_OLD`, `_SUFFIX_FROM_OLD` (the prefix/suffix compression).

**Delete flags (heapam_xlog.h:101-108):** `XLH_DELETE_ALL_VISIBLE_CLEARED`, `_CONTAINS_OLD_TUPLE/KEY`, `_IS_SUPER` (super-deletion of speculative-insert), `_IS_PARTITION_MOVE`, `_NO_LOGICAL`.

**Prune-record flags (heapam_xlog.h:327-369):** `XLHP_IS_CATALOG_REL`, `XLHP_CLEANUP_LOCK` (required when moving tuple data; not required for freeze-only or LP_DEAD→UNUSED-only), `XLHP_HAS_CONFLICT_HORIZON`, `XLHP_HAS_FREEZE_PLANS`, `XLHP_HAS_REDIRECTIONS/DEAD_ITEMS/NOW_UNUSED_ITEMS`, `XLHP_VM_ALL_VISIBLE/FROZEN`.

**Freeze-plan flags:** `XLH_FREEZE_XVAC 0x02`, `XLH_INVALID_XVAC 0x04` (0x01 was the now-removed XMIN flag) (heapam_xlog.h:375-377).

**Lock-record infobits (heapam_xlog.h:423-430):** `XLHL_XMAX_IS_MULTI`, `_LOCK_ONLY`, `_EXCL_LOCK`, `_KEYSHR_LOCK`, `_KEYS_UPDATED`; `XLH_LOCK_ALL_FROZEN_CLEARED`.

**Per-record block-reference index constants (NEW — commit `ed62d26cacac`, "Fix VM clear WAL logging by registering VM blocks"):** each heap WAL record that can clear a VM bit now registers the VM page as an explicit block reference, so the VM bit-clear is WAL-logged and replayed instead of being silently reconstructed (the corruption fix). The index constants name those block slots: `HEAP_DELETE_BLKREF_HEAP 0` / `HEAP_DELETE_BLKREF_VM 1` (heapam_xlog.h:115-116); `HEAP_INSERT_BLKREF_HEAP 0` / `HEAP_INSERT_BLKREF_VM 1` (heapam_xlog.h:165-166); `HEAP_MULTI_INSERT_BLKREF_HEAP 0` / `HEAP_MULTI_INSERT_BLKREF_VM 1` (heapam_xlog.h:185-186); `HEAP_UPDATE_BLKREF_HEAP_NEW 0` / `_HEAP_OLD 1` / `_VM_NEW 2` / `_VM_OLD 3` (heapam_xlog.h:242-245, with the registration rules in the comment at :231-241); `HEAP_LOCK_BLKREF_HEAP 0` / `HEAP_LOCK_BLKREF_VM 1` (heapam_xlog.h:433-434). [verified-by-code @5174d157a038]

**WAL record structs:** `xl_heap_delete` (heapam_xlog.h:118), `xl_heap_truncate` (FAM of relids, heapam_xlog.h:139), `xl_heap_header` (the 5 bytes from HeapTupleHeader that must be in WAL because they can't be reconstructed, heapam_xlog.h:155), `xl_heap_insert` (heapam_xlog.h:168), `xl_heap_multi_insert` + `xl_multi_insert_tuple` (heapam_xlog.h:193, 202), `xl_heap_update` (heapam_xlog.h:247), `xl_heap_prune` + companion `xlhp_freeze_plan(s)` + `xlhp_prune_items` (heapam_xlog.h:314-419), `xl_heap_lock` / `xl_heap_lock_updated` (heapam_xlog.h:436, 447), `xl_heap_confirm` (heapam_xlog.h:458), `xl_heap_inplace` (heapam_xlog.h:466 — carries shared-invalidation messages too), `xl_heap_new_cid` (heapam_xlog.h:478 — logical decoding), `xl_heap_rewrite_mapping` (heapam_xlog.h:499 — logical rewrite).

**Function prototypes:** `HeapTupleHeaderAdvanceConflictHorizon`, `heap_redo`, `heap_desc`, `heap_identify`, `heap_mask`, `heap2_redo`, `heap2_desc`, `heap2_identify`, `heap_xlog_logical_rewrite`, `heap_xlog_deserialize_prune_and_freeze` (the last one lives in `heapdesc.c` so it can be linked into frontend tools). [verified-by-code, heapam_xlog.h:509-527]

## Key types / structs

See "WAL record structs" above. Notable shapes:

- `xl_heap_prune` (heapam_xlog.h:314) — Variable-length composite. Lines 277-313 lay out the *exact* byte order of sub-records. `snapshot_conflict_horizon` is **stored unaligned** after `flags` to save space; the comment explicitly warns about this. [from-comment, heapam_xlog.h:306-312]
- `xl_heap_inplace` (heapam_xlog.h:466) — carries the FAM `msgs[]` of `SharedInvalidationMessage` so replay can fire catalog invalidations. Unusual among heap WAL records.
- `xl_heap_new_cid` (heapam_xlog.h:478) — emitted for logical-decoding catalog visibility; stores `target_locator + target_tid` so the cid mapping can be rebuilt.

## Key invariants and locking

- The high bit `XLOG_HEAP_INIT_PAGE` indicates the redo path will fully reinit the target page from the WAL record (used when the operation was on a previously-empty page). [from-comment, heapam_xlog.h:43-47]
- `XLHP_CLEANUP_LOCK` is required if and only if the record's replay needs to move tuple data (pruning that compacts the page). Freeze-only and LP_DEAD→UNUSED-only records can replay with an ordinary exclusive lock. [from-comment, heapam_xlog.h:329-337]
- The conflict horizon stored when `XLHP_HAS_CONFLICT_HORIZON` is set is required for Hot Standby: it gates replay of any record that removes still-visible tuples or freezes still-running xids. [from-comment, heapam_xlog.h:339-345]
- `XLHP_VM_ALL_VISIBLE` / `XLHP_VM_ALL_FROZEN` map to `VISIBILITYMAP_ALL_VISIBLE/FROZEN`; the prune record sets VM bits during VACUUM. Note that as of commit `ed62d26cacac`, the ordinary heap DML records (insert/delete/update/lock/multi-insert) now WAL-log VM-bit *clears* directly via their new VM block references (see "Per-record block-reference index constants") rather than relying on reconstruction — the prune record remains the VM-*set* path. [from-comment, heapam_xlog.h:362-369]
- `XLH_INSERT_ALL_FROZEN_SET` always implies `ALL_VISIBLE_SET` for the corresponding page. [from-comment, heapam_xlog.h:78-79]

## Functions of note

- `heap_redo` / `heap2_redo` — single dispatch points; the actual per-record handlers (`heap_xlog_insert`, `heap_xlog_prune_freeze`, …) are static in `heapam_xlog.c`.
- `heap_xlog_deserialize_prune_and_freeze` — implemented in `heapdesc.c` precisely so it can be linked by both backend redo and frontend `pg_waldump`/`pg_walinspect`. [from-comment, heapam_xlog.h:521-522]
- `HeapTupleHeaderAdvanceConflictHorizon` — used both at WAL-emit time and during redo to compute the snapshot-conflict horizon.

## Cross-references

- Emitters: most heap WAL records originate in `heapam.c` (insert/update/delete/lock/multi-insert), `pruneheap.c` (the unified prune+freeze record), `rewriteheap.c` (logical rewrite mappings).
- Redo: all in `heapam_xlog.c`. Resource-manager registration lives in `access/transam/rmgr.c` and `rmgrlist.h`. [inferred]

## Open questions

- Whether `XLOG_HEAP_TRUNCATE` is still emitted by main heap_truncate or only by partition-related paths. [unverified]
- Exact relationship between `XLH_DELETE_IS_PARTITION_MOVE` flag and logical-decoding handling of moved rows. [unverified]

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=10 [from-readme]=0 [inferred]=1 [unverified]=2`

<!-- Audit note (2026-07-18, pg-quality-auditor AUDIT mode @5174d157a038):
re-anchored from ef6a95c7c64. File grew 499→529 lines via the VM-clear
WAL-logging corruption fix (ed62d26cacac) + RelFileLocator VM refactor
(2340fb8f02b2). Back-half struct/flag cites shifted +27..+30; documented
the new HEAP_*_BLKREF_* block-reference index constants that record the
now-WAL-logged VM-bit clears. -->


## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../subsystems/access-heap.md)
- [idioms/vacuum-hot-prune.md](../../../../idioms/vacuum-hot-prune.md)

