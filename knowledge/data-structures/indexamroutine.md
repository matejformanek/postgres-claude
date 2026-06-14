# IndexAmRoutine — the index-AM vtable

`IndexAmRoutine` is the **virtual function table** every
index access method (B-tree, Hash, GIN, GiST, BRIN, SP-GiST,
Bloom) populates. The planner and executor talk only to the
AM through this vtable; the specifics of "how does a leaf
look" or "how is a key compared" are entirely behind the
function pointers. Adding a new index AM means creating a
`xxx_handler()` SQL function that returns a populated
`IndexAmRoutine *`.

Anchors:
- `source/src/include/access/amapi.h:233-330` — full struct
  [verified-by-code]
- `source/src/include/access/amapi.h:113-203` — per-function
  typedefs [verified-by-code]
- `knowledge/subsystems/contrib-bloom.md` — companion;
  reference custom-AM impl
- `.claude/skills/access-method-apis/SKILL.md` — AM skill

## The handler

Every AM has a `xxx_handler` SQL function registered in
`pg_am.amhandler`:

```c
PG_FUNCTION_INFO_V1(blhandler);

Datum
blhandler(PG_FUNCTION_ARGS)
{
    IndexAmRoutine *r = makeNode(IndexAmRoutine);
    r->amstrategies = ...;
    r->amsupport = ...;
    r->ambuild = blbuild;
    r->aminsert = blinsert;
    /* ... fill all required fields ... */
    PG_RETURN_POINTER(r);
}
```

When the planner / executor needs to use an AM, it calls
the handler and reads the returned vtable.

## The capability flags

[verified-by-code `amapi.h:240-295`]

| Field | Meaning |
|---|---|
| `amstrategies` | Number of WHERE-clause strategies (`amop` entries per opclass) |
| `amsupport` | Number of support functions per opclass |
| `amcanorder` | Supports ORDER BY through the index |
| `amcanorderbyop` | Supports ORDER BY <expr> via an operator |
| `amcanbackward` | Can scan backward |
| `amcanunique` | Supports unique indexes |
| `amcanmulticol` | Multi-column indexes supported |
| `amoptionalkey` | First column can be absent from WHERE |
| `amsearcharray` | Supports `IN (...)` (array-keyed search) |
| `amsearchnulls` | Can search for NULL values |
| `amstorage` | Index storage type differs from key type |
| `amclusterable` | CLUSTER can re-order heap by this index |
| `ampredlocks` | Participates in SSI predicate locking |
| `amcanparallel` | Parallel scan supported |
| `amcanbuildparallel` | Parallel index build supported |
| `amcaninclude` | Supports INCLUDE columns |
| `amusemaintenanceworkmem` | Maintenance work_mem applies to build |
| `amparallelvacuumoptions` | Parallel VACUUM options bitmap |

The capability flags determine which planner paths can use
the index. The planner consults them when deciding "can this
WHERE clause use this index?"

## The function pointers

[verified-by-code `amapi.h:296-320`]

### Required for any AM

- **`ambuild`** — initial index build from a heap scan.
- **`ambuildempty`** — build an empty (unlogged) initial
  index.
- **`aminsert`** — insert one tuple.
- **`ambulkdelete`** — VACUUM phase 1: remove TIDs.
- **`amvacuumcleanup`** — VACUUM phase 2: cleanup.
- **`amcostestimate`** — planner cost estimation.
- **`amoptions`** — parse WITH options at CREATE INDEX.
- **`amvalidate`** — validate an opclass (catalog
  invariants).
- **`amadjustmembers`** — opclass member adjustment.
- **`amgettuple` OR `amgetbitmap`** — at least one of:
  - `amgettuple` returns one TID at a time (for ordered
    scans).
  - `amgetbitmap` returns a TIDBitmap (for bitmap scans).
- **`ambeginscan`** — start a scan.
- **`amrescan`** — restart a scan.
- **`amendscan`** — finish a scan.

### Optional (NULL if not supported)

- **`aminsertcleanup`** — per-batch insert cleanup.
- **`ambuildphasename`** — progress reporting names.
- **`ammarkpos` / `amrestrpos`** — cursor save/restore.
- **`amestimateparallelscan` / `aminitparallelscan` /
  `amparallelrescan`** — parallel scan support.

## The two scan modes

[verified-by-code `amapi.h:199-203`]

- **`amgettuple(scan, dir)`** — returns the NEXT TID
  matching the scan keys. The scan maintains position;
  multiple calls walk through matches. Returns false at
  end-of-scan.
- **`amgetbitmap(scan, bitmap)`** — fills a TIDBitmap with
  all matching TIDs at once. Returns count. Used for
  bitmap-heap-scans where the heap is then visited in
  physical order.

Most AMs support both. Btree primarily uses `amgettuple`
(ordered); GIN primarily uses `amgetbitmap` (no natural
order).

## The build phase

```c
IndexBuildResult *
ambuild(Relation heap, Relation index, IndexInfo *indexInfo)
```

[verified-by-code `amapi.h:113-117`]

Inputs:
- `heap` — the relation to index.
- `index` — the (empty) new index relation.
- `indexInfo` — columns, predicate, etc.

The AM scans the heap (typically using
`table_index_build_scan`) and inserts each tuple's index
entries. Returns IndexBuildResult with statistics
(`heap_tuples`, `index_tuples`).

## The cost-estimate function

[verified-by-code `amapi.h:148-160`]

```c
void amcostestimate(PlannerInfo *root, IndexPath *path,
                    double loop_count, ...);
```

The planner calls this for every IndexPath. The AM computes:
- `startup_cost` — overhead before first tuple.
- `total_cost` — cost for the entire scan.
- `selectivity` — fraction of heap rows the index will
  return.
- `correlation` — physical/index order correlation (-1..1).

The cost numbers compete with seq-scan and other index
paths' costs; the planner picks the cheapest.

## Validate hooks

[verified-by-code `amapi.h:178`]

```c
bool amvalidate(Oid opclassoid);
```

Called by `pg_amop` / `pg_amproc` validation. The AM checks
that its opclass declarations make sense (e.g., btree
requires strategies 1-5 to be present, all return bool, etc).

Used by `CREATE OPERATOR CLASS` to refuse invalid
declarations.

## The NULL-can-be-NULL convention

Many fields can be NULL meaning "this AM doesn't support
that feature":
- `ambuildphasename = NULL` → no progress reporting.
- `ammarkpos = NULL` → no cursor save.
- `amgettuple = NULL` → bitmap-only.

The planner consults these to decide whether to choose a
path that would require the feature.

## Common review-time concerns

- **Adding a new capability** → add a flag + plumbing in
  planner; update every AM's handler.
- **All AMs must populate the required fields.** Forgetting
  one = crash on first use.
- **`amgettuple` semantics**: in `BackwardScanDirection`,
  return the previous TID. The AM must support this if
  `amcanbackward = true`.
- **The handler is per-cluster**; only loaded when an index
  using the AM is first accessed.
- **Don't allocate the routine in a short-lived context** —
  it's read across many planner calls.

## Invariants

- **[INV-1]** The AM handler returns a fully populated
  `IndexAmRoutine *`.
- **[INV-2]** Capability flags must match what the function
  pointers do — lying breaks the planner.
- **[INV-3]** At least one of `amgettuple` / `amgetbitmap`
  must be non-NULL.
- **[INV-4]** Optional functions can be NULL; planner
  checks before calling.
- **[INV-5]** AM's opclass declarations validated by
  `amvalidate`.

## Useful greps

- All handler functions:
  `grep -RIn '_handler\b.*RETURNS.*index_am_handler' source/src/include/catalog/pg_proc.dat | head -10`
- Built-in AMs:
  `grep -RIn 'IndexAmRoutine \*' source/src/backend/access | head -10`
- The amapi types:
  `grep -n 'typedef.*amfunction\|typedef struct IndexAmRoutine' source/src/include/access/amapi.h`

## Cross-references

- `knowledge/subsystems/contrib-bloom.md` — reference
  custom AM implementation.
- `knowledge/subsystems/access-nbtree.md` — the most
  common AM; canonical filled-out IndexAmRoutine.
- `knowledge/subsystems/contrib-pg_trgm.md` — GIN/GiST
  opclass impl that plugs into existing AMs.
- `.claude/skills/access-method-apis/SKILL.md` — AM
  contracts skill.
- `source/src/include/access/amapi.h` — full type.
- `source/src/backend/access/index/genam.c` — generic
  AM driver (dispatches via the vtable).
