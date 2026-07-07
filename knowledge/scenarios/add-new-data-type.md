---
scenario: add-new-data-type
when_to_use: You're adding a brand-new built-in scalar data type to core PostgreSQL (e.g. `macaddr8`, `uuid`-class addition) — not a `CREATE TYPE` in an extension and not a composite/range/domain wrapper around an existing type.
companion_skills: ["catalog-conventions","fmgr-and-spi"]
related_scenarios: ["add-new-operator","add-new-operator-class","add-new-cast","add-new-builtin-function"]
canonical_commit: c7a9fa399d5
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new built-in scalar data type

## Scope — what's in / out

**In scope:**
- A new fixed-or-variable-width scalar type with its own in/out/recv/send
  C functions, a default btree opclass, a default hash opclass, the
  basic comparison operators, and text-cast helpers — the "12-14 file
  sweep" that historically appears in every type-addition patch.
- The minimum needed to make `CREATE TABLE t (x newtype PRIMARY KEY);`
  work end-to-end (insert, index, ORDER BY, equality, hash join).

**Out of scope:**
- User-defined types via `CREATE TYPE` from SQL or contrib extension
  (these don't touch `pg_type.dat` — handled by `add-new-extension`).
- Range type wrappers (`pg_range.dat`) — that's a separate pattern.
- GiST/SP-GiST/GIN/BRIN opclasses beyond what btree+hash need; those go
  through `add-new-operator-class` per AM.
- Aggregate functions over the new type — `add-new-aggregate-function`.
- Typmod-bearing types (e.g. `numeric(p,s)`, `varchar(n)`) — same sweep
  plus `typmod_in`/`typmod_out` and a few `format_type` knobs; flagged
  in the pitfalls.
- I/O variant of an existing type (e.g. a new `jsonb`-like encoding for
  an already-installed scalar) — usually a smaller patch.

## Pre-flight

- **Companion skills:** load `catalog-conventions` (BKI pipeline, OID
  ranges, `unused_oids`, genbki rules) and `fmgr-and-spi` (V1 calling
  convention, `PG_GETARG_*`/`PG_RETURN_*`, `Datum` layout for pass-by-ref
  vs pass-by-value).
- **Canonical commit:** `c7a9fa399d5` — *"Add support for EUI-64 MAC
  addresses as macaddr8"* (Stephen Frost, 2017). Read it before
  starting; it is a clean copy-of-an-existing-type pattern and touches
  every file in this checklist except a brand-new `.h` (it reuses
  `utils/inet.h`). The complementary read is the original `uuid` type
  introduction (predates current `.dat` format — useful for shape, not
  for cite syntax).
- **Common pitfalls (one-liners):**
  - Forgetting `catversion.h` bump → initdb-from-old-bki silently
    inherits stale OIDs.
  - Picking an OID that collides — always run
    `src/include/catalog/unused_oids` first.
  - Missing `typcategory` / `typispreferred` → implicit-cast resolution
    behaves surprisingly in mixed expressions.
  - Variable-width type but forgetting `typstorage => 'x'` /
    `typstorage => 'p'` → toaster silently never compresses, or
    compression breaks because varlena header is wrong.
  - btree opclass without `BTEqualStrategyNumber` support proc → planner
    rejects hash joins on the type.

## File checklist (the FULL sweep)

The "starter 14" for a fully-indexable scalar type. Every row is
mandatory unless explicitly marked **optional**.

| #  | File | Why | Per-file doc | Companion skill |
|----|---|---|---|---|
| 1  | `src/include/catalog/pg_type.dat` | Add the `{ oid => …, typname => 'newtype', typlen, typbyval, typcategory, typinput/output/receive/send, typalign, typstorage }` row [verified-by-code](source/src/include/catalog/pg_type.dat:407-411) | [pg_type.h.md](../files/src/include/catalog/pg_type.h.md) | catalog-conventions |
| 2  | `src/include/catalog/pg_proc.dat` | Add `newtype_in`, `newtype_out`, `newtype_recv`, `newtype_send` (the four I/O fns), `newtype_cmp` (btree support 1), `hash_newtype` (hash support 1), plus `=`, `<`, `<=`, `>`, `>=`, `<>` underlying fns. Reserve OIDs from `unused_oids` [verified-by-code](source/src/include/catalog/pg_proc.dat:1211-1216) | [pg_proc.h.md](../files/src/include/catalog/pg_proc.h.md) | catalog-conventions |
| 3  | `src/backend/utils/adt/newtype.c` | (NEW) The C implementation: V1-style `newtype_in`, `newtype_out`, `newtype_recv`, `newtype_send`, `newtype_cmp`, `hash_newtype`, equality/ordering fns. `PG_FUNCTION_INFO_V1` for each. Pass-by-value uses `PG_RETURN_DATUM`; pass-by-ref returns palloc'd varlena. Mac8 (`mac8.c` 11.9K) is the cleanest reference [verified-by-code](source/src/backend/utils/adt/mac8.c:1) | — | fmgr-and-spi |
| 4  | `src/include/utils/newtype.h` *(optional)* | (NEW) Public struct + macros for other backend code that needs to construct/inspect Datums of the new type. Tiny types (uuid, mac) keep this in a 1KB header [verified-by-code](source/src/include/utils/uuid.h:1) | — | catalog-conventions |
| 5  | `src/include/catalog/pg_operator.dat` | Register `=`, `<>`, `<`, `<=`, `>`, `>=` operators with `oprcom`/`oprnegate`/`oprcanmerge`/`oprcanhash` set; `=` MUST have `oprcanhash => 't'` and `oprcanmerge => 't'` if you want hash/merge joins [verified-by-code](source/src/include/catalog/pg_operator.dat:2775-2778) | [pg_operator.h.md](../files/src/include/catalog/pg_operator.h.md) | catalog-conventions |
| 6  | `src/include/catalog/pg_opclass.dat` | Add `{ opcmethod => 'btree', opcname => 'newtype_ops', opcfamily => 'btree/newtype_ops', opcintype => 'newtype' }` and the corresponding `hash` row. Default opclass is implicit (omit `opcdefault => 'f'`) [verified-by-code](source/src/include/catalog/pg_opclass.dat:209-212) | [pg_opclass.h.md](../files/src/include/catalog/pg_opclass.h.md) | catalog-conventions |
| 7  | `src/include/catalog/pg_opfamily.dat` | Declare the opfamilies `btree/newtype_ops` and `hash/newtype_ops` (one row each). Required because opclass FK references opfamily [verified-by-code](source/src/include/catalog/pg_opclass.h:1) | — | catalog-conventions |
| 8  | `src/include/catalog/pg_amop.dat` | Five btree strategy rows (1=<, 2=<=, 3==, 4=>=, 5=>) + one hash strategy row (1==), all pointing at the operators from row 5 [verified-by-code](source/src/include/catalog/pg_amop.dat:875-878) | [pg_amop.h.md](../files/src/include/catalog/pg_amop.h.md) | catalog-conventions |
| 9  | `src/include/catalog/pg_amproc.dat` | Btree support proc 1 (`newtype_cmp` returning `int4`), optionally 2 (sortsupport), 4 (in_range) for window funcs; hash support proc 1 (`hash_newtype`) and 2 (`hash_newtype_extended`) [verified-by-code](source/src/include/catalog/pg_amproc.dat:286-288) | [pg_amproc.h.md](../files/src/include/catalog/pg_amproc.h.md) | catalog-conventions |
| 10 | `src/include/catalog/pg_cast.dat` | Explicit/assignment casts to/from `text` (and `bytea` if binary-friendly). Use `castcontext => 'e'` for explicit-only, `'a'` for assignment, `'i'` for implicit (rare for new scalars) [verified-by-code](source/src/include/catalog/pg_cast.dat:365-368) | [pg_cast.h.md](../files/src/include/catalog/pg_cast.h.md) | catalog-conventions |
| 11 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` to today's `YYYYMMDDN` so existing data dirs are rejected and `initdb` regenerates bootstrap data [verified-by-code](source/src/include/catalog/catversion.h:60) | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 12 | `src/backend/utils/adt/meson.build` | Add `'newtype.c'` to the `backend_sources` list — meson does not glob [verified-by-code](source/src/backend/utils/adt/meson.build:1) | — | catalog-conventions |
| 13 | `src/backend/utils/adt/Makefile` | Mirror the meson change with `newtype.o \\` in the OBJS list (autoconf build still ships) [verified-by-code](source/src/backend/utils/adt/Makefile:1) | — | catalog-conventions |
| 14 | `src/test/regress/sql/newtype.sql` + `expected/newtype.out` | (NEW) Round-trip the I/O, exercise every operator, build a btree + hash index, run an aggregate `min/max`. Match shape of `src/test/regress/sql/macaddr8.sql` [verified-by-code](source/src/test/regress/sql/macaddr8.sql:1) | — | testing |
| 15 | `src/test/regress/parallel_schedule` | Add `newtype` to an appropriate `test:` line so `meson test` picks it up. macaddr8 lives next to `inet macaddr` [verified-by-code](source/src/test/regress/parallel_schedule:1) | — | testing |
| 16 | `doc/src/sgml/datatype.sgml` | New `<sect1 id="datatype-newtype">` plus a row in the summary table near line 295. Reference: the uuid section at `datatype.sgml:4388` [verified-by-code](source/doc/src/sgml/datatype.sgml:4388) | — | catalog-conventions |
| 17 | `doc/src/sgml/func.sgml` *(only if you add SQL-callable helper fns beyond the standard I/O / comparison set)* | Document any helper functions registered in `pg_proc.dat` row 2 | — | catalog-conventions |
| 18 | `src/backend/utils/adt/selfuncs.c` *(optional but historical)* | Some types add themselves to a selectivity-helper switch; macaddr8 added a single line here [verified-by-code](source/src/backend/utils/adt/selfuncs.c:1) | — | catalog-conventions |

If the new type is **typmod-bearing** (`varchar(n)` style), add two more:
`newtype_typmod_in` and `newtype_typmod_out` in row 2/3, and set
`typmodin` / `typmodout` columns in the `pg_type.dat` row [verified-by-code](source/src/include/catalog/pg_type.dat:277-278). This is the
`add-new-data-type` ∪ "typmod axis" composite.

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — C implementation + headers.** Files: [3, 4, 12, 13].
   Write `newtype.c` and (optional) `newtype.h`; wire into meson +
   Makefile. Phase-end check: `meson compile -C dev/build-debug` is
   green (linker sees the new `*_in`/`*_out` symbols even though no
   catalog row references them yet).
2. **Phase 2 — Catalog rows.** Files: [1, 2, 5, 6, 7, 8, 9, 10, 11].
   Reserve OIDs with `src/include/catalog/unused_oids`, fill all `.dat`
   rows, bump catversion. Phase-end check: `meson compile` regenerates
   `postgres.bki` cleanly; `dev/install-debug/bin/initdb` succeeds on
   a scratch data dir. `psql -c "\dT newtype"` shows the type.
3. **Phase 3 — Casts + tests + docs.** Files: [10, 14, 15, 16, 17, 18].
   Add the regress test, plug into the parallel schedule, write the
   SGML section. Phase-end check: `meson test -C dev/build-debug
   --suite regress --test newtype` is green AND `check-world` is still
   green AND `meson test ... --test opr_sanity` passes (it cross-checks
   `pg_proc` vs `pg_operator` vs `pg_amop` for every type).



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | direct reference |
| [`memory-contexts`](../idioms/memory-contexts.md) | direct reference |

<!-- /idioms-invoked:auto -->

## Pitfalls

- **opr_sanity is the safety net.** `src/test/regress/sql/opr_sanity.sql`
  cross-validates every catalog OID reference. If you forget a
  commutator, mis-set `oprcanhash`, or have a btree opclass without all
  5 strategies, opr_sanity fails [verified-by-code](source/src/test/regress/sql/opr_sanity.sql:1).
  Run it FIRST when triaging failures; the error message names the row.
- **type_sanity** is the second safety net — checks `pg_type` row
  invariants. New types frequently trip it by forgetting `typanalyze`
  for a complex type that needs sampling, or by setting `typbyval => 't'`
  for a 16-byte type [verified-by-code](source/src/test/regress/sql/type_sanity.sql:1).
- **`unused_oids` is not deterministic across patches.** Two
  concurrent patches both grabbing OID 8204 will conflict at merge.
  Reserve high in the unused range (>= 8000) and document it; the
  hackers list has a long-running social protocol around this.
- **`typstorage` default is `'p'` (plain).** Variable-width types that
  want toasting MUST set `'x'` (external+compressed) or `'e'`
  (external only). See `pg_type.dat` row for `text` and contrast with
  a fixed-width type [verified-by-code](source/src/include/catalog/pg_type.dat:1).
- **Hash join requires `oprcanhash` on `=` AND a hash opclass support
  proc 1.** Either alone is silently insufficient; both must be
  present. Check via `EXPLAIN` on a join — if you get a nested loop
  where you expect a hash join, this is why.
- **Synchronization traps** (must change together):
  - `pg_type.dat` `typinput/output/receive/send` ↔ `pg_proc.dat`
    entries for those four function names with matching OIDs.
  - `pg_opclass.dat` `opcfamily` ↔ `pg_opfamily.dat` row that declares
    that family.
  - `pg_amop.dat` `amopopr` ↔ `pg_operator.dat` row OID.
  - `pg_amproc.dat` `amproc` ↔ `pg_proc.dat` row OID.
  - `src/backend/utils/adt/meson.build` ↔ `src/backend/utils/adt/Makefile`
    (build systems both ship, both must list the new `.c`).
  - `parallel_schedule` ↔ `expected/newtype.out` (test runs in parallel
    block, output must be deterministic w.r.t. that ordering).

## Verification (exact test invocations)

```bash
# Build + bootstrap (catversion bump invalidates old data dir)
meson compile -C dev/build-debug
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug

# The two cross-catalog sanity tests — run these BEFORE anything else
meson test -C dev/build-debug --suite regress --test opr_sanity
meson test -C dev/build-debug --suite regress --test type_sanity

# The new test for the type itself
meson test -C dev/build-debug --suite regress --test newtype

# Full sweep (catches collateral damage in unrelated tests)
meson test -C dev/build-debug --suite regress
```

If the type ships an opclass for any AM beyond btree/hash, add the
amvalidate invocation:

```bash
psql -c "SELECT amvalidate(oid) FROM pg_opfamily
         WHERE opfname = 'newtype_ops';"
```

Brand-new regress test file to register here: `newtype` (added to
`src/test/regress/parallel_schedule` and shipped as
`src/test/regress/{sql,expected}/newtype.{sql,out}`).

## Cross-refs

- Companion skills:
  `.claude/skills/catalog-conventions/SKILL.md` (BKI / OID / genbki
  pipeline), `.claude/skills/fmgr-and-spi/SKILL.md` (V1 calling
  convention, `PG_GETARG_*` macros, `Datum` semantics).
- Related scenarios:
  `scenarios/add-new-operator.md` (the rows in `pg_operator.dat`
  needed here),
  `scenarios/add-new-operator-class.md` (deeper detail on opclass +
  amop + amproc when you want more than the default btree+hash),
  `scenarios/add-new-cast.md` (the rows in `pg_cast.dat`),
  `scenarios/add-new-builtin-function.md` (every helper function is an
  instance of this).
- Idioms:
  `knowledge/idioms/catalog-conventions.md` (BKI mechanism),
  `knowledge/idioms/fmgr.md` (calling convention),
  `knowledge/idioms/memory-contexts.md` (palloc rules inside
  `*_in`/`*_recv`).
- Subsystems:
  `knowledge/subsystems/include-utils.md` (header layout for
  `src/include/utils/`),
  `knowledge/subsystems/utils-adt.md` (where `newtype.c` lives).
- Issues:
  `knowledge/issues/catalog.md` (known traps around `.dat` edits,
  catversion forgetting, OID collisions),
  `knowledge/issues/utils-adt.md` (per-type implementation gotchas).
- Reference patch: `git -C source show c7a9fa399d5` — the macaddr8
  addition; touches all 14 of the core rows and is small enough to
  read end-to-end in one sitting.
