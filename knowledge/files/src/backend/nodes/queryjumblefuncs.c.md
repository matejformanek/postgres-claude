# queryjumblefuncs.c

- **Source:** `source/src/backend/nodes/queryjumblefuncs.c` (~620 lines + generated)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Produces the **queryId** used by `pg_stat_statements` (and any other
consumer of `IsQueryIdEnabled()`). The idea: similar queries that
differ only in constants should fingerprint to the same 64-bit hash,
so the stat-tracking is per "query shape" rather than per literal
spelling. `:6-26` `[from-comment]`

## Wire format

Selectively serialise the fields of the `Query` tree that are
**essential to query shape**, hash the resulting byte sequence. Things
omitted on purpose:

- Const values (the whole point).
- Var collations (typmod / collation are usually irrelevant to shape).
- Anything marked `pg_node_attr(query_jumble_ignore)` on the node
  field — e.g. typmod fields.

`pg_node_attr` controls per-field jumbling:
- `query_jumble_ignore` — skip entirely
- `query_jumble_squash` — collapse repeats (e.g. lists of constants)
- `query_jumble_location` — record locations so pg_stat_statements
  can substitute `$1, $2, ...` back into the canonical query text
- `custom_query_jumble` — hand-written jumbler for this field/node

`nodes.h:108-115` `[verified-by-code]`

## Constants squashing `:24-27`

Lists of 2+ constants (or PARAM_EXTERN params) all jumble to the same
hash — so `IN (1,2,3)` and `IN (4,5,6,7,8)` get the same queryId.
Implemented via `_jumbleElements` `:75` `[verified-by-code]`.

## Pipeline

1. End of parse analysis calls `JumbleQuery(query)` if
   `IsQueryIdEnabled()`.
2. `InitJumble` allocates a `JumbleState` with a 1024-byte buffer
   (`JUMBLE_SIZE`). `:51, :65` `[verified-by-code]`
3. `DoJumble` walks the tree, repeatedly calling `AppendJumble` /
   `_jumbleNode` / `_jumbleList` / `_jumbleElements` / `_jumbleParam`,
   etc., flushing the buffer through `hash_any_extended` to a running
   64-bit hash.
4. The final hash lands in `Query.queryId`. The server propagates this
   field through plan caching, into `PlannedStmt`, and the executor.

## Custom jumblers

- `_jumbleA_Const` — value-node payload `:77`
- `_jumbleVariableSetStmt` — utility statement carve-out `:78`
- `_jumbleRangeTblEntry_eref` — RTE alias handling `:79-81`
- Generated bodies via `#include "queryjumblefuncs.funcs.c"` (not
  shown in the top-of-file snippet).

## GUCs and gating

- `compute_query_id` GUC: `off` / `on` / `auto` / `regress`.
  Default `auto` means "compute if any module asks". `:54`
  `[verified-by-code]`
- `query_id_enabled` bool: true when at least one consumer (typically
  `pg_stat_statements` loaded into `shared_preload_libraries`)
  registered interest. `:63` `[verified-by-code]`
- `IsQueryIdEnabled()` is the canonical test (combines the above).
  `:57-61` `[from-comment]`

## `CleanQuerytext` helper `:87+`

Trims the source-string region of multi-statement input down to the
specific statement, for pg_stat_statements display.

## Cross-references

- Header: `source/src/include/nodes/queryjumble.h`
- Top consumer: `contrib/pg_stat_statements/pg_stat_statements.c`
- Generator: `gen_node_support.pl` emits the `_jumbleFoo` family.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
