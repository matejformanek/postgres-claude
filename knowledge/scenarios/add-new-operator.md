---
scenario: add-new-operator
when_to_use: Adding a new built-in SQL operator — a `pg_operator.dat` row that names an underlying `pg_proc` function, optional commutator/negator, and selectivity estimators.
companion_skills: ["catalog-conventions","fmgr-and-spi"]
related_scenarios: ["add-new-builtin-function","add-new-data-type","add-new-operator-class"]
canonical_commit: 4d7684cc754
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new built-in operator

## Scope — what's in / out

**In scope:**
- A new row in `src/include/catalog/pg_operator.dat` that wires a SQL
  operator symbol (`@>`, `<<`, `=`, …) to an existing or new C
  function.
- Filling out `oprcom` / `oprnegate` / `oprrest` / `oprjoin` /
  `oprcanmerge` / `oprcanhash` correctly.
- The underlying `pg_proc.dat` entry for the implementation function
  (if not already present) and for any new selectivity estimator.
- Regression coverage and the catversion bump.

**Out of scope:**
- Brand-new scalar type the operator works on → see
  `scenarios/add-new-data-type.md`.
- Hooking the operator into an existing index AM (btree/hash/gin/…)
  → that's `pg_amop.dat` + `pg_amproc.dat`, covered by
  `scenarios/add-new-operator-class.md`.
- The C function itself if it's a wholly new builtin → split the
  function-add into `scenarios/add-new-builtin-function.md`; this
  playbook assumes `prosrc` already exists.

## Pre-flight

- **Companion skills:** load `catalog-conventions` (OID rules, BKI
  pipeline, `.dat` syntax, catversion discipline) and `fmgr-and-spi`
  (PG_FUNCTION_ARGS calling convention, return-type rules) before
  starting. They cover prerequisites this playbook assumes.
- **Canonical commit:** `4d7684cc754` — *"Implement operators for
  checking if the range contains a multirange"*. Two new `@>` /
  `<@` operators, two new `pg_proc` entries, doc + regress update,
  catversion bump. The shape of every operator-add patch.
  `git -C source show 4d7684cc754` is the reference example.
- **Common pitfalls (one-line each):**
  - Setting `oprcanhash => 't'` on an operator whose function is not
    a strict equality with hash-compatible semantics — planner blindly
    trusts the flag and produces wrong join results
    [verified-by-code](source/src/backend/optimizer/plan/initsplan.c:2622).
  - Forgetting that `oprrest` / `oprjoin` / `oprnegate` are only legal
    on boolean-returning binary operators (`OperatorValidateParams`
    rejects them in DDL but the BKI bootstrap path will *not* — silent
    catalog garbage if you cheat)
    [verified-by-code](source/src/backend/catalog/pg_operator.c:586-610).
  - Commutator/negator self-reference: if the operator is its own
    commutator (e.g. `=` on a symmetric type), the `.dat` syntax is
    `oprcom => '=(foo,foo)'` referencing the OID being defined; if
    nothing else defines it yet, `genbki.pl` errors out unless you use
    the OID-by-symbol trick (see Pitfalls §3).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_operator.dat` | The new operator row(s): `oid`, `oprname`, `oprleft`, `oprright`, `oprresult`, `oprcode`, optional `oprcom`/`oprnegate`/`oprrest`/`oprjoin`/`oprcanmerge`/`oprcanhash` [verified-by-code](source/src/include/catalog/pg_operator.dat:20-26). | — (no per-file doc; `.dat` files aren't documented individually) | catalog-conventions |
| 2 | `src/include/catalog/pg_operator.h` | Read-only reference for column semantics + `BKI_LOOKUP` targets [verified-by-code](source/src/include/catalog/pg_operator.h:46-77). Only edit if you need `oid_symbol` exposed as a C macro (rare; see `BooleanEqualOperator` precedent at `pg_operator.dat:58`). | [pg_operator.h.md](../files/src/include/catalog/pg_operator.h.md) | catalog-conventions |
| 3 | `src/include/catalog/pg_proc.dat` | The implementation function row (`prosrc => 'my_op_fn'`) if not already present; same for any new selectivity estimator (`oprrest`/`oprjoin` target) [verified-by-code](source/src/include/catalog/pg_proc.dat:14-38). | [pg_proc.h.md](../files/src/include/catalog/pg_proc.h.md) | catalog-conventions |
| 4 | `src/backend/utils/adt/<name>.c` | The C implementation: `PG_FUNCTION_INFO_V1(my_op_fn)` + `Datum my_op_fn(PG_FUNCTION_ARGS)`. May exist already if you're just adding an operator over an existing function; otherwise NEW. | — (path varies) | fmgr-and-spi |
| 5 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` — every `.dat` edit requires it; old clusters refuse to start otherwise [from-comment](source/src/include/catalog/catversion.h:26-29). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 6 | `src/test/regress/sql/<area>.sql` | SQL regression coverage: exercise the operator, its commutator path (planner-rewritten), and `WHERE`/`JOIN ON` usage so estimators get called [verified-by-code](source/src/backend/utils/adt/selfuncs.c:292-302). | — | — |
| 7 | `src/test/regress/expected/<area>.out` | Expected output for the new SQL lines. Regenerate via `meson test --setup running …` or by hand. | — | — |
| 8 | `doc/src/sgml/func.sgml` (or `datatype-*.sgml`) | User-facing docs: operator table entry describing semantics + return type. Look at `4d7684cc754` for the row shape. | — | — |
| 9 | `src/include/catalog/pg_amop.dat` (optional) | Only if the new operator participates in an existing index opfamily (`<`, `<=`, `>=`, `>`, `=`, GiST/GIN strategy numbers). Skip otherwise; that's the operator-class scenario [verified-by-code](source/src/include/catalog/pg_amop.h:11-24). | [pg_amop.h.md](../files/src/include/catalog/pg_amop.h.md) | catalog-conventions |
| 10 | `src/backend/utils/adt/selfuncs.c` (optional) | Only if you write a *new* restriction/join estimator instead of reusing `eqsel`/`neqsel`/`scalarltsel`/`scalargtsel`/`scalarlesel`/`scalargesel`/`eqjoinsel`/`neqjoinsel`/`scalarltjoinsel`/`scalargtjoinsel`/etc. The vast majority of operators reuse existing estimators [verified-by-code](source/src/backend/utils/adt/selfuncs.c:292-635). | [selfuncs.c.md](../files/src/backend/utils/adt/selfuncs.c.md) | — |

(`.dat` files have no per-file doc by project convention; the
companion `_d.h` is generated.)

## Phases — suggested split for `pg-feature-plan`

The tree must build cleanly at the end of each phase.

1. **Phase 1 — Implementation function.** Files: [3, 4]. Add the
   `pg_proc.dat` row(s) and the C function(s) (`PG_FUNCTION_INFO_V1` +
   body). If the function already exists, skip — Phase 1 is a no-op.
   Phase-end check: `meson compile -C dev/build-debug` succeeds; new
   symbols exported by `nm dev/build-debug/src/backend/postgres |
   grep my_op_fn`.

2. **Phase 2 — Catalog wiring.** Files: [1, 2 (read-only), 5,
   optionally 9]. Pick OIDs via `src/include/catalog/unused_oids`
   (random in 8000-9999 per project policy
   [verified-by-code](source/src/include/catalog/unused_oids:73-78));
   add the `pg_operator.dat` row(s); bump catversion. If the operator
   is indexable, add `pg_amop.dat` row(s). Phase-end check:
   `cd src/include/catalog && ./duplicate_oids` prints nothing;
   `meson compile && initdb -D dev/data-debug` finishes clean.

3. **Phase 3 — Tests + docs.** Files: [6, 7, 8, optionally 10]. Add
   SQL regress lines that hit both restriction (`WHERE x op y`) and
   join (`a JOIN b ON a.x op b.y`) planner paths so the estimators get
   exercised. Phase-end check: `meson test -C dev/build-debug --suite
   regress` green; `psql -c "\do+ <opname>"` shows the new operator.



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | direct reference |

<!-- /idioms-invoked:auto -->

## Pitfalls

1. **`oprcanhash` is a hard contract, `oprcanmerge` is a hint.**
   `op_hashjoinable()` and the planner trust `oprcanhash` outright —
   wrong setting → wrong join results. `oprcanmerge` is sanity-checked
   against `get_mergejoin_opfamilies()` at plan time, so a wrong
   setting demotes the operator to non-mergejoinable but doesn't
   corrupt results
   [verified-by-code](source/src/backend/optimizer/plan/initsplan.c:2615-2625).
   The rule: only set `oprcanhash => 't'` if the function is strict,
   returns bool, and the equality relation matches the type's hash
   function (the operator family for hash indexes will need a matching
   `pg_amproc` entry — see `add-new-operator-class`).

2. **Boolean-only attributes.** `oprnegate`, `oprrest`, `oprjoin`,
   `oprcanmerge`, `oprcanhash` are legal only when `oprresult = bool`
   and both args are present (binary op). DDL (`CREATE OPERATOR`)
   rejects violations via `OperatorValidateParams`
   [verified-by-code](source/src/backend/catalog/pg_operator.c:556-611),
   but `genbki.pl` does **not** run this check — it'll happily insert
   garbage. Manually mirror the rules in §2 of
   `OperatorValidateParams` when writing the `.dat` row.

3. **Commutator/negator forward references.** If operator A names B
   as its commutator and B doesn't exist yet, `genbki.pl` resolves the
   reference via the `oprname(oprleft,oprright)` lookup against the
   final `.dat` (both rows are loaded before resolution). If A is its
   own commutator (e.g. `=` over a symmetric type), `oprcom =>
   '=(foo,foo)'` referencing itself works because the lookup happens
   after all rows are parsed. The reverse-link maintenance that
   `OperatorUpd()` does for runtime `CREATE OPERATOR` is **not** done
   by BKI bootstrap — both rows must explicitly point at each other.

4. **Selectivity estimator typing.** A new `oprrest` function must
   match signature `float8 (internal, oid, internal, int4)` and
   `oprjoin` must match `float8 (internal, oid, internal, int2,
   internal)`. The `pg_proc.dat` entry for it must have the right
   `proargtypes` and `prorettype => 'float8'`; pick from the menu in
   `selfuncs.c` (eqsel, neqsel, scalarltsel, scalarlesel, scalargtsel,
   scalargesel, areasel, positionsel, contsel, …) before writing a
   custom one [verified-by-code](source/src/backend/utils/adt/selfuncs.c:292-635).

5. **Operator name characters.** `oprname` is restricted to the set
   `+ - * / < > = ~ ! @ # % ^ & | ` and `?`. Multi-character operators
   ending in `+` or `-` need at least one of `~ ! @ # % ^ & | ? `
   present (parser ambiguity rule). Documented in
   `doc/src/sgml/ref/create_operator.sgml`; the BKI path silently
   accepts invalid names but the parser will fail to lex `x foo y` at
   query time [from-docs](https://www.postgresql.org/docs/current/sql-createoperator.html).

6. **Synchronization traps (sibling files that must change together):**
   - `pg_operator.dat` row ↔ `pg_proc.dat` row for `oprcode`: the
     symbolic name in `oprcode => 'foo'` MUST resolve to exactly one
     `pg_proc.dat` row with matching `proargtypes`. Genbki errors
     otherwise.
   - `pg_operator.dat` ↔ `catversion.h`: any `.dat` edit requires a
     catversion bump in the same commit.
   - `pg_operator.dat` row ↔ `pg_amop.dat` row (if indexable):
     dropping the operator entry orphans the `pg_amop` row; the
     reverse (adding `pg_amop` without `pg_operator`) is a `BKI_LOOKUP`
     resolution error.

## Verification (exact test invocations)

```bash
# Pre-flight: OID uniqueness (must print nothing)
cd source/src/include/catalog && ./duplicate_oids

# Full regress (covers create_operator, alter_operator, drop_operator,
# plus whatever area suite you added SQL into)
meson test -C dev/build-debug --suite regress

# If your area is type-specific, narrow it
meson test -C dev/build-debug --suite regress --test create_operator
meson test -C dev/build-debug --suite regress --test <area>   # e.g. int8, multirangetypes

# Sanity: psql shows the operator
dev/install-debug/bin/psql -c "\do+ <opname>"

# Sanity: planner uses the right estimator
dev/install-debug/bin/psql -c "EXPLAIN (ANALYZE, VERBOSE)
  SELECT * FROM t WHERE col <opname> 42;"
```

For a brand-new operator on a brand-new type, add a dedicated test in
`src/test/regress/sql/<typename>.sql` and add it to
`src/test/regress/parallel_schedule`. For changes affecting hash/merge
join planning, add a join query to the suite so the cost path is
exercised.

## Cross-refs

- Companion skills: `.claude/skills/catalog-conventions/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md`.
- Related scenarios: `scenarios/add-new-builtin-function.md` (the
  `oprcode`/`oprrest`/`oprjoin` C function), `scenarios/add-new-data-type.md`
  (when you need the *whole* type+ops+opclass sweep),
  `scenarios/add-new-operator-class.md` (wiring the operator into an
  index AM via `pg_amop` + `pg_amproc`).
- Idioms: `knowledge/idioms/catalog-conventions.md` (BKI / OID / .dat
  syntax), `knowledge/idioms/fmgr.md` (PG_FUNCTION_ARGS calling
  convention for `oprcode`).
- Subsystems: `knowledge/subsystems/optimizer.md` (where `oprcanhash`
  / `oprcanmerge` / selectivity are consumed),
  `knowledge/subsystems/parser-and-rewrite.md` (how operator lookup
  by name+types works at parse time).
- Issues: `knowledge/issues/catalog.md` (catversion-bump traps, OID
  collisions, BKI quirks).
- Reference patch (canonical_commit): `git -C source show 4d7684cc754`
  — multirange `@>` / `<@` operator additions; minimal, complete,
  idiomatic. Also worth reading: `a148f8bc04b` for a planner-support
  attachment via `prosupport`, and `06e94eccfd9` for the
  hash-correctness landmine in pitfall §1.
