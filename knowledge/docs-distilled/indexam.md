---
source_url: https://www.postgresql.org/docs/current/indexam.html
also_referenced:
  - https://www.postgresql.org/docs/current/index-api.html
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 63: Index Access Method Interface Definition

The contract for writing a pluggable **index AM**. Unlike the table-AM chapter,
this one *does* enumerate the callbacks and — more valuably — spells out the
subtle correctness rules (null handling, optional keys, included columns, HOT
interaction) that are easy to get wrong and are not obvious from the struct.
Distilled here from §63.1 "Basic API Structure" (the meatiest subsection).

## The contract

- **The AM is an `IndexAmRoutine` struct**, returned palloc'd by a handler:
  "The result of the function must be a palloc'd struct of type `IndexAmRoutine`,
  which contains everything that the core code needs to know to make use of the
  index access method." [from-docs]
  [verified-by-code, source/src/include/access/amapi.h:233-326 — `typedef struct
  IndexAmRoutine` … `} IndexAmRoutine;`]
- The handler takes a **dummy `internal` argument** that "simply serves to
  prevent handler functions from being called directly from SQL commands."
  [from-docs]
- Support functions are **plain C functions, not SQL-visible**; they "do all of
  the real work to access indexes." [from-docs]
- **`pg_am` entry names the AM + handler**; created/dropped with `CREATE/DROP
  ACCESS METHOD`. An index AM also needs **operator families/classes** in
  `pg_opfamily`, `pg_opclass`, `pg_amop`, `pg_amproc`. [from-docs]
- **An index = `pg_class` row (physical relation) + `pg_index` row (logical
  content: indexed columns + operator classes).** Two catalogs, not one.
  [from-docs] [via knowledge/idioms/catalog-conventions.md]

## Mandatory vs optional callbacks (from the struct, §63.1)

- **Mandatory** (no `/* can be NULL */`): `ambuild`, `ambuildempty`, `aminsert`,
  `ambulkdelete`, `amvacuumcleanup`, `ambeginscan`, `amrescan`, `amendscan`,
  `amcostestimate`, `amoptions`, `amvalidate`. [from-docs]
  [verified-by-code, source/src/include/access/amapi.h:233-326]
- **Optional** (`/* can be NULL */`): `amcanreturn`, `aminsertcleanup`,
  `amgettuple`, `amgetbitmap`, `ammarkpos`, `amrestrpos`, `amgettreeheight`,
  `amproperty`, `ambuildphasename`, `amadjustmembers`, the parallel-scan trio
  `amestimateparallelscan`/`aminitparallelscan`/`amparallelrescan`, and the
  strategy-translation pair `amtranslatestrategy`/`amtranslatecmptype`. [from-docs]
- **`amgettuple` vs `amgetbitmap` are the two scan styles** and an AM may support
  either or both (both optional, but at least one must work for the index to be
  usable in scans): `amgettuple` returns one TID at a time (ordered scans,
  supports `ammarkpos`/`amrestrpos`); `amgetbitmap` returns all matching TIDs at
  once into a bitmap (no ordering, feeds bitmap heap scans). [from-docs/inferred]

## The subtle correctness rules (the part people get wrong)

- **Optional-key AMs MUST index nulls.** "Indexes that have `amoptionalkey` true
  *must index nulls*, since the planner might decide to use such an index with no
  scan keys at all." A multi-column AM "*must* support scans that omit
  restrictions on any or all of the columns after the first," and must index null
  values "in columns after the first." Exception: "It is, however, OK to omit
  rows where the first indexed column is null." [from-docs — exact phrasing]
- **Included (`INCLUDE`) columns must allow nulls independently of
  `amoptionalkey`.** "`amcaninclude` … can store (without processing) additional
  columns beyond the key column(s)." Legal combo: `amcanmulticol=false` +
  `amcaninclude=true` (one key column plus included columns). [from-docs]
- **`amsummarizing` and HOT.** An AM that summarizes (granularity "at least per
  block", e.g. BRIN) sets `amsummarizing`, which lets **HOT updates continue**
  even when a summarized attribute changes — because the index points at block
  ranges, not individual tuples. Caveat: "this does not apply to attributes
  referenced in index predicates; an update of such an attribute always disables
  HOT." [from-docs] [via knowledge/subsystems/access-heap.md — HOT]
- **`aminsert` must be safe under concurrency** and `ambulkdelete`/`amvacuumcleanup`
  return `IndexBulkDeleteResult`; `ambuild` returns `IndexBuildResult`. These
  result structs are how VACUUM and CREATE INDEX learn tuple counts/pages.
  [from-docs]

## Links into corpus

- [[knowledge/files/src/backend/access/index/amapi.c.md]] — `GetIndexAmRoutine`,
  the validation of a returned `IndexAmRoutine`.
- [[knowledge/subsystems/access-nbtree.md]] — the btree AM as the canonical full
  implementation of every callback (incl. `amgettuple`, `amcanreturn`).
- [[knowledge/idioms/catalog-conventions.md]] — the `pg_am`/`pg_opclass`/`pg_amop`/
  `pg_amproc` registration an index AM requires.
- [[knowledge/docs-distilled/indexes-types.md]] — user-facing view of the AMs.
- [[knowledge/docs-distilled/brin.md]], [[knowledge/docs-distilled/gin.md]],
  [[knowledge/docs-distilled/gist.md]] — the summarizing / non-btree AMs whose
  flags this chapter explains.
- access-method-apis skill — TID semantics for non-heap stores, strategy/support
  numbers, `genam.c` wrappers.

## Gaps / follow-ups

- §63.2–63.6 (index-functions, index-scanning, index-locking,
  index-unique-checks, index-cost-estimation) carry the per-function signatures
  and the locking/uniqueness contracts; only §63.1 is mined here. `index-locking`
  and `index-unique-checks` are strong candidates for their own distilled docs
  (they intersect the `locking` skill).
