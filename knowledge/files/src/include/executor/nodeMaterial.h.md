---
path: src/include/executor/nodeMaterial.h
anchor_sha: 4b0bf0788b0
loc: 25
depth: read
---

# nodeMaterial.h

- **Source path:** `source/src/include/executor/nodeMaterial.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 25

## Purpose

Prototype header for the `Material` executor node (`nodeMaterial.c`),
which buffers its child's output into a tuplestore so it can be re-read
cheaply. Two main uses: shielding a non-rescannable child under a
mergejoin/nestloop inner, and supporting **mark/restore** for a mergejoin
inner that isn't a Sort. `ExecMaterialMarkPos` is cited as the canonical
mark/restore example in the `executor-and-planner` skill. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitMaterial(Material *, EState *, int eflags)` | init | returns `MaterialState *` |
| `ExecEndMaterial(MaterialState *)` | teardown | frees the tuplestore |
| `ExecMaterialMarkPos` / `ExecMaterialRestrPos` | mark/restore | canonical implementation |
| `ExecReScanMaterial(MaterialState *)` | rescan | may rewind the tuplestore instead of re-running the child |

## Invariants & gotchas

- On rescan, Material can replay from its tuplestore without re-executing
  the child — the whole point when the child is expensive or
  non-repeatable. [from-comment]

## Cross-refs

- [[nodeSort.h]] — the other mark/restore-capable buffering node.
- [[nodeMemoize.h]] — the parameterised-cache alternative to blanket
  materialization.

## Tags

- [verified-by-code] prototype surface.
