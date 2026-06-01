# storage.h

- **Source path:** `source/src/include/catalog/storage.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Prototypes for functions in backend/catalog/storage.c."

## Key declarations

- `wal_skip_threshold` GUC (kB; default 2048).
- API prototypes: `RelationCreateStorage`, `RelationDropStorage`, `RelationPreserveStorage`, `RelationTruncate`, `RelationPreTruncate`, `RelationCopyStorage`, `RelFileLocatorSkippingWAL`, `EstimatePendingSyncsSpace`, `SerializePendingSyncs`, `RestorePendingSyncs`, `smgrDoPendingDeletes`, `smgrDoPendingSyncs`, `smgrGetPendingDeletes`, `PostPrepare_smgr`, `AtSubCommit_smgr`, `AtSubAbort_smgr`, `smgr_redo` (declared but in storage_xlog.h logically).

## Tally

`[verified-by-code]=1`
