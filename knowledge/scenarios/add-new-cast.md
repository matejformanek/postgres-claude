---
scenario: add-new-cast
when_to_use: A new built-in cast from type A to type B — implicit, assignment, or explicit, with or without a backing function.
companion_skills: [catalog-conventions]
related_scenarios: [add-new-data-type, add-new-builtin-function]
canonical_commit: ba21f5bf8af
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new built-in type cast

## Scope — what's in / out

**In scope:**
- A new `pg_cast.dat` entry between two existing built-in types.
- The C function backing the cast (if `castmethod = 'f'`), via the
  usual `pg_proc.dat` + `utils/adt/<file>.c` pattern.
- Choosing `castcontext` (`i` / `a` / `e`) and `castmethod`
  (`f` / `b` / `i`) correctly — the resolution-lattice consequences
  are the load-bearing part of this scenario.
- Regression coverage (a new `*.sql` / `*.out` pair, or extension of
  an existing per-type test file) + sanity checks in
  `opr_sanity.sql`.

**Out of scope:**
- The source or target type itself does not yet exist
  → compose with `add-new-data-type` (#3); the type's "I/O + binary
  coercion to text/bytea" casts are usually part of that scenario's
  bundle.
- A new SQL-level `CREATE CAST` issued by a user extension at
  runtime → that goes through `CastCreate()` in
  `src/backend/catalog/pg_cast.c` and is documented in
  `doc/src/sgml/ref/create_cast.sgml`; built-in casts skip the
  utility statement and go straight into the catalog `.dat` file.
- Domain casts — domains are always implicitly coercible to/from
  their base type via `getBaseType()` in `find_coercion_pathway`
  [verified-by-code](../../source/src/backend/parser/parse_coerce.c:3168-3175),
  no `pg_cast` row is involved.

## Pre-flight

- **Companion skills:** load `catalog-conventions` — the
  `pg_cast.dat` + `pg_proc.dat` edits, OID picking, and
  `CATALOG_VERSION_NO` bump are pure catalog-plumbing operations
  governed by that skill.
- **Canonical commit:** `ba21f5bf8af` — *"Allow explicit casting
  between bytea and uuid."* Seven files: docs + C impl in
  `utils/adt/bytea.c` + `catversion.h` bump + `pg_cast.dat` + 2
  rows in `pg_proc.dat` + regression `uuid.sql` / `uuid.out`. Read
  it before starting; it is the minimal reference shape.
- **Common pitfalls (one-line each):**
  - **Implicit-cast contagion** — marking a new cast `i` can make
    previously-unambiguous function/operator resolutions ambiguous
    elsewhere. The `create_cast.sgml` doc explicitly warns against
    this
    [from-docs](../../source/doc/src/sgml/ref/create_cast.sgml:138-148).
    Default to `a` (assignment) unless the type pair is
    same-category and the community has accepted `i` for similar
    casts.
  - **`castfunc` signature mismatch** —
    `opr_sanity.sql:481-490` checks that
    `castfunc(castsource) → casttarget` is binary-coercible at the
    edges
    [verified-by-code](../../source/src/test/regress/sql/opr_sanity.sql:481-490).
    Wrong arg type or return type → opr_sanity fails.
  - **Forgetting `CATALOG_VERSION_NO`** — see
    `knowledge/idioms/catalog-conventions.md` §3. Symptom: other
    devs' clusters refuse to start
    [from-comment](../../source/src/include/catalog/catversion.h:7-14).

## File checklist (the FULL sweep)

Every row mandatory unless flagged "(optional)". `pg-feature-plan`
will refuse to drop these without an explicit user override.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_cast.dat` | The actual new row: `castsource`, `casttarget`, `castfunc`, `castcontext`, `castmethod` [verified-by-code](../../source/src/include/catalog/pg_cast.dat:16-22). OIDs are NOT assigned by hand here — comment at top says "we don't bother to assign them manually" [from-comment](../../source/src/include/catalog/pg_cast.dat:14-16). | — | catalog-conventions |
| 2 | `src/include/catalog/pg_proc.dat` | New row(s) for the C function(s) that implement the cast (only if `castmethod = 'f'`). The `prosrc` value is the C symbol name; `proargtypes` MUST be exactly `castsource` (single arg) and `prorettype` MUST be `casttarget`, else `opr_sanity.sql:481-490` fails [verified-by-code](../../source/src/test/regress/sql/opr_sanity.sql:481-490). Two rows if the cast is bidirectional. | — | catalog-conventions |
| 3 | `src/backend/utils/adt/<type>.c` | The C body, normally living alongside the source-type's existing I/O routines (e.g. `bytea.c` for `bytea↔uuid` in the canonical commit). Standard `PG_FUNCTION_INFO_V1` + `Datum xxx_to_yyy(PG_FUNCTION_ARGS)` shape. Not needed for `castmethod = 'b'` or `'i'`. | — | catalog-conventions |
| 4 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` — any `.dat` row change requires it [from-comment](../../source/src/include/catalog/catversion.h:26-29). | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 5 | `src/test/regress/sql/<type>.sql` + matching `expected/<type>.out` | Exercise the new cast in both `CAST(x AS y)` form and the `::` form. For implicit casts, add a query that exercises the implicit path (e.g. passing `castsource` to a function taking `casttarget`). | — | catalog-conventions |
| 6 | `doc/src/sgml/datatype.sgml` (or per-type SGML) | Document the new cast in user-facing prose. Canonical commit added 11 lines under the `bytea` datatype section [verified-by-code](../../source/doc/src/sgml/datatype.sgml). For purely-internal casts this is sometimes skipped, but any user-visible cast must be documented. | — | catalog-conventions |
| 7 | `src/test/regress/sql/opr_sanity.sql` (verify only — usually no edit) | Existing checks run automatically: `castsource/casttarget ≠ 0`, `castcontext ∈ {e,a,i}`, `castmethod ∈ {f,b,i}` consistency, function-signature edges, length-coercion shape [verified-by-code](../../source/src/test/regress/sql/opr_sanity.sql:442-516). Your row must pass without editing this file. | — | catalog-conventions |
| 8 | `src/test/regress/sql/type_sanity.sql` (verify only) | Sister-suite to opr_sanity for type plumbing — run as part of `--suite regress`. Not normally edited. | — | catalog-conventions |
| 9 (optional) | `src/test/regress/parallel_schedule` | If you create a brand-new `*.sql` test file (rather than extending an existing one), wire it into a parallel group here. | — | catalog-conventions |

(Use `—` in the per-file doc column for genuinely-new files;
otherwise the entry should exist in `knowledge/files/` and link.)

The other consumer that you should NOT need to edit but should
understand: `src/backend/parser/parse_coerce.c` —
`find_coercion_pathway()` is what reads your new row from
`CASTSOURCETARGET` syscache and decides whether the cast is
applicable in the current `CoercionContext`
[verified-by-code](../../source/src/backend/parser/parse_coerce.c:3158-3227).
The `ccontext >= castcontext` comparison is what makes implicit
casts ALSO available in assignment/explicit contexts (the
`CoercionContext` enum in `primnodes.h` is ordered explicit <
assignment < implicit on purpose
[from-comment](../../source/src/include/catalog/pg_cast.h:71-77)).

## Phases — suggested split for `pg-feature-plan`

The planner uses this as the §8 starting point. Each phase is
self-contained; the tree must build at the end of each phase.

1. **Phase 1 — Cast function (C body + pg_proc).** Files: [2, 3].
   Edits: implement the C cast function(s) in
   `src/backend/utils/adt/<type>.c`; add `pg_proc.dat` row(s) with
   `proname`, `prorettype = casttarget`, `proargtypes = castsource`,
   `prosrc = <C symbol>`. Phase-end check: `meson compile`
   succeeds; the new function is callable from SQL as a regular
   function (without going through CAST yet). Skip this phase
   entirely if `castmethod ∈ {b, i}`.
2. **Phase 2 — Catalog wiring.** Files: [1, 4]. Edits: add the
   `pg_cast.dat` row referencing the function (or `castfunc => '0'`
   for `castmethod = 'b'`); bump `CATALOG_VERSION_NO`. Phase-end
   check: `initdb` succeeds against the rebuilt binary;
   `./duplicate_oids` in `src/include/catalog` returns empty;
   `SELECT * FROM pg_cast WHERE castsource = '...'::regtype` shows
   the new row.
3. **Phase 3 — Tests + docs.** Files: [5, 6, 9?]. Edits: extend
   `<type>.sql` regression with positive and negative cases (NULL,
   overflow if applicable, both `CAST` and `::` syntax, implicit
   path if `castcontext = 'i'`); add SGML prose. Phase-end check:
   `meson test --suite regress` green including opr_sanity and
   type_sanity.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/backend/parser` (+1) |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/test/regress` |
| [`david-rowley`](../personas/david-rowley.md) | `src/test/regress` |
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/test/regress` |
| [`tom-lane`](../personas/tom-lane.md) | `src/test/regress` |

<!-- /persona-reviewers:auto -->

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

- **Implicit-cast contagion.** Adding a new `i` cast widens the
  parser's resolution lattice. Common failure mode: an existing
  function call now matches two candidate paths and the parser
  raises "function is not unique". `create_cast.sgml` is explicit:
  *"It is wise to be conservative about marking casts as implicit"*
  [from-docs](../../source/doc/src/sgml/ref/create_cast.sgml:138-148).
  Same-numeric-category implicit casts are accepted; cross-category
  is not. Default to `a`.
- **Wrong castfunc signature.** `opr_sanity.sql:481-490` enforces:
  `castfunc.proargtypes[0]` must be binary-coercible from
  `castsource` (with the documented exception that `character` may
  use a `text`-taking function), AND `castfunc.prorettype` must be
  binary-coercible to `casttarget`
  [verified-by-code](../../source/src/test/regress/sql/opr_sanity.sql:481-490).
  If your cast needs a typmod-aware variant, use a 3-arg function
  (`{value, typmod, isExplicit}`) — also enforced by opr_sanity
  same area.
- **Length-coercion casts have an extra rule.** If
  `castsource = casttarget`, the row represents a length-coercion
  (e.g. `varchar(20) → varchar(10)`). `castfunc` MUST be nonzero
  and its function must take ≥2 args
  [verified-by-code](../../source/src/test/regress/sql/opr_sanity.sql:464-470).
  Don't accidentally create such a row.
- **`castmethod = 'b'` requires `castfunc = 0`** and vice versa.
  `opr_sanity.sql:455-458` catches it
  [verified-by-code](../../source/src/test/regress/sql/opr_sanity.sql:455-458).
  Binary-coercible casts are pointer-relabel-only (no run-time
  work), so a function would be nonsensical.
- **`castmethod = 'i'` (I/O) is rarely what you want.** It tells
  the parser "fall back to source's `typoutput` then target's
  `typinput`." Slow, format-dependent, and `find_coercion_pathway`
  already auto-falls-back to CoerceViaIO for assignment-to-string
  and explicit-from-string without needing an explicit row
  [verified-by-code](../../source/src/backend/parser/parse_coerce.c:3262-3290).
  Add an explicit `'i'`-method row only when you specifically want
  to *override* the default with a different context.
- **Symmetric casts are TWO rows.** `bytea→uuid` and `uuid→bytea`
  are independent `pg_cast` rows with independent contexts and
  independent functions. The canonical commit adds both (and the
  matching pair of `pg_proc` rows). Don't assume the reverse cast
  is implied.
- **Synchronization traps.** If you edit `pg_cast.dat` you almost
  always also edit `pg_proc.dat` and `catversion.h`. If you add a
  new `*.sql` regression test, you must also add the matching
  `expected/*.out` and (if it's a new file) wire it into
  `parallel_schedule`.

## Verification (exact test invocations)

```bash
# Full regression suite — opr_sanity and type_sanity will run as
# part of this and exercise every pg_cast row including yours.
meson test -C dev/build-debug --suite regress

# The specific per-type test you extended (replace <type>).
meson test -C dev/build-debug --suite regress --test <type>

# The two sanity tests that catch malformed pg_cast / pg_proc rows.
meson test -C dev/build-debug --suite regress --test opr_sanity
meson test -C dev/build-debug --suite regress --test type_sanity

# Catalog hygiene: globally unique OIDs.
( cd source/src/include/catalog && ./duplicate_oids )   # expect empty
```

If the change adds a brand-new regression `.sql`, name it
explicitly here (e.g. `cast_mytype.sql` wired into
`parallel_schedule`). The canonical commit avoided this by
extending the existing `uuid.sql` test.

## Cross-refs

- Companion skills: `.claude/skills/catalog-conventions/SKILL.md`.
- Related scenarios: `scenarios/add-new-data-type.md`,
  `scenarios/add-new-builtin-function.md`,
  `scenarios/bump-catversion.md`.
- Idioms: `knowledge/idioms/catalog-conventions.md` (BKI pipeline,
  OID rules, catversion bump, syscache mechanics — §5
  "Adding a new system (builtin) function" is the directly
  analogous procedure),
  `knowledge/idioms/fmgr.md` (for the C cast function signature).
- Subsystems: `knowledge/subsystems/parser-and-rewrite.md`
  (`parse_coerce.c` consumer of `CASTSOURCETARGET` syscache),
  `knowledge/subsystems/catalog.md` (the bigger picture of the
  catalog `.dat` regeneration loop).
- Files: `knowledge/files/src/include/catalog/pg_cast.h.md`,
  `knowledge/files/src/backend/catalog/pg_cast.c.md`,
  `knowledge/files/src/backend/parser/parse_coerce.c.md`,
  `knowledge/files/src/include/catalog/catversion.h.md`.
- Issues: `knowledge/issues/catalog.md` for known traps in the
  affected area.
- Reference patch (canonical_commit):
  `git -C source show ba21f5bf8af` — 7 files, 79 insertions, the
  minimal "explicit cast with a function in each direction" shape.
