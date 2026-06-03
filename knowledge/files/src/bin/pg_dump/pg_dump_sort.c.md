---
path: src/bin/pg_dump/pg_dump_sort.c
anchor_sha: 4b0bf0788b0
loc: 1780
depth: deep
---

# pg_dump_sort.c

- **Source path:** `source/src/bin/pg_dump/pg_dump_sort.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1780

## Purpose

Two orthogonal ordering passes over the `DumpableObject[]` array
collected by the `getXxx()` calls in `pg_dump.c`:

1. **Type-then-name sort** (`sortDumpableObjectsByTypeName`) — a
   cosmetic deterministic baseline so that "logically identical
   schemas dump identically". Sort key: priority-of-type → namespace
   name → object name → type → per-type natural-key tiebreaker.
2. **Dependency sort** (`sortDumpableObjects`) — a topological sort
   on the dependency graph. When the graph has cycles (which the
   PG dependency model frequently produces — type↔I/O function,
   view↔ON SELECT rule, table↔CHECK constraint, …), the failure list
   is passed to `findDependencyLoops` → `repairDependencyLoop`, which
   pattern-matches the cycle shape and breaks it by either (a) removing
   one edge, (b) marking one object `separate`+postponing it to
   post-data, or (c) marking a view with a `dummy_view` body.

The output of stage 2 is the order in which `dumpDumpableObject`
emits TOC entries in `pg_dump.c:1213`. [verified-by-code,
pg_dump_sort.c:191-582, 1166-1506; pg_dump.c:1191-1214]

## Public surface

- `sortDumpableObjectsByTypeName(DumpableObject **objs, int numObjs)`
  (191) — qsort with `DOTypeNameCompare`. Stable cosmetic baseline.
- `sortDumpableObjects(DumpableObject **objs, int numObjs, DumpId
  preBoundaryId, DumpId postBoundaryId)` (558) — top-level driver.
  Stashes the boundary IDs in `preDataBoundId`/`postDataBoundId` file
  statics, then loops `TopoSort` until success, calling
  `findDependencyLoops` between failed attempts.

## Internal landmarks

- **`dbObjectTypePriority[]`** (105-155) — designated-initializer
  table mapping each `DumpableObjectType` to a `PRIO_*` enum value.
  Top-of-file comment (24-51) explains the unusual ordering choices:
  triggers/event-triggers/matview-refresh sort LAST to avoid
  interfering with data loads; casts sort EARLY to hoist their
  underlying functions; the `PRE_DATA_BOUNDARY` and
  `POST_DATA_BOUNDARY` priorities serve as section anchors.
  [from-comment, pg_dump_sort.c:24-51]
- **`StaticAssertDecl(lengthof(dbObjectTypePriority) ==
  NUM_DUMPABLE_OBJECT_TYPES, ...)`** (157) — compile-time guard against
  adding a `DO_*` enum value without updating the priority table.
  [verified-by-code, pg_dump_sort.c:157-158]
- **`DOTypeNameCompare`** (199) — the comparator. After priority,
  namespace, name, type, it descends into per-type natural-key
  tiebreakers: function arg-type list (266-283), operator kind +
  arg types (284-300), opclass/opfamily AM (301-322), collation
  encoding (323-344), attrdef attnum (345-354), policy/rule/trigger
  table name (355-387), domain-vs-table constraint discriminator
  (388-421, with the cute trick of returning `PRIO_TYPE - PRIO_TABLE`
  to sort domain constraints before table ones), default-ACL role
  (422-434), publication/subscription rel publication name
  (435-467). Final `Assert(false)` + OID-sort fallback (469-480) is
  a catalog-corruption escape hatch.
- **`pgTypeNameCompare`** (484), **`accessMethodNameCompare`** (528) —
  natural-key lookups: resolve OID via `findTypeByOid` /
  `findAccessMethodByOid` then compare by (nspname, name) /
  amname. Both return 0 with `Assert(false)` on missing OID — treats
  catalog corruption as a tie. [verified-by-code, pg_dump_sort.c:497-525,
  540-548]
- **`TopoSort`** (610) — Knuth Vol. 1 algorithm with a priority-queue
  twist: a `binaryheap` over input-array indices means "of all
  candidates ready to output, pick the one latest in input order",
  which minimises rearrangement vs. the type-name baseline. Cost:
  O(N log N). The output is built right-to-left (`ordering[--i] =
  obj`) and predecessors' `beforeConstraints[]` count is decremented.
  Returns false (and outputs the unresolved set) when a cycle blocks
  progress. [verified-by-code, pg_dump_sort.c:610-741]
- **`findDependencyLoops`** (759) — runs `findLoop` per stuck object;
  uses a `processed[]` array (don't re-find loops sharing already-fixed
  members) and `searchFailed[]` (memoize "no path from j back to k")
  so the search isn't O(N²). Calls `pg_fatal` if a whole sweep fixed
  zero loops — that would mean an infinite outer loop in
  `sortDumpableObjects`. [verified-by-code, pg_dump_sort.c:759-836]
- **`findLoop`** (855) — DFS over the dependency graph. Three early
  exits: object already processed, object already proven not-on-path
  to startPoint, object already in workspace[] (= we're going around
  a different cycle, abandon). Returns the loop length on success;
  on failure, marks `searchFailed[obj] = startPoint` to memoize.
- **Loop-repair fixers** (940-1164) — one per known cycle shape:
  - `repairTypeFuncLoop` (940) — type↔I/O function: redirect function
    dep to the type's shell-type, and bump the shell-type's `dump`
    mask to include the definition.
  - `repairViewRuleLoop` (971) + `repairViewRuleMultiLoop` (991) —
    view↔ON SELECT rule. Simple case removes the rule→view dep;
    multi-loop case marks `viewinfo->dummy_view = true` so a
    placeholder CREATE VIEW emits, then the rule (and the real view
    body) restores in post-data.
  - `repairMatViewBoundaryMultiLoop` (1025) — matview cannot be split
    like a view, so the stopgap is to mark the matview (and any
    dependent matviews) as `postponed_def = true`, dropping into
    post-data.
  - `repairFunctionBoundaryMultiLoop` (1059) — function involved in a
    cycle with the pre-data boundary; mark the function
    `postponed_def = true`.
  - `repairTableConstraintLoop`/`MultiLoop` (1080, 1097) — CHECK
    constraint on table: simple case removes the auto-edge; multi
    marks the constraint `separate = true` and adds a post-data
    dependency.
  - `repairTableAttrDefLoop`/`MultiLoop` (1114, 1122) — attribute
    default behaves identically to CHECK.
  - `repairDomainConstraintLoop`/`MultiLoop` (1137, 1145) — domain
    CHECK or NOT NULL constraints; same pattern as table constraints.
  - `repairIndexLoop` (1159) — index-on-partition ↔ index-on-parent
    (`parentidx == partition_oid`); drop the edge from the parent.
- **`repairDependencyLoop`** (1173) — the big switchboard.
  Pattern-matches `nLoop == 2` cases first (most cycles are pairs),
  then `nLoop > 2` indirect cases. Two ultimate fallbacks: (a) all
  members are `DO_TABLE_DATA` → "circular foreign keys" warning
  + hint about `--disable-triggers` (1463-1487); (b) genuinely
  unrecognised → log everything via `describeDumpableObject` and
  arbitrarily break the first edge (1489-1505).
- **`describeDumpableObject`** (1513) — giant `switch` over all 48
  `DumpableObjectType` enum values; produces human-readable strings
  like `"TABLE foo  (ID 17 OID 16823)"` for warning output.

## Invariants & gotchas

- **Section ordering invariant.** The top-of-file comment (47-50)
  states: "PRE_DATA objects must sort before `DO_PRE_DATA_BOUNDARY`,
  POST_DATA objects must sort after `DO_POST_DATA_BOUNDARY`, and DATA
  objects must sort between them." Adding a `DO_*` whose priority
  violates this silently produces wrong dumps. [from-comment,
  pg_dump_sort.c:47-50]
- **Triggers/event-triggers/REFRESH MATERIALIZED VIEW MUST stay
  last.** Top comment (29-36): "Matview refreshes are last because
  they should execute in the database's normal state (e.g., they
  must come after all ACLs are restored)." Tied to a related
  `RestorePass` mechanism in `pg_backup_archiver.c`. [from-comment,
  pg_dump_sort.c:29-36]
- **Casts sort BEFORE functions deliberately.** Comment (38-46) is
  explicit: this works around the backend recording views-using-casts
  as depending on the cast's underlying function. Reverting this
  would break view dumps. [from-comment, pg_dump_sort.c:38-46]
- **`TopoSort` builds output right-to-left.** `ordering[--i] = obj`;
  the resulting `objs[]` post-`memcpy` is in the correct (left-to-right)
  emission order. Easy to read as backward and misdiagnose.
  [verified-by-code, pg_dump_sort.c:702-718]
- **`findDependencyLoops` calls `pg_fatal` if it fixes zero loops
  in a sweep.** That guards against infinite looping in the
  `while (!TopoSort(...)) findDependencyLoops(...)` driver — if the
  dependency graph has a cycle shape `repairDependencyLoop` doesn't
  recognise, the arbitrary edge-break at line 1502 still fires, so
  in practice this should never trigger. [verified-by-code,
  pg_dump_sort.c:829-831, 1489-1505]
- **`preDataBoundId`/`postDataBoundId` are file statics** (160-161)
  — `sortDumpableObjects` stashes them so the loop-repair fixers can
  reference the boundary objects without parameter-passing
  gymnastics. The file's only mutable state outside the call. The
  comment calls it "grotty but" preferred. [from-comment,
  pg_dump_sort.c:568-571]
- **`Assert(false)` in `DOTypeNameCompare` fallback (479-480)** —
  reaching the OID-sort fallback means two objects compared equal on
  every natural-key column; under `Assert` builds this is a panic.
  Comment notes the test `002_pg_upgrade.pl` may show flakes here
  because `pg_restore -j` doesn't fully constrain OID assignment.
  [from-comment, pg_dump_sort.c:469-478]
- **Catalog corruption is silently "equal".** `pgTypeNameCompare`
  and `accessMethodNameCompare` both Assert+return 0 if `findXxxByOid`
  fails — so under non-assert builds the sort key collapses to the
  next column, but the wrong row may end up before its dependencies.
  [verified-by-code, pg_dump_sort.c:497-513, 540-547]

## Cross-refs

- Header: `knowledge/files/src/bin/pg_dump/pg_dump.h.md`
  (`DumpableObjectType` enum + `DUMP_COMPONENT_*` bits, must stay in
  sync with `dbObjectTypePriority[]`).
- Producer: `knowledge/files/src/bin/pg_dump/pg_dump.c.md`
  (`addBoundaryDependencies` builds the section anchors; the
  per-`getXxx()` collectors populate the `dependencies[]` arrays this
  file reads).
- Archive ordering: `pg_backup_archiver.c`'s `RestorePass` mechanism
  is the matching concept on the restore side (see top comment line
  35).
- Cycle-fix knock-ons: `dumpRule`/`dumpView`/`dumpConstraint`/
  `dumpAttrDef` in `pg_dump.c` all read the `separate` / `dummy_view`
  / `postponed_def` flags set here.

## Potential issues

- **[ISSUE-correctness: catalog-corruption sort fallback can place
  child before parent]** `pg_dump_sort.c:497-513, 540-547` — when
  `findTypeByOid` / `findAccessMethodByOid` returns NULL,
  `pgTypeNameCompare` / `accessMethodNameCompare` return 0 with
  `Assert(false)`. Under release builds, the sort silently degrades
  to the next tiebreaker, but the resulting order may not respect
  the actual catalog relation. Probably benign in practice (catalog
  corruption is rare), but worth a defensive `pg_fatal`. Severity:
  maybe.
- **[ISSUE-undocumented-invariant: `repairDependencyLoop` ordering of
  pattern matches is significant]** `pg_dump_sort.c:1180-1505` — the
  list of `if (nLoop == 2 ...)` blocks is order-sensitive: e.g. the
  index↔index pair (1365) is tested AFTER table↔attrdef (1347), so
  an index dependency loop on a partitioned table doesn't get
  mis-matched. No comment marks this. Adding a new pair-fixer at the
  wrong position could silently take over another's loop. Severity:
  maybe.
- **[ISSUE-stale-todo: matview multi-object loop is "stopgap"]**
  `pg_dump_sort.c:1010-1023` — comment says "As a stopgap, we try
  to fix it by dropping the constraint that the matview be dumped
  in the pre-data section." The fix has held since at least PG 9.x;
  if there's still a known counter-example, it'd be worth tagging
  here. Severity: nit.
- **[ISSUE-question: arbitrary edge-break in unrecognised loop]**
  `pg_dump_sort.c:1502-1505` — when `repairDependencyLoop` doesn't
  recognise the shape, it removes `loop[0] → loop[1]` (or self-dep
  for `nLoop==1`). The choice of edge is data-order-dependent and
  may produce different (but all valid) breaks on different runs.
  Logged via `pg_log_warning`. Severity: nit.

## Tally

`[verified-by-code]=14 [from-comment]=10 [inferred]=0 [unverified]=0`
