# heap.h

- **Source path:** `source/src/include/catalog/heap.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Prototypes for functions in backend/catalog/heap.c."

## Key declarations

- `CookedConstraint` struct — parser-output constraint after pre-evaluation, ready for StoreConstraints.
- `RawColumnDefault` struct — parsed-but-not-yet-cooked default expression.
- Flags for `CheckAttributeType`: `CHKATYPE_ANYARRAY`, `CHKATYPE_ANYRECORD`, `CHKATYPE_IS_PARTKEY`, `CHKATYPE_IS_PARTITIONED`.
- API prototypes: `heap_create`, `heap_create_with_catalog`, `heap_drop_with_catalog`, `heap_truncate*`, `RelationClearMissing`, `SetAttrMissing`, `StoreAttrMissingVal`, `CheckAttributeNamesTypes`, `CheckAttributeType`, `InsertPgAttributeTuples`, `InsertPgClassTuple`, `AddRelationNewConstraints`, `AddRelationNotNullConstraints`, `cookDefault`, `RemovePartitionKeyByRelId`, `StorePartitionKey`, `StorePartitionBound`.

## Tally

`[verified-by-code]=1`
