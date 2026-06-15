---
source_url: https://www.postgresql.org/docs/current/index-api.html
chapter: "63.1 Basic API Structure for Indexes"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# Index AM API structure (`IndexAmRoutine`) — §63.1

Distilled from the official docs §63.1. This is the leaf that actually
enumerates the `IndexAmRoutine` struct; the parent `indexam.html`
(→ `indexam.md`) only frames it. Capability-flag semantics here are the
non-obvious part — they encode contracts the *planner* relies on, so a
wrong flag is a correctness bug, not just a missed optimization.

## Non-obvious claims

- An index AM is a **handler function** taking a single dummy `internal`
  arg and returning the pseudo-type `index_am_handler`; it must return a
  *palloc'd* `IndexAmRoutine` struct. The dummy `internal` arg exists
  only to block direct SQL invocation. [from-docs §63.1]
- `amstrategies` = number of operator strategies, but **0 is legal** and
  means "no fixed set of strategy assignments" (e.g. GiST/SP-GiST/GIN,
  where strategy numbers are opclass-defined, not AM-fixed). `amsupport`
  = number of support functions; `amoptsprocnum` = the opclass-options
  support proc number or 0. [from-docs §63.1]
- `amkeytype` is the type of data *stored in the index*, or `InvalidOid`
  if variable — distinct from the indexed column type (see `amstorage`).
  [from-docs §63.1]
- **`amoptionalkey` is a planner contract, not a convenience flag.** If
  true, the AM must support a scan with *no* scan keys at all, AND must
  index NULL values in the first column. The planner assumes this; an AM
  that omits NULL entries while claiming `amoptionalkey` violates the
  assumption and returns wrong answers. [from-docs §63.1]
- **`amcanmulticol` interacts with NULL indexing:** when true, the AM
  *must* index NULLs in all columns after the first regardless of
  `amoptionalkey` (so the planner can use the index with restrictions
  only on a prefix of columns). Only the *first* column's NULL handling
  is gated on `amoptionalkey`. [from-docs §63.1]
- `amcaninclude` (INCLUDE columns) is independent of `amcanmulticol`:
  `amcanmulticol=false, amcaninclude=true` is valid (one key + payload
  columns). Included columns must always be nullable, independent of
  `amoptionalkey`. [from-docs §63.1]
- `amsummarizing` (BRIN-style per-block-or-coarser summarization) lets
  HOT updates stay HOT even when a summarized attribute changes — but
  does NOT apply to attributes referenced in an index *predicate*
  (those still disable HOT). [from-docs §63.1]
- Other capability flags worth knowing: `amcanorder` (ORDER BY on the
  indexed value, btree), `amcanorderbyop` (ORDER BY on an operator
  result — KNN, GiST distance), `amcanhash` + `amconsistentequality` +
  `amconsistentordering` (newer opfamily-consistency flags),
  `amcanbackward`, `amcanunique`, `amsearcharray` (ScalarArrayOpExpr),
  `amsearchnulls` (IS [NOT] NULL), `amstorage`, `amclusterable`,
  `ampredlocks` (SSI), `amcanparallel`, `amcanbuildparallel`,
  `amusemaintenanceworkmem`. [from-docs §63.1]
- Many interface function pointers are explicitly nullable ("can be
  NULL"): `aminsertcleanup`, `amgettuple`, `amgetbitmap`, `ammarkpos`,
  `amrestrpos`, `amcanreturn`, `amgettreeheight`, `amproperty`,
  `ambuildphasename`, `amadjustmembers`, the three parallel-scan procs,
  and `amtranslatestrategy`/`amtranslatecmptype`. A NULL `amgettuple`
  means bitmap-only (GIN); a NULL `amgetbitmap` means plain-scan-only.
  An AM needs at least one of the two. [from-docs §63.1, inferred]
- The struct is **not self-sufficient**: an index AM is only usable once
  matching `pg_opfamily` / `pg_opclass` / `pg_amop` / `pg_amproc`
  catalog rows exist — those, not the C struct, tell the planner which
  quals an index of this AM can satisfy. [from-docs §63.1]

## Links into corpus

- Parent chapter: [[knowledge/docs-distilled/indexam.md]] (interface
  overview) — this leaf is the struct enumeration that chapter elides.
- Sibling leaves already distilled: [[knowledge/docs-distilled/index-functions.md]],
  [[knowledge/docs-distilled/index-scanning.md]],
  [[knowledge/docs-distilled/index-locking.md]],
  [[knowledge/docs-distilled/index-unique-checks.md]],
  [[knowledge/docs-distilled/index-cost-estimation.md]].
- Source struct: [[knowledge/files/src/include/access/amapi.md]]
  (`IndexAmRoutine` definition + the `IndexAMProperty` enum).
- AM validation: [[knowledge/files/src/backend/access/index/amvalidate.c.md]],
  [[knowledge/files/src/backend/access/index/amapi.c.md]]
  (`GetIndexAmRoutine` / `index_am_handler` resolution).
- Generic AM wrappers: [[knowledge/files/src/backend/access/index/genam.c.md]],
  [[knowledge/files/src/backend/access/index/indexam.c.md]].
- Table-AM counterpart: [[knowledge/docs-distilled/tableam.md]] (the
  `TableAmRoutine` analogue; same handler-returns-palloc'd-struct idiom).

## Caveats / verification

- All claims are `[from-docs]` against the §63.1 prose. Field-by-field
  cross-check against `amapi.h` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735` not performed this run; the
  capability-flag *set* tracks current master but exact field order /
  newly-added flags should be re-verified against
  `source/src/include/access/amapi.h` before citing a line number.
