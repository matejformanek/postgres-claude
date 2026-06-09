# Issues — `contrib/btree_gin`

Per-subsystem issue register for **btree_gin**, the GIN opclass
framework for built-in PG types (parallel to btree_gist). 1 source
file / 978 LOC.

**Parent doc:** `knowledge/files/contrib/btree_gin/btree_gin.md`.

**Source:** 6 entries surfaced 2026-06-09 by A13-4.

## Headlines

1. **`cvt_text_name` truncates to NAMEDATALEN-1** and assumes
   truncation < original — only valid in C collation; comment-
   acknowledged. **Latent collation-vs-byte mismatch (parallel to
   A13-3 btree_gist findings).**

2. **`leftmostvalue_timetz` hardcoded `zone = -24*3600` with
   FIXME "XXX is that true?" since 1990s.**

3. **Cross-type `=` with imprecise conversion always sets
   partial-match=true** — performance footgun for O(log N) exact-
   match expectation.

4. **`gin_btree_consistent` returns `true` unconditionally** —
   relies on prefix-match correctness; auditable but fragile.

## Cross-sweep references

- **A13-3 btree_gist** — sibling GiST framework with overlapping
  type coverage; btree_gin is the GIN-side parallel.
- **A12 amcheck `verify_nbtree` invariants** — same type-comparator
  correctness assumptions; if either is wrong, EXCLUDE constraints
  + index-only-scans give wrong answers.

## Entries (6)

- [ISSUE-correctness: cvt_text_name truncates to NAMEDATALEN-1 and
  assumes truncation < original — only valid in C collation;
  comment-acknowledged (nit)] —
  `source/contrib/btree_gin/btree_gin.c`.
- [ISSUE-correctness: hardcoded zone = -24*3600 for
  leftmostvalue_timetz with FIXME "XXX is that true?" since 1990s
  (nit)].
- [ISSUE-defense-in-depth: cross-type = with imprecise conversion
  always sets partial-match=true; performance footgun for O(log N)
  exact-match expectation (nit)].
- [ISSUE-api-shape: gin_btree_consistent returns true
  unconditionally; relies on prefix-match correctness — auditable
  but fragile (nit)].
- [ISSUE-correctness: Assert(partial_key == data->entry_datum)
  compares Datums by value for pass-by-ref types (pointer compare);
  future GIN refactor copying the Datum will fire (nit)].
- [ISSUE-defense-in-depth: leftmostvalue_inet calls inet_in per
  scan (nit, trivial perf)].
