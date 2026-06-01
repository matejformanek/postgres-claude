# objectaccess.c

- **Source path:** `source/src/backend/catalog/objectaccess.c`
- **Lines:** ~290
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Functions for object_access_hook on various events." Centralises the `object_access_hook` callback dispatch for the security/audit module hook points: post-create, drop, truncate, post-alter, namespace-search, function-execute. The hook itself is `extern PGDLLIMPORT object_access_hook_type object_access_hook;` declared in objectaccess.h; extensions like sepgsql install into it.

## Public surface

Per-event hooks come in pairs: an OID variant and a `_Str` variant for objects identified by string (used during initdb / bootstrap before OIDs are assigned):

- `RunObjectPostCreateHook` (32) — fired after CREATE; includes `is_internal` flag.
- `RunObjectDropHook` (54) — fired before pg_depend deletion; carries DropBehavior subflags.
- `RunObjectTruncateHook` (76) — fired by TRUNCATE.
- `RunObjectPostAlterHook` (92) — fired after ALTER.
- `RunNamespaceSearchHook` (115) — fired during search-path resolution if `ereport_on_violation` is on; lets sepgsql veto schema visibility.
- `RunFunctionExecuteHook` (139) — fired right before fmgr invokes a user-defined function.
- Plus `_Str` variants at lines 158, 180, 202, 218, 241, 265 for bootstrap.

## Wiring

`Invoke*Hook*` macros in objectaccess.h call these only if `object_access_hook` is non-NULL, so the overhead in a vanilla build is one branch.

## Confidence tag tally

`[verified-by-code]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
