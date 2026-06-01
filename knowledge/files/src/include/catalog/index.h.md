# index.h

- **Source path:** `source/src/include/catalog/index.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Prototypes for catalog/index.c."

## Key declarations

- `INDEX_CREATE_*` bitmask flags for `index_create`: `IS_PRIMARY`, `ADD_CONSTRAINT`, `SKIP_BUILD`, `CONCURRENT`, `IF_NOT_EXISTS`, `PARTITIONED`, `INVALID`, `SUPPRESS_PROGRESS`.
- `INDEX_CONSTR_CREATE_*` bitmask flags for `index_constraint_create`.
- `IndexStateFlagsAction` enum (used by `index_set_state_flags` during REINDEX CONCURRENTLY transitions).
- `ReindexParams` struct (options/tablespaceOid for REINDEX).
- API prototypes: `index_create`, `index_create_copy`, `index_concurrently_*`, `index_constraint_create`, `index_drop`, `BuildIndexInfo`, `BuildDummyIndexInfo`, `BuildSpeculativeIndexInfo`, `CompareIndexInfo`, `FormIndexDatum`, `index_update_stats`, `index_build`, `validate_index`, `index_set_state_flags`, `IndexGetRelation`, `reindex_index`, `reindex_relation`.

## Tally

`[verified-by-code]=1`
