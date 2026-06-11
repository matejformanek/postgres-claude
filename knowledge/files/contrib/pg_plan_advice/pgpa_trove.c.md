# `contrib/pg_plan_advice/pgpa_trove.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~518
- **Source:** `source/contrib/pg_plan_advice/pgpa_trove.c`

A "trove" is the in-memory, lookup-optimized organization of supplied advice
for a single query. The data is bucketed into three slices — SCAN advice,
JOIN advice, and REL (applies-to-either) advice — each backed by an array of
`pgpa_trove_entry` plus a `simplehash`-generated hash table keyed by
`(alias_name, partition_name, plan_name)`. Lookups by `pgpa_identifier` are
O(1) average. [verified-by-code]

## API / entry points

- `pgpa_build_trove(advice_items)` (line 133): build a trove from a list of
  parsed `pgpa_advice_item *`. Big switch routes each item by tag to the
  appropriate slice. JOIN_ORDER items get a special transformation: their
  whole top-level list is wrapped in a surrogate `pgpa_advice_target` with
  `ttype = PGPA_TARGET_ORDERED_LIST`, because join order is a single unit
  conceptually. [verified-by-code]
- `pgpa_trove_lookup(trove, type, nrids, rids, *result)` (line 235): main
  query — look up potentially-relevant entries for a set of identifiers.
  Result is a Bitmapset of indexes into `result->entries` (a stable pointer
  to one of the slice's entry arrays). Returns the *union* of matches per
  identifier — the caller filters further. [verified-by-code]
- `pgpa_trove_lookup_all(trove, type, **entries, *nentries)` (line 277):
  bulk variant — return all entries in a slice. Used by feedback generation.
  [verified-by-code]
- `pgpa_cstring_trove_entry(entry)` (line 297): render an entry back to its
  user-facing advice string (used in feedback DefElem defnames).
  [verified-by-code]
- `pgpa_trove_set_flags(entries, indexes, flags)` (line 328): OR `flags`
  into every selected entry's `flags` field. Used by `pgpa_planner.c`
  feedback bookkeeping. [verified-by-code]
- `pgpa_trove_append_flags(buf, flags)` (line 345): render a flag-bitfield
  as English ("matched", "partially matched", "not matched", optionally
  ", inapplicable", ", conflicting", ", failed"). [verified-by-code]

## Notable invariants / details

- **Three slices.** SCAN holds BITMAP_HEAP_SCAN, DO_NOT_SCAN, INDEX_(ONLY_)SCAN,
  SEQ_SCAN, TID_SCAN. JOIN holds JOIN_ORDER, FOREIGN_JOIN, HASH_JOIN,
  MERGE_JOIN_*, NESTED_LOOP_*, SEMIJOIN_*. REL holds PARTITIONWISE,
  GATHER, GATHER_MERGE, NO_GATHER. The split is consumed verbatim in
  `pgpa_planner.c`. [verified-by-code]
- **Hash key omits occurrence and partition_schema** (line 60-72). The
  module's expectation: most queries have occurrence=1 and uniform
  partition_schema, so hashing on all five fields would barely help. The
  hash lookup is followed by a `pgpa_identifier_matches_target` call
  (line 512) that does the full 5-field check. [from-comment]
- **JOIN_ORDER wrapping** (line 144-162): JOIN_ORDER syntactically takes
  a top-level list of targets, but semantically the whole list is one unit.
  The trove builder constructs a surrogate `pgpa_advice_target` to enforce
  this. `pgpa_cstring_trove_entry` undoes the wrapping when rendering
  (line 304-307). [verified-by-code]
- **Per-slice hash + array** (line 37-43). Both `entries` and `hash` start
  at size 16 and grow by doubling. The hash table maps the
  partition-name/plan-name/alias-name key to a Bitmapset of entry-array
  indexes. [verified-by-code]
- The trove builder's switch (line 143) is exhaustive over
  `pgpa_advice_tag_type`; missing values are a compile warning under
  `-Werror=switch`. [verified-by-code]
- `pgpa_trove_lookup_all` (line 277-291) is used post-planning to emit
  feedback for EVERY supplied advice item — including ones that never
  matched anything during planning (so they can be reported as "not
  matched"). [verified-by-code]

## Potential issues

- `pgpa_trove.c:444` — initial allocation of 16 slots; comment explains the
  tradeoff against zeroing overhead. Reasonable default; might be worth a
  per-input sizing heuristic for large advice strings. [verified-by-code]
- `pgpa_trove.c:472-477` — comment "It's not clear to me what to do if
  there are multiple strings, so for now I'm just using the total of all
  of the lengths" — hashing-function quality tradeoff. With three short
  strings the impact is small. [ISSUE-question: hash-tweak choice
  acknowledged as ad-hoc (nit)]
- `pgpa_trove.c:257-264` — `Assert` that all rids share `plan_name`. If they
  don't, the caller has bug. Silently returns wrong results in production.
  [ISSUE-undocumented-invariant: cross-subquery rid-array assertion only
  in cassert (maybe)]
- `pgpa_trove.c:135` — `palloc_object(pgpa_trove)` is uninitialized; relies
  on `pgpa_init_trove_slice` to set every field of each slice. If a new
  field is added to `pgpa_trove_slice`, it must be set in `pgpa_init_trove_slice`.
  [ISSUE-undocumented-invariant: pgpa_trove field-init via per-slice init
  function only (nit)]
- `pgpa_trove.c:347-355` — `pgpa_trove_append_flags` `Assert((flags &
  PGPA_FB_MATCH_PARTIAL) != 0)` if MATCH_FULL is set. Documented in
  `pgpa_planner_feedback_warning` comment that "Feedback should never be
  marked fully matched without also being marked partially matched."
  [from-comment]
- `pgpa_trove.c:444-449` — `pgpa_init_trove_slice` runs `palloc_array` for
  `entries` but leaves it uninitialized (no `palloc0_array`). The first
  `pgpa_trove_add_to_slice` initializes `tag`, `target`, `flags` for the
  newly-used entry. Re-use of previously-grown space relies on per-add
  explicit init. [verified-by-code]
- `pgpa_trove.c:447-448` — `pgpa_trove_entry_create` uses
  `CurrentMemoryContext` not a captured per-query context. Safe because
  `pgpa_planner_setup` runs in a query-scoped context, but
  GEQO interaction (per `pgpa_planner.c` notes) means this could leak
  partial state. [ISSUE-leak: trove hash table tied to
  CurrentMemoryContext at build time, may interact poorly with GEQO (maybe)]
