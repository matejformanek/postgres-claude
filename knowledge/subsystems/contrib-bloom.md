# contrib-bloom (Bloom-filter index access method)

- **Source path:** `source/contrib/bloom/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `bloom.control`)
- **Trusted:** no

## 1. Purpose

Implement a custom **access method** (AM) using Bloom-filter
signatures. Each index entry is a fixed-size bit vector with
bits set for each column's hash; lookups OR the query
signature against entries; mismatches are skipped without
heap visit.

Strengths:
- **Multi-column equality matching** where any subset of
  columns is in the WHERE clause.
- **Compact** — index size is bounded regardless of value
  size.
- **Probabilistic** — false positives possible (rechecked at
  heap); false negatives never.

Weaknesses:
- No range queries.
- No inequality.
- No NULL handling per the spec (limited).

The canonical **"how do I implement a custom AM?"** reference.
All FDW / AM authors look here for "what does an
`amroutine` actually look like."

## 2. The 5 C files

| File | LOC | What it does |
|---|---|---|
| `blutils.c` | 497 | AM registration + handler |
| `blinsert.c` | 342 | Insert path |
| `blscan.c` | 190 | Scan path |
| `blvacuum.c` | 259 | VACUUM cleanup |
| `blcost.c` | 44 | Cost estimation for planner |
| `blvalidate.c` | 215 | Opclass validity check |

[verified-by-code `wc -l source/contrib/bloom/*.c`]

The split mirrors the AM-routine API: each function category
in its own file.

## 3. The handler function

[verified-by-code `blutils.c:32-150`]

```c
PG_FUNCTION_INFO_V1(blhandler);

Datum
blhandler(PG_FUNCTION_ARGS)
{
    IndexAmRoutine *amroutine = makeNode(IndexAmRoutine);
    /* ... populate the routine ... */
    PG_RETURN_POINTER(amroutine);
}
```

The handler returns a populated `IndexAmRoutine` struct.
Every AM (btree, hash, gin, gist, brin, bloom, sp_gist,
hash) has one of these.

Key fields:
- **`amstrategies` / `amsupport`** — number of strategy +
  support functions in the opclass.
- **`amcanorder` / `amcanorderbyop`** — does this AM support
  ORDER BY?
- **`amcanmulticol`** — multi-column indexes supported?
  (bloom: yes)
- **`amsearchnulls`** — can search NULLs? (bloom: no)
- **`ambuild`, `aminsert`, `ambeginscan`, `amgettuple`,
  `ambulkdelete`, ...** — the actual function pointers.

## 4. The required AM functions (filled in bloom_handler)

[verified-by-code `blutils.c:132-146`]

```c
.ambuild       = blbuild,
.ambuildempty  = blbuildempty,
.aminsert      = blinsert,
.ambulkdelete  = blbulkdelete,
.amvacuumcleanup = blvacuumcleanup,
.ambeginscan   = blbeginscan,
.amgetbitmap   = blgetbitmap,
.amrescan      = blrescan,
.amendscan     = blendscan,
```

Each function implements one phase of the index lifecycle.
The "bitmap" variant of getbitmap (vs `amgettuple`) means
bloom only returns a **bitmap** of candidate TIDs to the
executor; the executor then bitmap-scans the heap.

## 5. The bloom-filter mechanics

For each column in the index, each value gets hashed K
times; K bits in the per-row signature are set. The
signature size and K are configurable via index options:

```sql
CREATE INDEX bloom_idx ON t USING bloom (c1, c2, c3)
WITH (length = 80, col1 = 2, col2 = 2, col3 = 4);
```

- `length = 80` — signature size in bits (per-row).
- `col1 = 2`, `col2 = 2`, `col3 = 4` — bits per column.

A query that constrains some subset of columns sets the
corresponding bits in the query signature. Rows whose
signature `& query_signature != query_signature` are
guaranteed no-match. Rows that pass go to heap recheck.

False-positive rate scales with column density and
signature length. Default config produces ~1% false-positive
rate.

## 6. The build phase

[verified-by-code `blinsert.c`]

`blbuild` does the initial index build:

1. Allocate the bloom-page structure (signatures + free-
   space tracking).
2. Scan the heap, calling per-row callback.
3. Per row, compute the signature and INSERT it.

The build can be parallelized via the standard parallel-
build infrastructure if `amcanbuildparallel = true` (bloom
doesn't enable this).

## 7. The scan path

`blbeginscan` + `blrescan` + `blgetbitmap`:

1. Compute the **query signature** from the WHERE clause.
2. Walk every bloom-index page.
3. Per page, for each entry, AND with query signature; if
   result == query signature, add TID to result bitmap.
4. Return bitmap to executor for bitmap-scan + heap-recheck.

Note this is O(index_size) — bloom is NOT a fast lookup. Its
advantage is when the **index is much smaller than the heap**
because of bit-packing.

## 8. When to use bloom

- **Wide rows with many low-cardinality columns**, queried
  with various subsets of WHERE conditions.
- **You CAN'T use a B-tree** because there's no natural
  multi-column order.
- **You CAN'T use GIN** because the values aren't array-like.

For:
- Single-column equality on high-cardinality columns →
  btree wins.
- Range queries → btree.
- Full-text → GIN.
- Multi-column ANY-of-N WHERE → bloom shines.

## 9. Production-use guidance

- **Bloom is a niche AM.** Use only after measuring btree
  vs bloom on the actual workload.
- **Tune signature length** — too small = false-positive
  rate spikes; too large = index size grows.
- **No NULL handling** — `WHERE c IS NULL` won't use the
  bloom index.
- **Cost estimation is approximate** — the planner may
  prefer seq scan; force with `enable_seqscan = off` for
  testing.

## 10. Invariants

- **[INV-1]** Multi-column equality only; no range, no
  inequality.
- **[INV-2]** False positives possible (heap recheck);
  false negatives never.
- **[INV-3]** Signature is per-row, length determined at
  CREATE INDEX time.
- **[INV-4]** Returns bitmap of candidate TIDs, not
  individual tuples.
- **[INV-5]** Cost model assumes uniform distribution; check
  with real data.

## 11. Useful greps

- The handler:
  `grep -n 'blhandler\|IndexAmRoutine' source/contrib/bloom/blutils.c | head -10`
- The routine table:
  `grep -n 'amstrategies\|amsupport\|ambuild\|aminsert\|amgetbitmap' source/contrib/bloom/blutils.c | head -15`
- Signature computation:
  `grep -n 'BloomSig\|signature' source/contrib/bloom/blutils.c | head -10`

## 12. Cross-references

- `knowledge/subsystems/access-method-apis/SKILL.md` —
  index AM API; bloom is the reference impl.
- `knowledge/subsystems/access-nbtree.md` — companion
  (different) AM; the btree implementation.
- `knowledge/subsystems/contrib-btree_gist.md` — companion
  contrib AM extension.
- `.claude/skills/access-method-apis.md` — AM contracts.
- `source/contrib/bloom/` — implementation directory.
- `source/src/include/access/amapi.h` — IndexAmRoutine
  definition.
