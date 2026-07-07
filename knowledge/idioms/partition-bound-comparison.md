# Partition bound comparison — bsearch for the right partition

Once you have a row's partition-key values, finding which
partition the row belongs to is a **comparison + bsearch** on
the parent's stored bounds. Range partitioning uses
`partition_range_bsearch`; list uses `partition_list_bsearch`;
hash uses modular arithmetic on hash values. Each lives in
`partbounds.c` and is called by both tuple routing (insert)
and runtime pruning (select).

Anchors:
- `source/src/backend/partitioning/partbounds.c:3600` —
  partition_list_bsearch [verified-by-code]
- `source/src/backend/partitioning/partbounds.c:3646` —
  partition_range_bsearch [verified-by-code]
- `source/src/backend/partitioning/partbounds.c:2949` —
  partition_hash_bsearch call site [verified-by-code]
- `knowledge/idioms/partition-tuple-routing.md` — companion
  (insert side)
- `knowledge/idioms/partition-runtime-pruning.md` — companion
  (select side)
- `knowledge/idioms/partition-attach-detach.md` — companion
  (validation uses these)
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The three partition strategies

| Strategy | Lookup | Complexity |
|---|---|---|
| RANGE | bsearch on sorted upper bounds | O(log n) |
| LIST | bsearch on sorted (value, partition) pairs | O(log n) |
| HASH | (hash(value) mod modulus, remainder match) | O(1) |

Each has different invariants about the partition-bound space.

## partition_range_bsearch

[verified-by-code `partbounds.c:3646`]

```c
static int
partition_range_bsearch(int partnatts, FmgrInfo *partsupfunc,
                        Oid *partcollation, PartitionBoundInfo boundinfo,
                        PartitionRangeBound *probe, bool *is_equal);
```

Binary search over the sorted upper-bound array. Returns the
**index of the largest bound ≤ probe**. The corresponding
partition is the one whose upper-bound just exceeds the probe
value.

- `is_equal` set if the probe exactly equals the bound (matters
  for inclusivity).
- Returns -1 if probe is below ALL bounds (= default partition,
  if any).
- `partnatts > 1` for multi-column keys; comparison is
  lexicographic.

The `FmgrInfo *partsupfunc` array holds the comparison
function for each partition key column (typically a btree-
opfamily comparator).

## RANGE bound semantics

Ranges have **inclusive lower / exclusive upper** semantics:

```sql
CREATE TABLE p1 PARTITION OF parent FOR VALUES FROM (0) TO (100);
CREATE TABLE p2 PARTITION OF parent FOR VALUES FROM (100) TO (200);
```

- `99` → p1.
- `100` → p2 (lower-inclusive).
- `200` → no partition (upper-exclusive); routing fails or
  goes to default.

Internally only the **upper bound** of each partition is
stored; the lower bound of partition N is the upper bound of
partition N-1.

## partition_list_bsearch

[verified-by-code `partbounds.c:3600`]

```c
static int
partition_list_bsearch(FmgrInfo *partsupfunc, Oid *partcollation,
                       PartitionBoundInfo boundinfo, Datum value,
                       bool *is_equal);
```

For list partitioning, bounds are an array of (value,
partition-index) pairs sorted by value. Binary search finds
the exact value or "not found".

Multi-value list partitions:
```sql
CREATE TABLE p_red PARTITION OF parent FOR VALUES IN ('R1', 'R2');
```

Each list value becomes a separate `boundinfo.datums` entry,
all pointing at the same partition index.

## partition_hash_bsearch

[verified-by-code `partbounds.c:2949` (caller context)]

For hash partitioning:
```sql
CREATE TABLE p0 PARTITION OF parent
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE p1 PARTITION OF parent
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
/* ... */
```

The bounds store (modulus, remainder) pairs. Lookup:
```c
hash = compute_partition_hash(partkey, values);
target_remainder = hash % modulus;
/* bsearch for partition with this (modulus, remainder) */
```

Hash partitions can have **different moduli** (e.g., 4 and 8)
as long as they cover the hash space without overlap. The
bsearch handles this.

## Multi-column key comparison

For multi-key partitioning:
```sql
PARTITION BY RANGE (col1, col2)
```

Each `PartitionBoundInfo.datums[i]` is an array of
`partnatts` Datums. Comparison is lexicographic:
1. Compare datums[0]; if not equal, done.
2. Else compare datums[1]; etc.

Useful for compound ordering: `(2024, 1)` < `(2024, 2)` <
`(2025, 1)`.

## Default partition

If a parent declares `DEFAULT`:
```sql
CREATE TABLE p_default PARTITION OF parent DEFAULT;
```

Bounds that don't match any specific partition route to
default. The lookup functions return a special "default"
marker when no specific bound matches.

A parent can have at most one default partition. If no default
exists, unmatched bounds cause "no partition" errors at
INSERT time.

## The PartitionBoundInfo struct

```c
typedef struct PartitionBoundInfoData
{
    char        strategy;       /* 'r' / 'l' / 'h' */
    int         ndatums;
    Datum     **datums;          /* sorted bound values */
    PartitionRangeDatumKind **kind;  /* MINVALUE / VALUE / MAXVALUE per key */
    int        *indexes;         /* datum → partition index map */
    int         default_index;
    bool        null_index_valid;
    int         null_index;
} PartitionBoundInfoData;
```

The discriminator is `strategy`; subsequent fields are
interpreted per strategy.

## NULL handling

- **RANGE**: NULL values always route to default (or error).
- **LIST**: A partition can explicitly include NULL:
  `FOR VALUES IN (NULL, 'a', 'b')`. The `null_index` field
  tracks which partition.
- **HASH**: NULL hashes to 0; routes to whichever partition
  matches that remainder.

## Common review-time concerns

- **Inclusive-low / exclusive-high** for RANGE — easy to
  off-by-one.
- **bsearch returns largest-≤** — handle the "not found"
  return value (-1).
- **Multi-key comparison is lexicographic** — order of keys
  matters.
- **Hash strategy must cover the space** — overlap detection
  at ATTACH time.
- **Default partition is required** for INSERT to succeed
  when key falls outside specific bounds.
- **NULL handling differs per strategy** — RANGE error, LIST
  optional explicit, HASH always partition-0.

## Invariants

- **[INV-1]** RANGE: bounds sorted; bsearch O(log n).
- **[INV-2]** LIST: distinct values sorted; bsearch O(log
  n); one partition can hold many values.
- **[INV-3]** HASH: lookup is modular O(1); space coverage
  enforced at ATTACH.
- **[INV-4]** Default partition routes unmatched values.
- **[INV-5]** Multi-key comparison is lexicographic in
  declared key order.

## Useful greps

- The bsearch family:
  `grep -n 'partition_range_bsearch\|partition_list_bsearch\|partition_hash_bsearch' source/src/backend/partitioning/partbounds.c | head -10`
- Bound info construction:
  `grep -RIn 'PartitionBoundInfoData\|create_partition_bounds' source/src/backend/partitioning | head -10`
- Overlap detection at ATTACH:
  `grep -n 'check_new_partition_bound\|partition_bounds_equal' source/src/backend/partitioning/partbounds.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/partitioning/partbounds.c`](../files/src/backend/partitioning/partbounds.c.md) | 2949 | partition_hash_bsearch call site |
| [`src/backend/partitioning/partbounds.c`](../files/src/backend/partitioning/partbounds.c.md) | 3600 | partition_list_bsearch |
| [`src/backend/partitioning/partbounds.c`](../files/src/backend/partitioning/partbounds.c.md) | 3646 | partition_range_bsearch |
| [`src/backend/partitioning/partbounds.c`](../files/src/backend/partitioning/partbounds.c.md) | — | full module |
| [`src/include/partitioning/partbounds.h`](../files/src/include/partitioning/partbounds.h.md) | — | public API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/partition-tuple-routing.md` —
  insert-side caller.
- `knowledge/idioms/partition-runtime-pruning.md` —
  select-side caller.
- `knowledge/idioms/partition-attach-detach.md` —
  bound validation at ATTACH.
- `knowledge/data-structures/relfilelocator.md` —
  each partition has its own relfilenumber.
- `knowledge/data-structures/datum-nullabledatum.md` —
  Datum comparison primitives.
- `knowledge/subsystems/partitioning.md` —
  partitioning overview.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/partitioning/partbounds.c` — full
  module.
- `source/src/include/partitioning/partbounds.h` —
  public API.
