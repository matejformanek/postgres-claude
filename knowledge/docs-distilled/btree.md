---
source_url: https://www.postgresql.org/docs/current/btree.html
fetched_at: 2026-06-08T20:51:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter: B-Tree Indexes

The default AM and the one whose opclass contract every other part of the
system leans on (`ORDER BY`, `GROUP BY`, `DISTINCT`, merge joins). The
non-obvious parts are the six support-function slots and the `equalimage`
gate on deduplication.

## Opclass contract — what a btree opclass must satisfy

- **A btree opclass must impose a total order** obeying trichotomy: for any
  non-null A, B exactly one of `A < B`, `A = B`, `B < A` holds. [from-docs]
- **Five strategy operators**, all returning `boolean`: 1=`<`, 2=`<=`, 3=`=`,
  4=`>=`, 5=`>`. `<>` is **not** a strategy member — the planner reaches it via
  the `=` operator's negator link in `pg_amop`. [from-docs]
  [verified-by-code, via [[knowledge/subsystems/access-nbtree.md]]]
- `=` must be an equivalence relation (reflexive/symmetric/transitive); `<`
  must be irreflexive and transitive. [from-docs]

## Six support-function slots (amproc numbers)

- **amproc 1 — `order` (mandatory):** the comparison proc returning `int32`
  `<0 / 0 / >0`. Must respect collation (`PG_GET_COLLATION()`) for collatable
  types; may not return null. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/nbtree/nbtcompare.c.md]]]
- **amproc 2 — `sortsupport` (optional):** faster sorting than repeated
  `order` calls; interface in `src/include/utils/sortsupport.h`. [from-docs]
- **amproc 3 — `in_range` (optional):** supports window `RANGE offset
  PRECEDING/FOLLOWING` frames; raises `ERRCODE_INVALID_PRECEDING_OR_FOLLOWING_SIZE`
  on a negative offset. [from-docs]
- **amproc 4 — `equalimage` (optional):** the **deduplication-safety gate**;
  `equalimage(opcintype oid) returns bool`, true only when "datums the `order`
  proc calls equal are also *bitwise* (image) equal" (`datum_image_eq()`).
  [from-docs] [verified-by-code, via [[knowledge/files/src/backend/access/nbtree/nbtdedup.c.md]]]
- **amproc 5 — `options` (optional):** opclass-specific parameters; present for
  uniformity with other AMs, currently unused by core btree opclasses. [from-docs]
- **amproc 6 — `skipsupport` (optional):** enables **skip scan** by iterating
  discrete-type values in key order; interface in
  `src/include/utils/skipsupport.h`. [from-docs]

## Deduplication

- **Lazy, space-pressure-triggered:** dedup runs only when a new item won't fit
  on a leaf page *and* simple LP_DEAD deletion couldn't free enough room — it is
  not a background task. [from-docs]
- **Posting-list tuples:** duplicate keys are merged into one tuple holding the
  key once plus a *sorted TID array*. Controlled per-index by the
  **`deduplicate_items`** storage parameter (default on). [from-docs]
- **Disabled (unsafe `equalimage`) for:** nondeterministic-collation
  `text`/`varchar`/`char`; `numeric` (display scale must survive); `jsonb`
  (uses numeric internally); `float4`/`float8` (`-0` vs `0`); composite, array,
  and range container types. **`INCLUDE` (covering) indexes can never
  deduplicate**, regardless of opclass. [from-docs]
- **Unique indexes *can* still deduplicate** — used to absorb version-churn
  duplicates and delay page splits while a long-running xact blocks GC,
  complementing bottom-up deletion. [from-docs]
- Core opclasses register either **`btequalimage()`** (always safe) or
  **`btvarstrequalimage()`** (safe only for deterministic collations). [from-docs]

## Implementation notes

- Concurrency follows **Lehman & Yao** with the **Lanin & Shasha** refinements
  (high-key + right-link "move right" without holding locks up the tree).
  [from-docs] [verified-by-code, via [[knowledge/files/src/backend/access/nbtree/README.md]]]
- Page splits cascade upward; a root split adds a new level. [from-docs]
- **Bottom-up index deletion (PG14+)** proactively targets version-churn
  duplicates to avoid page splits under UPDATE-heavy workloads; pre-14 only the
  deferred LP_DEAD "simple deletion" existed. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/nbtree/nbtdedup.c.md]]]

## Why this opclass is load-bearing system-wide
- The default btree opclass's `=` member defines the system's notion of equality
  for `GROUP BY`/`DISTINCT`, and its sort order defines default `ORDER BY` — even
  for types you never index. (Cross-ref: `xindex` chapter.) [from-docs]

## Links into corpus
- [[knowledge/subsystems/access-nbtree.md]] — full subsystem synthesis (60 cites).
- [[knowledge/files/src/backend/access/nbtree/README.md]] — L&Y/Lanin-Shasha description.
- [[knowledge/files/src/backend/access/nbtree/nbtdedup.c.md]] — deduplication + posting lists.
- [[knowledge/files/src/backend/access/nbtree/nbtcompare.c.md]] — the stock comparison procs.
- [[knowledge/docs-distilled/xindex.md]] — operator-class/family mechanics this chapter relies on.
- Skill: `access-method-apis` — implementing a btree opclass in C.

## Gaps / follow-ups
- The chapter's skip-scan (amproc 6) coverage is brief; the executor-side skip
  logic lives in `nbtsearch.c` — cross-check the per-file doc when quoting.
