# execGrouping.c

- **Source:** `source/src/backend/executor/execGrouping.c` (624 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

The **shared TupleHashTable** used by HashAgg, Hashjoin (the in-memory side),
SetOp(hash), Subplan hashed-IN, Memoize, and Recursive Union duplicate-check.
Uses simplehash.h to generate a strongly-typed hash table keyed on
MinimalTuple. [from-comment] `:3-15`

## Key APIs

- `execTuplesMatchPrepare(desc, numCols, keyColIdx, eqOperators, collations, parent)` `:61`
  — Compile a "do these two grouping-key column sets match?" ExprState via
  `ExecBuildGroupingEqual`; cached and reused for the table's life.
- `execTuplesHashPrepare(numCols, hashOperators, &eqFuncOids, &hashFunctions)` `:100`
  — Resolve the hash and equality functions for each grouping column from
  the operator OIDs.
- `BuildTupleHashTable(parent, inputDesc, inputOps, numCols, keyColIdx,
  eqfuncoids, hashfunctions, collations, nbuckets, additionalsize,
  metacxt, tablecxt, tempcxt, use_variable_hash_iv)` `:184` — Allocate the
  hash table; `metacxt` holds the simplehash struct, `tablecxt` holds the
  stored MinimalTuples, `tempcxt` is reset per probe. `additionalsize` is
  pad bytes appended to each entry — HashAgg uses it to store transition
  values inline. `use_variable_hash_iv` mixes the parallel worker number
  into the seed so workers don't all hash identically (for partitioned
  hashagg).
- `ResetTupleHashTable(hashtable)` `:302` — empty without freeing the
  simplehash struct; reset the tuple memory context.
- `LookupTupleHashEntry(hashtable, slot, isnew, [hash])` `:382` /
  `LookupTupleHashEntryHash` `:437` — insert-or-find given a slot
  containing the probe row. The two-arg form computes the hash;
  the *Hash form is for cases where the caller already has it (HashAgg
  computes it via a compiled ExecBuildHash32Expr ExprState so it can
  fuse hashing with grouping-key extraction).
- `FindTupleHashEntry(hashtable, slot, eqcomp, hashfunctions)` `:469` —
  read-only probe; takes its own eq/hash funcs because Hashjoin uses
  *different* eq operators for the probe side vs. the build side (the
  build side might use a more restrictive operator if cross-type joins
  collapse to a single hash function).
- `TupleHashTableHash` `:414` — exposed for callers who want to compute the
  hash separately (e.g. HashAgg with batched probes).

## Internal mechanics

- `TupleHashTableHash_internal(tb, tuple)` `:502` — used by simplehash;
  retrieves the precomputed hash from `entry->hash` when SH_STORE_HASH is
  set (it is, see `:33-44` of file). Falls back to extracting columns from
  the MinimalTuple via the `inputOps` and running the precomputed
  hashfunctions if no cached hash.
- `TupleHashTableMatch` `:601` — compares two MinimalTuples by deserializing
  one into the table's `tableslot` and the other into `inputslot`, then
  running the cached eq ExprState (`tablecxt`'s `TupleHashTable->tab_eq_func`).
- The dance with three TupleTableSlots (`inputslot`, `tableslot`, `tab_hash_slot`)
  exists because MinimalTuples don't have system-column space and must be
  unpacked into a slot before the ExprState (which only knows about slots)
  can compare them.

## Shared state notes

- The hash table is **not** parallel-safe by default. Parallel HashAgg uses
  per-worker tables and a final spill-and-redistribute pass — see nodeAgg.c.
- The `additionalsize` mechanism is what lets HashAgg store transition
  values inline; the additional bytes are returned by
  `((char*)entry) + MAXALIGN(sizeof(TupleHashEntryData))`.

## Tags

- [verified-by-code] all API line numbers + the additionalsize/parallel
  isolation behavior.
- [from-comment] file header purpose.
- [inferred] rationale for separate input/table/hash slots.
