# extensible.c

- **Source:** `source/src/backend/nodes/extensible.c` (144 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Registry for **extension-defined node types** and **custom-scan
methods**. Loadable modules call the registration functions at
`_PG_init` time; core code then calls into the registered method
tables for copy/equal/out/read of those nodes and for executor
operations on CustomScan plans. `:1-19` `[from-comment]`

## Two hashtables

```c
static HTAB *extensible_node_methods = NULL;
static HTAB *custom_scan_methods    = NULL;
```

Both keyed by a string `extnodename` (max length `EXTNODENAME_MAX_LEN
= 64` from `extensible.h:24`). Lazily created on first registration via
`hash_create(..., HASH_ELEM | HASH_STRINGS)` with initial size 100.
`:26-55` `[verified-by-code]`

## Public API

| Function | Purpose |
|---|---|
| `RegisterExtensibleNodeMethods` `:75-82` | adds an `ExtensibleNodeMethods` (node_size + nodeCopy/Equal/Out/Read callbacks) |
| `GetExtensibleNodeMethods` `:124-131` | look up by name; `missing_ok` controls whether missing → NULL or `ereport(ERROR)` |
| `RegisterCustomScanMethods` `:87-94` | adds a `CustomScanMethods` (CreateCustomScanState) |
| `GetCustomScanMethods` `:136-143` | look up by name |

Duplicate registration is rejected with
`ERRCODE_DUPLICATE_OBJECT` `:64-67` `[verified-by-code]`.
Lookup-with-missing-not-ok raises `ERRCODE_UNDEFINED_OBJECT`
`:112-115`.

## How an extensible node travels

1. Extension defines its own struct that starts with `ExtensibleNode`
   (`extensible.h:32-38`) — that gives it `NodeTag type = T_ExtensibleNode`
   plus an `extnodename` string identifier.
2. At `_PG_init`, the extension calls `RegisterExtensibleNodeMethods(&my_methods)`.
3. Core `copyObject(p)` sees `T_ExtensibleNode`, calls
   `_copyExtensibleNode` (`copyfuncs.c:146-161`), which looks up
   `my_methods` by `extnodename` and calls `methods->nodeCopy(newnode,
   oldnode)` after allocating `node_size` bytes and copying the
   `extnodename`.
4. Same dispatch pattern for `equal()` (`equalfuncs.c:116-131`),
   `outNode` and `nodeRead` (custom out/read functions).

## CustomScan integration

`extensible.h:79-158` declares three method tables consumed by the
planner/executor:

- `CustomPathMethods` — `PlanCustomPath`, `ReparameterizeCustomPathByChild`
- `CustomScanMethods` — `CreateCustomScanState` (registered here)
- `CustomExecMethods` — Begin/Exec/End/ReScan + DSM hooks + Explain

The Path/Exec method tables travel with the node itself (they're
`const` pointers in the path/state struct). Only `CustomScanMethods`
needs name-based lookup so plan trees serialized to parallel workers
can re-find the methods after `stringToNode`.

## Cross-references

- Header: `source/src/include/nodes/extensible.h`
- Path/Plan/State integration: `nodes/plannodes.h:932 CustomScan`,
  `nodes/execnodes.h CustomScanState`, `nodes/pathnodes.h:2249 CustomPath`.
- Example consumers: `contrib/postgres_fdw` (uses ForeignScan, not
  CustomScan, but same registration pattern via `fdwapi.h`),
  TimescaleDB, Citus.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
