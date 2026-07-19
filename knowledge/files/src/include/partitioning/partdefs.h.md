# `src/include/partitioning/partdefs.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~26
- **Source:** `source/src/include/partitioning/partdefs.h`

Forward-typedef header — declares the opaque pointer typedefs for the
core partitioning structs so that other headers can refer to
`PartitionBoundInfo`/`PartitionKey`/`PartitionDesc`/
`PartitionDirectory`/`PartitionBoundSpec` without pulling in the full
definitions and their transitive includes. Substitute for "if exists,
list partition_info.h" — the actual file in tree is `partdefs.h`.
[verified-by-code]

## API / declarations

- `typedef struct PartitionBoundInfoData *PartitionBoundInfo;`
- `typedef struct PartitionKeyData *PartitionKey;`
- `typedef struct PartitionBoundSpec PartitionBoundSpec;`
- `typedef struct PartitionDescData *PartitionDesc;`
- `typedef struct PartitionDirectoryData *PartitionDirectory;`

[verified-by-code]

## Notable invariants / details

- No includes — keeps the dependency footprint to zero. Anywhere a
  header just needs to mention "a pointer to a PartitionFoo", it
  includes this file rather than the heavier per-struct header.
  [inferred]
- `PartitionBoundSpec` is a Node (declared in `parsenodes.h`) so
  the typedef here uses the same name as the tag — the other four
  are tagged with `Data` suffixes so the pointer typedef strips it.

## Potential issues

- No header guard violations or stale TODOs — file is intentionally
  minimal. None to report.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/partitioning.md](../../../../subsystems/partitioning.md)
