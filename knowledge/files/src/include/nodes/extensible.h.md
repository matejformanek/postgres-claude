# extensible.h

- **Source:** `source/src/include/nodes/extensible.h` (164 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Declares the **registration-by-name** API for extension-defined node
types and custom scans. Implementation in `extensible.c`. Used by
loadable modules to participate in copy/equal/out/read of plan trees
and to plug in custom executor nodes.

## Types

### `ExtensibleNode` `:32-38`

```c
typedef struct ExtensibleNode {
    pg_node_attr(custom_copy_equal, custom_read_write)
    NodeTag     type;
    const char *extnodename;   /* lookup key */
} ExtensibleNode;
```

Every extension's custom node starts with these fields. The `type`
is always `T_ExtensibleNode`; the `extnodename` (≤ 63 chars, per
`EXTNODENAME_MAX_LEN = 64`) selects the right method table.

### `ExtensibleNodeMethods` `:62-73`

Mandatory callbacks for copy / equal / out / read. Note: callbacks
do **not** need to handle the `type` or `extnodename` fields — core
code does that. `nodeCopy` / `nodeEqual` work on the private fields;
`nodeOut` uses outfuncs conventions; `nodeRead` consumes
`pg_strtok()` tokens.

### CustomPath/Scan/Exec methods `:79-158`

- `CustomPathMethods` — `PlanCustomPath`,
  `ReparameterizeCustomPathByChild`. Lives directly on the
  `CustomPath` node.
- `CustomScanMethods` — `CreateCustomScanState`. Looked up by name,
  because CustomScan nodes serialize through nodeToString to
  parallel workers.
- `CustomExecMethods` — full executor surface:
  - Required: `BeginCustomScan`, `ExecCustomScan`, `EndCustomScan`,
    `ReScanCustomScan`
  - Optional: `MarkPosCustomScan`, `RestrPosCustomScan` (mark/restore)
  - Optional (parallel): `EstimateDSMCustomScan`,
    `InitializeDSMCustomScan`, `ReInitializeDSMCustomScan`,
    `InitializeWorkerCustomScan`, `ShutdownCustomScan`
  - Optional: `ExplainCustomScan`

### Flag bits `:84-86`

```
CUSTOMPATH_SUPPORT_BACKWARD_SCAN   0x0001
CUSTOMPATH_SUPPORT_MARK_RESTORE    0x0002
CUSTOMPATH_SUPPORT_PROJECTION      0x0004
```

Set on `CustomPath.flags` / `CustomScan.flags` so the planner knows
which capabilities the resulting scan has.

## Public functions `:75-77, :160-162`

- `RegisterExtensibleNodeMethods(const ExtensibleNodeMethods *)`
- `GetExtensibleNodeMethods(name, missing_ok)`
- `RegisterCustomScanMethods(const CustomScanMethods *)`
- `GetCustomScanMethods(name, missing_ok)`

## Cross-references

- Implementation: `source/src/backend/nodes/extensible.c`
- Plan/Path/State: `plannodes.h CustomScan`, `pathnodes.h CustomPath`,
  `execnodes.h CustomScanState`.
