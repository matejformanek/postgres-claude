---
scenario: add-new-aggregate-function
when_to_use: Adding a new built-in aggregate function — pg_aggregate.dat row plus the supporting C transition / final / serial / deserial / combine functions in pg_proc.dat.
companion_skills: ["catalog-conventions","fmgr-and-spi"]
related_scenarios: ["add-new-builtin-function","add-new-data-type"]
canonical_commit: f9a0392e1cf
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new built-in aggregate

## Scope — what's in / out

**In scope:**
- Adding a new aggregate visible as a SQL-callable aggregate (e.g. `bit_xor(int4)`, `min(bytea)`).
- Wiring its support procs: `aggtransfn` (a.k.a. sfunc), optional `aggfinalfn`, optional parallel-aware trio `aggcombinefn` / `aggserialfn` / `aggdeserialfn`, optional moving-aggregate `aggmtransfn` / `aggminvtransfn` / `aggmfinalfn`.
- Choosing `aggtranstype` (flat Datum vs `internal` pointer-to-palloc'd struct).
- Doc + regression coverage.

**Out of scope:**
- Adding a brand-new scalar data type the aggregate operates on → see `add-new-data-type.md`.
- Adding a non-aggregate built-in function (the transfn itself, if it's a regular binary op like `int4xor` you'd reuse, may already exist) → see `add-new-builtin-function.md`.
- User-defined aggregates via `CREATE AGGREGATE` (this scenario is for *built-in* aggregates that ship in `pg_aggregate.dat`).
- Ordered-set / hypothetical-set aggregates (`aggkind='o'`/`'h'`) — the same machinery, but the direct-args wiring and `aggnumdirectargs` add a layer this scenario doesn't drill into; see `orderedsetaggs.c`.
- Window-function specialisation (handled by `nodeWindowAgg.c`, mostly orthogonal).

## Pre-flight

- **Companion skills:** load `catalog-conventions` (BKI / `.dat` syntax / catversion / OID range / syscache regen) and `fmgr-and-spi` (V1 calling convention, `PG_RETURN_*`, `AggCheckCallContext` for internal-state aggs).
- **Canonical commit:** `f9a0392e1cf` — *"Add bit_xor aggregate function"*. Pure catalog-only patch (reused existing `intNxor` C funcs as transfn=combinefn), and a clean reference for the minimal aggregate shape. Read it before starting. For the parallel-aware-with-internal-state shape, also read `16fd03e9565` (parallel `string_agg` / `array_agg`) and `2d24fd942c7` (`min`/`max(bytea)`).
- **Common pitfalls (one-line each):**
  - Forgetting `prokind => 'a'` and `prosrc => 'aggregate_dummy'` on the `pg_proc.dat` rows for the aggregate itself [verified-by-code](source/src/include/catalog/pg_proc.dat:8824).
  - `aggtranstype => 'internal'` with no `aggserialfn`/`aggdeserialfn` → planner silently disables parallel aggregation (no error, but no parallel) [verified-by-code](source/src/backend/optimizer/prep/prepagg.c).
  - Strict transfns vs non-strict: setting `proisstrict => 'f'` on the aggregate `pg_proc` row matters; the transfn's own strictness controls NULL-skip semantics differently — see `pitfalls` below.
  - `opr_sanity` regression catches most catalog inconsistencies; run it before anything else.

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_aggregate.dat` | The aggregate row itself: `aggfnoid`, `aggtransfn`, optional `aggfinalfn` / `aggcombinefn` / `aggserialfn` / `aggdeserialfn` / `aggmtransfn` / `aggminvtransfn` / `aggmfinalfn`, `aggtranstype`, `aggtransspace`, `agginitval`. Schema defined in `pg_aggregate.h:34-104` [verified-by-code](source/src/include/catalog/pg_aggregate.h:34). | — | catalog-conventions |
| 2 | `src/include/catalog/pg_proc.dat` | One row per aggregate signature with `prokind => 'a'`, `proisstrict => 'f'`, `prosrc => 'aggregate_dummy'`. Plus rows for any *new* C support funcs (transfn, finalfn, combine, serial, deserial) you're introducing. Pick OIDs from an unused block; `unused_oids` script helps [verified-by-code](source/src/include/catalog/pg_proc.dat:8824). | [pg_proc.dat.md](../files/src/include/catalog/pg_proc.dat.md) (TODO: confirm exists) | catalog-conventions |
| 3 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` because the catalog content changed. Required for any `.dat` edit [verified-by-code](source/src/include/catalog/catversion.h). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 4 | `src/backend/utils/adt/<typname>.c` | (NEW or extended) C body of the new transfn / finalfn / combine / serial / deserial. For numeric-family aggregates: `numeric.c`. For text/bytea: `varlena.c`. For arrays: `array_userfuncs.c`. Use `PG_FUNCTION_INFO_V1` and, for `internal`-state aggs, call `AggCheckCallContext` to fish out the per-agg memory context [verified-by-code](source/src/include/fmgr.h:821). | (varies; e.g. [varlena.c.md](../files/src/backend/utils/adt/varlena.c.md), [array_userfuncs.c.md](../files/src/backend/utils/adt/array_userfuncs.c.md)) | fmgr-and-spi |
| 5 | `src/test/regress/sql/aggregates.sql` | Functional coverage: small, deterministic queries that exercise the new aggregate, including NULL handling and (if applicable) the FILTER / DISTINCT paths. | — | testing (built-in) |
| 6 | `src/test/regress/expected/aggregates.out` | Matching expected output for #5. Regenerate by running the test and using `pg_regress --inputdir … --outputdir …` or via `meson test --print-errorlogs` then copy from `tmp_install` results dir. | — | testing (built-in) |
| 7 | `src/test/regress/expected/opr_sanity.out` | `opr_sanity` cross-checks catalog rows. New aggregate may surface diff lines (e.g. the "binary_coercible" / "missing combine func" sanity queries). Update expected output to match, but ONLY after confirming the new diff is benign [verified-by-code](source/src/test/regress/sql/opr_sanity.sql). | — | catalog-conventions |
| 8 | `doc/src/sgml/func.sgml` | User-facing reference for the aggregate. The aggregates table is in this file (for `bit_xor` it's the bit-string functions table; for `min`/`max` it's the general aggregate table) [verified-by-code](source/doc/src/sgml/func.sgml). | — | catalog-conventions |
| 9 | `doc/src/sgml/func/func-aggregate.sgml` (if it exists in your tree) | For tree layouts that split the aggregate doc out of `func.sgml`. Confirm via `ls source/doc/src/sgml/func/` — this layout exists on master [verified-by-code](source/doc/src/sgml/func/func-aggregate.sgml). | — | catalog-conventions |
| 10 | `src/include/catalog/pg_aggregate.h` (optional) | Only edit if introducing a new `aggkind` constant, a new `aggfinalmodify` value, or otherwise extending the catalog schema. Schema-only aggregates leave this alone [verified-by-code](source/src/include/catalog/pg_aggregate.h:131). | [pg_aggregate.h.md](../files/src/include/catalog/pg_aggregate.h.md) | catalog-conventions |

(`pg_aggregate_d.h`, `fmgroids.h`, `fmgrprotos.h`, `fmgrtab.c` are all **generated** — no hand edits. They're regenerated by `genbki.pl` / `Gen_fmgrtab.pl` during the build [verified-by-code](source/src/backend/utils/Gen_fmgrtab.pl:5).)

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Catalog wiring + C funcs.** Files: [1, 2, 3, 4, 10 if needed]. Edits: add the `pg_proc.dat` rows for the aggregate signature(s) and (if new) for the C support functions; add the `pg_aggregate.dat` row(s); bump catversion; write the C bodies in `utils/adt/`. Phase-end check: `meson compile -C dev/build-debug` succeeds and `initdb` produces a fresh cluster without complaint. (`initdb` failure here usually means a typo in a `.dat` symbolic ref, an OID clash, or a missing transfn signature.)

2. **Phase 2 — Regression coverage.** Files: [5, 6, 7]. Edits: extend `aggregates.sql` with the new test cases (cover NULL inputs, empty-input behavior, FILTER if `aggfinalextra` is true, parallel plan if combine+serial+deserial are wired), regenerate `aggregates.out`, then run `opr_sanity` and reconcile `opr_sanity.out`. Phase-end check: `meson test --suite regress --test aggregates --test opr_sanity` is green.

3. **Phase 3 — Parallel + moving-agg (optional).** Files: [1, 4]. Edits: only if the aggregate is meant to be parallel-safe and/or usable in window frames with `EXCLUDE`/moving frames. Add `aggcombinefn` / `aggserialfn` / `aggdeserialfn` (parallel) and / or `aggmtransfn` / `aggminvtransfn` / `aggmfinalfn` (moving). Re-extend `aggregates.sql` with a query forced into parallel via `SET min_parallel_table_scan_size=0; SET parallel_setup_cost=0`. Phase-end check: `EXPLAIN` of the new test query shows `Partial Aggregate` / `Finalize Aggregate`.

4. **Phase 4 — Docs.** Files: [8, 9]. Edits: add the aggregate to the appropriate SGML table with signature, description, and (if non-obvious) a note on partial-aggregation support. Phase-end check: `meson compile -C dev/build-debug docs` renders without xmllint errors.



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`aggregate-partial-finalize`](../idioms/aggregate-partial-finalize.md) | shares files: `src/include/catalog/pg_aggregate.h` |
| [`aggregate-trans-state`](../idioms/aggregate-trans-state.md) | shares files: `src/include/catalog/pg_aggregate.h` |
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | shares files: `src/include/fmgr.h` |
| [`memory-contexts`](../idioms/memory-contexts.md) | direct reference |

<!-- /idioms-invoked:auto -->

## Pitfalls

- **`aggtranstype = internal` requires explicit serial/deserial for parallel.** If `aggtranstype` is `'internal'` (state is a pointer to a struct palloc'd in the aggregate memory context), the planner refuses to use partial aggregation across workers unless both `aggserialfn` and `aggdeserialfn` are present. Symptom: no parallel plan, no error message. Reference: `array_agg` / `string_agg` parallelisation in commit `16fd03e9565` [verified-by-code](source/src/include/catalog/pg_aggregate.dat:563).
- **Transfn must palloc its state in the right memory context.** For non-trivial state, call `AggCheckCallContext(fcinfo, &aggcontext)` and `MemoryContextSwitchTo(aggcontext)` before allocating, otherwise the state lives in the per-tuple context and is freed mid-aggregation. Declaration: `fmgr.h:821` [verified-by-code](source/src/include/fmgr.h:821). See idiom `memory-contexts.md`.
- **`prokind => 'a'` AND `prosrc => 'aggregate_dummy'`** are both mandatory on the aggregate's `pg_proc` row. The body never runs; the executor dispatches via `pg_aggregate`. Missing either trips `opr_sanity` [verified-by-code](source/src/include/catalog/pg_proc.dat:8824).
- **`aggfinalextra => 't'` changes the finalfn signature.** When true, the finalfn receives dummy NULL args matching the aggregate's input types (so polymorphic aggregates like `array_agg(anynonarray)` can resolve their return type). If you set this, the finalfn's `pg_proc` signature must take `internal` + the dummy arg type(s). Schema doc: `pg_aggregate.h:69-73` [verified-by-code](source/src/include/catalog/pg_aggregate.h:69).
- **Strict transfn semantics differ from strict aggregate.** A *strict* transfn is skipped on NULL input but the aggregate keeps running. A *non-strict* transfn sees NULL inputs and must handle them. The `pg_proc` row for the aggregate itself sets `proisstrict => 'f'` — that controls SQL-level strictness, not the transfn's [verified-by-code](source/src/include/catalog/pg_proc.dat:8824). See `aggregate-trans-state.md`.
- **OID picking from the wrong block.** New built-in OIDs go in the documented `Add an entry to this block when adding a new built-in OID` range — run `src/include/catalog/unused_oids` to get a free block. Stomping a reserved OID breaks `initdb` cryptically.
- **Synchronization traps (sibling files that must change together):**
  - Any row added to `pg_aggregate.dat` requires a matching `prokind='a'` row in `pg_proc.dat` *and* a `catversion.h` bump. All three move together.
  - If you add `aggcombinefn`/`aggserialfn`/`aggdeserialfn` later (Phase 3), you ALSO need to update the `opr_sanity` expected output, because some sanity queries enumerate aggregates with/without parallel support.
  - C transfn body in `utils/adt/foo.c` ↔ its `pg_proc.dat` row (signature, return type, strict flag) — drift here is the most common build/initdb breakage.

## Verification (exact test invocations)

```bash
# Primary functional coverage
meson test -C dev/build-debug --suite regress --test aggregates

# Catalog cross-check (catches schema-level mistakes the compiler can't)
meson test -C dev/build-debug --suite regress --test opr_sanity

# Full regression suite — the new aggregate may surface in unrelated tests
# (e.g. create_aggregate, partition_aggregate, eager_aggregate)
meson test -C dev/build-debug --suite regress --test create_aggregate \
                                              --test partition_aggregate \
                                              --test eager_aggregate

# Once green, sweep the full thing
meson test -C dev/build-debug
```

If the new aggregate is meant to be parallel-safe, add a query under `aggregates.sql` that forces a parallel plan and EXPLAIN-asserts `Partial Aggregate` appears. No new test file required — `aggregates.sql` is the canonical home.

## Cross-refs

- Companion skills: `.claude/skills/catalog-conventions/SKILL.md`, `.claude/skills/fmgr-and-spi/SKILL.md`.
- Related scenarios: `scenarios/add-new-builtin-function.md` (the transfn / finalfn C body is just an ordinary built-in function), `scenarios/add-new-data-type.md` (often a composite feature: new type + its `min`/`max`/`sum` aggregates).
- Idioms: `knowledge/idioms/catalog-conventions.md` (BKI / `.dat` / catversion), `knowledge/idioms/memory-contexts.md` (`AggCheckCallContext` + per-group memory).
- Subsystems: `knowledge/subsystems/executor.md` (nodeAgg dispatch), `knowledge/subsystems/optimizer.md` (parallel agg planning via `prepagg.c`), `knowledge/subsystems/parser-and-rewrite.md` (`parse_agg.c` handles aggregate parsing).
- Deep-dive flow docs: `knowledge/flows/aggregate-trans-state.md`, `knowledge/flows/aggregate-hash-vs-sort.md`, `knowledge/flows/aggregate-partial-finalize.md`, `knowledge/flows/aggregate-grouping-sets.md`.
- Reference patch (canonical_commit): `git -C source show f9a0392e1cf`. For parallel-aware shape: `git -C source show 16fd03e9565`. For `min`/`max` over a new datatype: `git -C source show 2d24fd942c7`.
