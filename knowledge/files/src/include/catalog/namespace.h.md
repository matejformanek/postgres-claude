# namespace.h

- **Source path:** `source/src/include/catalog/namespace.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Prototypes for functions in backend/catalog/namespace.c."

## Key declarations

- `FuncCandidateList` linked-list (used to enumerate ambiguous overloads during function-call resolution).
- `RVRFlags` bits: `RVR_MISSING_OK`, `RVR_NOWAIT`, `RVR_SKIP_LOCKED`. Passed to `RangeVarGetRelidExtended`.
- `RangeVarGetRelidCallback` typedef — the optional callback invoked after OID resolution but *before* lock acquisition. Used by ALTER TABLE etc. to do a permissions check at the right point.
- API prototypes: `RangeVarGetRelidExtended`, `RangeVarGetCreationNamespace`, `RangeVarGetAndCheckCreationNamespace`, `RangeVarAdjustRelationPersistence`, `RelnameGetRelid`, `RelationIsVisible`, `TypenameGetTypid`, `FuncnameGetCandidates`, `OpernameGetOprid`, `OpernameGetCandidates`, `OpclassnameGetOpcid`, `OpfamilynameGetOpfid`, `CollationGetCollid`, `ConversionGetConid`, `LookupExplicitNamespace`, `get_namespace_oid`, `isTempNamespace`, `isTempToastNamespace`, `isAnyTempNamespace`, `GetTempNamespaceProcNumber`, `RestrictSearchPath`, `fetch_search_path`, `fetch_search_path_array`.

## Tally

`[verified-by-code]=1`
