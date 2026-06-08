---
source_url: https://www.postgresql.org/docs/current/wal-for-extensions.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
note: §64.2 (custom-rmgr.html) supplies the callback contract; the parent page (wal-for-extensions.html) supplies only the generic-vs-custom choice.
---

# Docs distilled — Chapter 64: Write-Ahead Logging for Extensions

The two ways an extension makes its changes crash-safe. Distilled for the
**choice criteria** (Generic WAL vs Custom Resource Manager) and the **custom-rmgr
contract + its standby-redo trap** — the docs companion to the `wal-and-xlog`
skill.

## The two options

1. **Generic WAL** (`generic_xlog.c`): you wrap page modifications in
   `GenericXLogStart` / `GenericXLogRegisterBuffer` / `GenericXLogFinish`; core
   computes a byte-diff and **writes the redo for you — no redo function to
   author.** Simplest; works for any extension that just dirties pages. [from-docs]
   [cross: knowledge/docs-distilled/wal.md]
2. **Custom Resource Manager** (`custom-rmgr.html`, §64.2): you define your own
   WAL record types and **write your own `rm_redo`.** "More flexible, supports
   logical decoding, and can sometimes generate much smaller WAL records than
   generic WAL. However, it is more complex." [from-docs — exact wording]

**Rule of thumb:** reach for Generic WAL unless you need logical decoding or WAL
volume matters; only then pay the custom-rmgr complexity. [inferred, from-docs]

## Custom rmgr — the `RmgrData` contract (§64.2)

`RegisterCustomRmgr(RmgrId rmid, const RmgrData *rmgr)` registers an
eight-callback table: [from-docs]

- `const char *rm_name;` — unique human name.
- `rm_redo(XLogReaderState *record)` — **apply the record during recovery** (the
  one you can't omit).
- `rm_desc(StringInfo, record)` — pretty-print for `pg_waldump`.
- `rm_identify(uint8 info)` — record-subtype name **from `xl_info` only** (must not
  consult the rmid).
- `rm_startup` / `rm_cleanup` — recovery begin/end hooks.
- `rm_mask(char *pagedata, BlockNumber)` — mask non-deterministic bits for
  `wal_consistency_checking`.
- `rm_decode(LogicalDecodingContext *, XLogRecordBuffer *)` — required only for
  logical-decoding support.

[from-docs] [verified-by-code, source/src/include/access/xlog_internal.h —
`typedef struct RmgrData`] — re-verify the exact field order on a direct read.

## The standby-redo trap (the load-bearing gotcha)

- `RegisterCustomRmgr` **must be called from `_PG_init`**, and the module **must
  stay in `shared_preload_libraries` for as long as any of its WAL records can
  exist in the system** — otherwise **"PostgreSQL will not be able to apply or
  decode the custom WAL records, which may prevent the server from starting."**
  [from-docs — exact wording]
- Consequence: the `rmid → handler` mapping must be **identical on primary and
  standby** (and across restart-into-recovery), because redo runs the standby's
  registered `rm_redo`. Forgetting the standby's `shared_preload_libraries`, or
  changing the rmid, bricks recovery. This is the same "must be loaded everywhere
  it can be invoked" discipline as parallel-worker custom-scan registration.
  [inferred, from-docs] [cross: knowledge/docs-distilled/custom-scan.md]

## ID allocation

- During development use **`RM_EXPERIMENTAL_ID`** to avoid reserving a number; for
  release, **reserve a real ID at the Custom WAL Resource Managers wiki page** to
  avoid cross-extension collisions. The reservable custom range is the high rmgr
  IDs (`RM_EXT_ID_MIN`..`RM_EXT_ID_MAX`, the 128–255 band). [from-docs]
  [inferred — numeric range per source/src/include/access/rmgr.h; not directly
  re-verified this run, tag pending a header read]

## Emitting a record

- Build the record with `XLogBeginInsert` + `XLogRegisterData` /
  `XLogRegisterBuffer`, then `XLogInsert(rmid, info)` with your custom `rmid` and
  an `info` byte your `rm_identify`/`rm_redo` understand. [from-docs]
  [cross: wal-and-xlog skill — the XLogInsert idiom]

## Links into corpus

- [[knowledge/docs-distilled/wal.md]] — the WAL chapter this extends.
- [[knowledge/docs-distilled/tableam.md]] / [[knowledge/docs-distilled/indexam.md]]
  — AMs needing durability are the prime custom-rmgr clients.
- [[knowledge/docs-distilled/custom-scan.md]] — the same register-everywhere
  discipline for parallel workers.
- [[knowledge/subsystems/access-transam.md]] — the xlog machinery rmgrs plug into.
- wal-and-xlog skill — builtin rmgr vs Generic WAL vs custom rmgr decision tree,
  redo-function correctness, FPI/hint-bit rules.

## Gaps / follow-ups

- The parent page rendered as intro-only; §64.2 supplied the callbacks. No
  per-file corpus doc yet for `src/backend/access/transam/generic_xlog.c` or
  `rmgr.c`; the `RmgrData` field order and the `RM_EXT_ID_*` numerics need a
  direct header read to upgrade from `[inferred]` to `[verified-by-code]`.
