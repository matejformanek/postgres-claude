# relcache.h

- **Source path:** `source/src/include/utils/relcache.h`
- **Lines:** 164
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `relcache.c` (impl), `rel.h` (the `RelationData` struct itself), `pg_publication.h` (for `PublicationDesc`).

## Purpose

Public surface of the relation descriptor cache. Declares the `Relation` typedef (pointer to opaque `RelationData`), the `RelationPtr` array-of-relations typedef, the startup phase functions, the open/close API, the various subsidiary getters, and the invalidation hooks called from `inval.c`. Also defines `RELCACHE_INIT_FILENAME = "pg_internal.init"` (25).

## Top-of-file comment

> "Relation descriptor cache definitions." [relcache.h:3-4]

## Public surface (declarations)

- **Constants**: `RELCACHE_INIT_FILENAME` (25).
- **Typedefs**: `Relation` (27) — pointer to `RelationData`; `RelationPtr` (35); `IndexAttrBitmapKind` enum (68) — `KEY`, `PRIMARY_KEY`, `IDENTITY_KEY`, `HOT_BLOCKING`, `SUMMARIZED`.
- **Open/close**: `RelationIdGetRelation`, `RelationClose`, `RelationGetQualifiedRelationName`, `AssertCouldGetRelation` (only meaningful under USE_ASSERT_CHECKING).
- **Subsidiary getters**: `RelationGetFKeyList`, `RelationGetIndexList`, `RelationGetStatExtList`, `RelationGetPrimaryKeyIndex`, `RelationGetReplicaIndex`, `RelationGetIndexExpressions`, `RelationGetDummyIndexExpressions`, `RelationGetIndexPredicate`, `RelationGetIndexAttOptions`, `RelationGetIndexAttrBitmap`, `RelationGetIdentityKeyBitmap`, `RelationGetExclusionInfo`.
- **Init/init-coords**: `RelationInitIndexAccessInfo`, `RelationInitTableAccessMethod`, `RelationBuildPublicationDesc`.
- **Errreports**: `errtable`, `errtablecol`, `errtablecolname`, `errtableconstraint`.
- **Backend startup**: `RelationCacheInitialize`, `RelationCacheInitializePhase2`, `RelationCacheInitializePhase3`.
- **Local-relation creation**: `RelationBuildLocalRelation`.
- **Relfilenumber transitions**: `RelationSetNewRelfilenumber`, `RelationAssumeNewRelfilelocator`.
- **Invalidation hooks**: `RelationForgetRelation`, `RelationCacheInvalidateEntry`, `RelationCacheInvalidate`.
- **Transaction end**: `AtEOXact_RelationCache`, `AtEOSubXact_RelationCache`.
- **Init-file mgmt**: `RelationIdIsInInitFile`, `RelationCacheInitFilePreInvalidate`, `RelationCacheInitFilePostInvalidate`, `RelationCacheInitFileRemove`.
- **Globals (PGDLLIMPORT)**: `criticalRelcachesBuilt`, `criticalSharedRelcachesBuilt`.

## Key types

- `Relation` — forward declared as `typedef struct RelationData *Relation` (27). The struct lives in `rel.h`. Most callers see only the pointer.
- `IndexAttrBitmapKind` (68) — selector for `RelationGetIndexAttrBitmap`; matters for HOT-update eligibility (`HOT_BLOCKING`), logical replication identity (`IDENTITY_KEY`), and summarized-index logic.

## Key invariants

- `criticalRelcachesBuilt` and `criticalSharedRelcachesBuilt` are `PGDLLIMPORT` globals that gate index-scan use during relcache build (see relcache.c notes). Other modules read but should never write them. Comment at 158-162: "should be used only by relcache.c and catcache.c" / "by relcache.c and postinit.c".

## Confidence tag tally

verified-by-code: 3 — from-comment: 2 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-cache.md](../../../../subsystems/utils-cache.md)
