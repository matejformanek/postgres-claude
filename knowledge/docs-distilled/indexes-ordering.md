---
source_url: https://www.postgresql.org/docs/current/indexes-ordering.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.4 Indexes and ORDER BY"
maps_to_skills: [executor-and-planner, access-method-apis]
---

# 11.4 Indexes and ORDER BY

Distilled from §11.4. The planner-facing point: a B-tree scan can *supply*
an ordering, letting the optimizer drop an explicit `Sort` — and the
`ORDER BY … LIMIT n` case is where an ordered index scan is dramatically
cheaper than sort-then-limit.

## Non-obvious claims

- **Only B-tree produces sorted output.** GiST/SP-GiST/GIN/BRIN/hash return
  matching rows in an unspecified, implementation-dependent order, so they
  can never satisfy an `ORDER BY` by themselves. [from-docs §11.4]
- **A default B-tree stores ascending, nulls-last.** A *forward* scan
  satisfies `ORDER BY x` (= `x ASC NULLS LAST`); a *backward* scan satisfies
  `ORDER BY x DESC` (= `x DESC NULLS FIRST`). So plain ASC↔DESC reversal
  needs no special index — the executor just scans the other way. [from-docs §11.4]
- **`ASC`/`DESC`/`NULLS FIRST`/`NULLS LAST` index options only matter for
  mixed orderings.** A single-column custom-ordered index is redundant with
  forward/backward scan; the payoff is a **multicolumn** index that must
  satisfy e.g. `ORDER BY x ASC, y DESC` — only `(x ASC, y DESC)` or
  `(x DESC, y ASC)` can serve it in a single scan. [from-docs §11.4]
- **The planner weighs ordered-index-scan vs seqscan+Sort.** For a full-table
  ordering, an explicit sort over a sequential scan is usually faster
  (sequential I/O) than a fully-ordered index scan (random heap I/O). The
  optimizer picks per estimated cost. [from-docs §11.4]
- **`ORDER BY … LIMIT n` flips the calculus.** An explicit sort must consume
  *all* input to find the first `n` rows; a matching index returns the first
  `n` directly "without scanning the remainder at all." This is the canonical
  ordered-index-scan win. [from-docs §11.4]

## Links into corpus

- B-tree is the ordering-producing AM; ordering keys / scan direction:
  [[knowledge/subsystems/access-nbtree.md]],
  [[knowledge/docs-distilled/btree.md]],
  [[knowledge/files/src/backend/access/nbtree/nbtsearch.c.md]].
- Planner choice ordered-scan vs Sort, and `LIMIT` pushdown:
  [[knowledge/subsystems/optimizer.md]], [[knowledge/docs-distilled/using-explain.md]].
- `amcanorder` / `amcanbackward` AM flags that gate this:
  [[knowledge/docs-distilled/index-api.md]], [[knowledge/docs-distilled/indexam.md]].
- Collation participates in the ordering an index encodes:
  [[knowledge/docs-distilled/indexes-collations.md]].

## Citations

- All bullets: source-URL §11.4 (B-tree-only sorted output, forward/backward
  scan equivalences, multicolumn mixed-order rule, seqscan+Sort vs
  ordered-scan trade-off, and the `LIMIT n` special case).
