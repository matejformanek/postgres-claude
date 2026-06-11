# `contrib/pg_plan_advice/pgpa_join.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~105
- **Source:** `source/contrib/pg_plan_advice/pgpa_join.h`

Defines the join-strategy enum (six values — three methods × variants) and
the flattened `pgpa_unrolled_join` / `pgpa_join_member` representation of
join subtrees consumed elsewhere. [verified-by-code]

## API / entry points

- `pgpa_join_strategy` enum (line 27): `JSTRAT_MERGE_JOIN_PLAIN`,
  `_MERGE_JOIN_MATERIALIZE`, `_NESTED_LOOP_PLAIN`, `_NESTED_LOOP_MATERIALIZE`,
  `_NESTED_LOOP_MEMOIZE`, `_HASH_JOIN`. `NUM_PGPA_JOIN_STRATEGY` macro.
  Two distinct merge variants (plain / + Material on inner), three nl
  variants (plain / + Material / + Memoize), one hash. [verified-by-code]
- `pgpa_join_member` struct (line 56): `plan` (the Plan inner/outer child),
  `elided_node` (optional ElidedNode covering it), and *exactly one* of
  `scan` or `unrolled_join` will be non-NULL. [from-comment]
- `pgpa_unrolled_join` struct (line 71): an outer member + arrays of strategy
  + inner members. README example: `((A JOIN B) JOIN C) JOIN D` →
  outer = A, inner = ⟨B,C,D⟩. Non-outer-deep trees use sub-`unrolled_join`s
  inside inner members. [from-comment]
- `pgpa_is_join(plan)` inline (line 89): `NestLoop`, `MergeJoin`, or `HashJoin`.
  [verified-by-code]
- Public function declarations for `pgpa_create_join_unroller`,
  `pgpa_unroll_join`, `pgpa_build_unrolled_join`, `pgpa_destroy_join_unroller`.

## Notable invariants / details

- "Inner array deepest first" — implicit; `pgpa_build_unrolled_join` reverses
  `pgpa_join_unroller`'s outer-first appending. The contract is documented
  on line 82 ("Deepest first."). [from-comment]
- `pgpa_join_unroller` is forward-declared opaque (line 18); definition lives
  in `pgpa_join.c`. [verified-by-code]

## Potential issues

- `pgpa_join.h:54` — "Exactly one of scan and unrolled_join will be non-NULL."
  is a runtime invariant with no `StaticAssert` or struct-level enforcement;
  consumers must verify. [ISSUE-undocumented-invariant: scan-XOR-unrolled_join
  invariant not enforced at compile time (nit)]
- `pgpa_join.h:35` — "update NUM_PGPA_JOIN_STRATEGY if you add anything here"
  comment is the only guard. Pattern reused throughout this contrib.
  [ISSUE-style: trailing-sentinel-via-comment is fragile (nit)]
