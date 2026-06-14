# contrib-amcheck (index / heap structural verification)

- **Source path:** `source/contrib/amcheck/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.5` (per `amcheck.control`)
- **Trusted:** no (superuser install; per-function REVOKE FROM PUBLIC)

## 1. Purpose

Structurally verify B-tree indexes, GIN indexes, and heap tables
against PostgreSQL's on-disk invariants. Catches subtle storage
corruption — out-of-order index keys, mis-sized tuple headers,
broken parent-downlink relationships, indexed-but-missing heap
tuples, frozen-yet-dead tuples — that would otherwise surface as
"phantom" rows, missed index matches, or replay failures days
later. Two operating modes per access method:

- **Read-only** (`AccessShareLock`): safe to run on production.
  Catches most invariant violations; misses cross-page
  parent-downlink checks.
- **Read-write-blocking** (`ShareLock`): blocks concurrent DML on
  the target. Catches downlink + sibling-order violations a
  read-only check can't.

## 2. The four verification surfaces

| File | LOC | What it verifies |
|---|---|---|
| `verify_nbtree.c` | 3591 | B-tree indexes (the original; most-used) |
| `verify_heapam.c` | 2180 | Heap tables — tuple headers, XID windows, TOAST consistency |
| `verify_gin.c` | 792 | GIN indexes (pending list + posting tree) |
| `verify_common.c` | 191 | Shared callback dispatch, lock-mode unification |

[verified-by-code via `wc -l source/contrib/amcheck/verify_*.c`]

`verify_common.c` is the dispatch hub — it owns the
`amcheck_lock_relation_and_check()` entry point that every public
function ultimately calls. Per-AM verifier files supply only the
inner callback.

## 3. The B-tree verifier (the canonical one)

Two SQL entry points
[verified-by-code `verify_nbtree.c:176-177`]:

- **`bt_index_check(index, heapallindexed, checkunique)`**
  [verified-by-code `verify_nbtree.c:252`]
  - Acquires `AccessShareLock` on heap + index
    [verified-by-code `verify_nbtree.c:269`].
  - Walks every leaf page left→right. Checks tuple order vs
    insertion scankey; checks high-key invariants.
  - With `heapallindexed=true`, fingerprints every index tuple
    into a Bloom filter, then scans the heap and probes the
    filter — any visible heap tuple missing from the filter is a
    "no matching index tuple" violation.
- **`bt_index_parent_check(index, heapallindexed, rootdescend, checkunique)`**
  [verified-by-code `verify_nbtree.c:284`]
  - Acquires `ShareLock` on heap + index — blocks concurrent DML.
  - Adds verification that downlinks from parent pages point at
    the correct child page, and that sibling pointers form a
    coherent doubly-linked list.
  - With `rootdescend=true`, every leaf tuple is also re-searched
    from the root; catches "incomplete-split"-style transitivity
    violations that the leaf-only walk misses.
  - With `checkunique=true` on a unique index, verifies no
    duplicate-key violations across the index.

The `BtreeCheckState` struct
[verified-by-code `verify_nbtree.c:70-145`] carries the verifier's
mutable per-page state: target block, target LSN, low-key /
high-key for parent verification, plus the optional Bloom filter
+ snapshot for the heapallindexed mode.

## 4. The heap verifier

`verify_heapam(relation, on_error_stop, check_toast, skip,
startblock, endblock)` — verifies tuple headers, xmin / xmax
windows against the clog, line-pointer redirects, TOAST chunk
consistency. The `skip` parameter controls VM-fork-aware skipping
(`all-frozen`, `all-visible`, `none`) — useful for incremental
checks. Returns `(blkno, offnum, attnum, msg)` rows; empty result
= no violations found.

`verify_heapam.c` is the largest verifier (2180 LOC) because heap
invariants are the richest — every column has type-specific
length/encoding constraints to check on top of the per-tuple
header rules.

## 5. The Bloom-filter trick (heapallindexed)

When `heapallindexed=true`:

1. Build a Bloom filter sized for the index's tuple count.
   `bloom_create` is from `source/src/backend/lib/bloomfilter.c`.
2. As the verifier visits each index leaf, fingerprint the
   downlink-pointed heap TID and a hash of the indexed values.
3. After the index walk, open the heap and snapshot-scan.
4. For each visible heap tuple, compute the same fingerprint and
   probe.
5. A miss = heap tuple not represented in index. False-positive
   rate is configurable; default tuned so that a false-negative
   (heap-tuple-with-no-index-entry but matches by chance) is
   astronomically unlikely.

Bloom filters trade memory for verification scope — a 1B-tuple
index needs ~1GB of filter at the default error rate. The verifier
uses the configured `work_mem` as the soft cap; oversize indexes
get a higher false-positive rate, which translates to "may report
fewer violations than exist," never "may report a non-violation as
a violation."

## 6. GIN verification (newest, smallest)

`gin_index_check(index)` [verified-by-code `amcheck--1.4--1.5.sql:7`]
— added in 1.5. Walks the GIN pending list and posting trees;
verifies key order and child pointers. Read-only-lock semantics
(`AccessShareLock`).

## 7. Production-use guidance

- **Read-only mode is cheap enough for nightly CI.** `bt_index_check`
  on a 100GB index is ~10 minutes of read I/O; runs without
  blocking writers.
- **Parent-check is the corruption-paranoia mode.** Use it after a
  suspected crash, replication-replay anomaly, or storage event
  (bad disk, bad RAM). `ShareLock` is acceptable for a maintenance
  window.
- **Always report violations to the upstream `pgsql-hackers` list
  with the table's relkind + extension list.** Storage corruption
  is rare; if amcheck reports it, the bug is either in PG, in an
  extension's WAL code, or in your storage stack.
- **Don't run on a hot replica during catchup.** The verifier uses
  the standby's snapshot horizon, which may move under it.

## 8. Invariants

- **[INV-1]** Read-only checks acquire `AccessShareLock`;
  parent-checks acquire `ShareLock`. The lock mode is a function
  parameter only insofar as the bool `readonly` flag on
  `BtreeCheckState` records it
  [verified-by-code `verify_nbtree.c:81`].
- **[INV-2]** `heapallindexed=true` may report false-positives at
  high index sizes (Bloom-filter saturation); never false-negatives.
- **[INV-3]** `checkunique` requires a UNIQUE constraint; verifier
  errors otherwise.
- **[INV-4]** `verify_heapam` returns rows, not raises ERROR;
  `bt_index_check` raises on first violation unless wrapped.
- **[INV-5]** All public functions are `PARALLEL RESTRICTED`
  [verified-by-code `amcheck--1.3--1.4.sql:18`] — they hold
  per-relation locks and can't be safely run by parallel workers.

## 9. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/amcheck/verify_*.c`
- The Bloom-filter user (heapallindexed code):
  `grep -n 'bloom_' source/contrib/amcheck/verify_nbtree.c`
- Lock-mode dispatch:
  `grep -n 'amcheck_lock_relation_and_check\|AccessShareLock\|ShareLock' source/contrib/amcheck/verify_common.c`

## 10. Cross-references

- `knowledge/subsystems/access-nbtree.md` — the B-tree access
  method whose invariants this verifier checks.
- `knowledge/subsystems/access-heap.md` — heap layout; the heap
  verifier's invariant set.
- `.claude/skills/debugging/SKILL.md` — amcheck is the recommended
  first probe for suspected storage corruption.
- `.claude/skills/access-method-apis/SKILL.md` — index access
  method API; amcheck's checks correspond to AM-level invariants.
- `source/src/backend/lib/bloomfilter.c` — the Bloom filter used
  for heapallindexed mode.
- `source/contrib/amcheck/verify_nbtree.c` — primary verifier.
- `source/contrib/amcheck/verify_heapam.c` — heap verifier.
