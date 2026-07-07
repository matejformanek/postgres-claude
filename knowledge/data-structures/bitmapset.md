# Bitmapset — sets of nonnegative small integers

- **Source path:** `source/src/include/nodes/bitmapset.h`, `source/src/backend/nodes/bitmapset.c`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Companion docs:** `knowledge/idioms/node-types-and-lists.md`,
  `knowledge/subsystems/optimizer.md`, `knowledge/subsystems/parser-and-rewrite.md`

## 1. What it is

A `Bitmapset *` represents any set of nonnegative integers, optimized for
sets where the maximum value isn't large (a few hundred typically). The
canonical use: tracking which rangetable entries / relids / parallel-aware
plan-node ids are in a join.

```c
typedef struct Bitmapset {
    pg_node_attr(custom_copy_equal, special_read_write, no_query_jumble)
    NodeTag      type;
    int          nwords;                              // length of words[]
    bitmapword   words[FLEXIBLE_ARRAY_MEMBER];        // really words[nwords]
} Bitmapset;
```

[verified-by-code `source/src/include/nodes/bitmapset.h:48-54`]

The word width is **64 bits on 64-bit hosts, 32 bits on 32-bit hosts**,
selected by `SIZEOF_VOID_P` [verified-by-code `bitmapset.h:32-46`]. So
`bitmapword` is `uint64` or `uint32` depending on the host. **Don't
hardcode the width in callers.** `BITS_PER_BITMAPWORD` is the
build-time constant to use.

By **convention, the empty set is represented as a NULL pointer**, not
as a zero-length `Bitmapset`. Every API function takes `NULL` to mean
empty — `bms_is_empty(NULL)` is `true`, `bms_add_member(NULL, 5)`
returns a fresh `Bitmapset *`. This invariant is load-bearing across the
optimizer.

## 2. Why it's a Node

`Bitmapset` is a Node-tagged type (`NodeTag type` first field) because:

- It appears in `Plan` and `Query` trees (e.g. `Plan->initPlan` as a
  `Bitmapset *` of subplan ids, `Query->rteperminfos` indices).
- It needs `copyObject` / `equal` / `nodeToString` / `stringToNode`
  support so it survives serialization to parallel workers and to
  catalogs (rule actions).

The `pg_node_attr(custom_copy_equal, special_read_write, no_query_jumble)`
annotation tells `gen_node_support.pl` to skip generation — there are
hand-written `_copyBitmapset`, `_equalBitmapset`, `_outBitmapset`,
`_readBitmapset` in `copyfuncs.c` / `equalfuncs.c` / `outfuncs.c` /
`readfuncs.c`. The `no_query_jumble` tells the query jumbler to skip
this field (Bitmapsets in `Query` don't affect query identity).

## 3. Key operations (`bitmapset.c`)

| Operation | Signature | Notes |
|---|---|---|
| Membership | `bms_is_member(x, bms)` | O(1) |
| Cardinality | `bms_num_members(bms)` | O(nwords) |
| Add | `bms_add_member(bms, x)` | Returns potentially-realloced `Bitmapset *` |
| Delete | `bms_del_member(bms, x)` | Returns the input pointer |
| Union | `bms_union(a, b)` | Allocates new |
| Intersect | `bms_intersect(a, b)` | Allocates new |
| Difference | `bms_difference(a, b)` | Allocates new |
| Subset | `bms_is_subset(sub, super)` | |
| Single member | `bms_singleton_member(bms)` | Errors if not exactly one member |
| Iterate | `bms_next_member(bms, prev)` | Sentinel: pass `-1` first, returns `-2` at end |
| Iterate-destructive | `bms_first_member(bms)` | Removes from set as it returns; pass NULL when done |
| Free | `bms_free(bms)` | `pfree`s the words array + struct |

## 4. The realloc trap

Operations that **may grow** the set (`bms_add_member`, `bms_union`,
`bms_add_members`, `bms_join`) return a pointer that **may be different
from the input**. The classic bug:

```c
bms_add_member(my_set, 42);     // WRONG — return value discarded
                                //   my_set may be invalid if realloc'd
```

The right pattern:

```c
my_set = bms_add_member(my_set, 42);   // always reassign
```

Compiler tools (clang's `nodiscard`-like) won't catch this. Code
review must.

## 5. The mutate-in-place operations

A second class of API mutates the input bitmap **in place** without
reallocation — `bms_del_member`, `bms_replace_members`, etc. These
return the input pointer for caller convenience but the input *is* the
output; aliasing is fine. They never grow the words array, so realloc
isn't a hazard.

`bms_first_member(bms)` is the special case: it both returns a value
and mutates the set. Loop pattern:

```c
int x;
while ((x = bms_first_member(bms)) >= 0)
{
    process(x);
}
/* bms is now empty (logically); free if you allocated it. */
```

## 6. Memory context discipline

`Bitmapset` allocations live in `CurrentMemoryContext`. A
`Bitmapset *` stored in a `RelOptInfo` (or other long-lived planner
struct) was allocated in the planner's per-query context; clones must
go through `bms_copy` if the lifetime needs to extend.

`bms_free(bms)` is a `pfree` shortcut — only useful if you're freeing
inside a context that won't be reset soon. Most planner code lets the
context cleanup do the work.

## 7. Common usage sites

| Site | Field | What it stores |
|---|---|---|
| `RelOptInfo` | `relids` | which baserels this rel covers |
| `PlannerInfo` | `all_baserels`, `outer_join_rels` | set of all rangetable indices |
| `Path` | `param_info->ppi_req_outer` | parameterized-path outer-relid set |
| `Plan` | `initPlan` (as `List` of `int`, NOT a Bitmapset) | subplan ids (note: *not* a Bitmapset by convention) |
| `Query` | `rteperminfos`, `colCollations` (as List) | RTE indices |
| `EState` | `es_jit_combined_instr` | parallel-worker JIT combiner |

The `relids` use is the dominant one — most planner code that takes
a `Bitmapset *` is talking about a set of baserel indices.

## 8. Performance properties

- **Membership / add / delete:** O(1) amortized (constant-bound number of
  words for typical planner usage).
- **Union / intersect / iterate:** O(nwords). For typical 5-table joins,
  nwords = 1 and operations are 1-2 instructions.
- **For sets where the maximum value is large** (e.g. tens of thousands)
  the constant factor on `bms_is_member` is still fast but space is
  wasteful. Don't reach for `Bitmapset` for "set of OIDs" patterns;
  use a hash table or `List` instead.

## 9. Invariants

- **[INV-1]** NULL is the empty set. Never construct an empty
  zero-length `Bitmapset` — the equality functions and `bms_is_empty`
  rely on NULL meaning empty.
- **[INV-2]** The trailing words may have leading zeros, but the
  *highest* set bit must not be in a word past `nwords - 1`. The
  invariant is maintained by canonicalizing on every mutation.
- **[INV-3]** `bms_*` functions that may realloc return the (possibly
  new) pointer; callers MUST assign the return value. Compiler
  doesn't catch this.
- **[INV-4]** A `Bitmapset` stored long-term (in `RelOptInfo`,
  `PlannerInfo`) was allocated in a context that may be reset; use
  `bms_copy` to extend lifetime.

## 10. Useful greps

- Heavy users (planner): `grep -RIn 'bms_' source/src/backend/optimizer/ | head -20`
- The hand-written node funcs:
  `grep -n '_copyBitmapset\|_equalBitmapset\|_outBitmapset\|_readBitmapset' source/src/backend/nodes/*.c`
- The canonical word-width macro: `grep -n 'BITS_PER_BITMAPWORD' source/src/include/nodes/bitmapset.h`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/nodes/bitmapset.c`](../files/src/backend/nodes/bitmapset.c.md) | — | implementation (~1100 LOC) |
| [`src/include/nodes/bitmapset.h`](../files/src/include/nodes/bitmapset.h.md) | 48 | [verified-by-code -54] |
| [`src/include/nodes/bitmapset.h`](../files/src/include/nodes/bitmapset.h.md) | — | Source path |

<!-- /callsites:auto -->

## Cross-references

- `.claude/skills/parser-and-nodes/SKILL.md` — `Bitmapset` is a Node-tagged type that flows through copy/equal/out/read; `pg_node_attr(custom_copy_equal)` rule.
- `.claude/skills/executor-and-planner/SKILL.md` — heavy use in `RelOptInfo->relids` and `Path` parameterized-path tracking.
- `.claude/skills/memory-contexts/SKILL.md` — `Bitmapset` allocations live in `CurrentMemoryContext`; lifetime extension via `bms_copy`.
- `knowledge/idioms/node-types-and-lists.md` — companion patterns for `List` (the heterogeneous version) and `IntList` (the integer-element version).
- `knowledge/subsystems/optimizer.md` — usage patterns in path enumeration and join-order search.
- `source/src/backend/nodes/bitmapset.c` — the implementation (~1100 LOC).
