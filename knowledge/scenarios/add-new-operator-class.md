---
scenario: add-new-operator-class
when_to_use: Make an existing data type indexable by an existing built-in index AM (btree, hash, gist, gin, spgist, brin) by registering a new operator class + family + amop + amproc rows.
companion_skills: ["catalog-conventions", "access-method-apis"]
related_scenarios: ["add-new-data-type", "add-new-index-am", "add-new-operator"]
canonical_commit: 0a6ea4001a9
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new operator class for an existing index AM

## Scope — what's in / out

**In scope:**
- Registering a new `pg_opclass` + `pg_opfamily` pair so an existing
  type becomes indexable under one of the six built-in AMs.
- The `pg_amop` rows (one per supported strategy / operator) and
  `pg_amproc` rows (one per required support function) for that AM.
- New `pg_proc.dat` rows for the C support functions if they don't
  exist yet.
- Per-AM strategy/proc number rules (btree=5 strategies + 6 procs;
  hash=1 strategy + 2 procs; gist=variable; gin=variable;
  spgist=variable; brin=variable, per opfamily).
- `catversion` bump + regress test for the new index.

**Out of scope:**
- Adding a brand-new index AM itself (handler, `IndexAmRoutine`, WAL
  rmgr) → see `add-new-index-am`.
- Adding the underlying data type → see `add-new-data-type`.
- Adding the underlying operators (`=`, `<`, `<@`, etc.) → see
  `add-new-operator`. This scenario assumes the operators already
  exist; opclass just *registers* them with an AM.
- Cross-type opclass entries (e.g. int4_ops accepting int8 RHS) —
  use the same playbook but one `amop`/`amproc` row per
  `(lefttype, righttype)` pair.

## Pre-flight

- **Companion skills:** load `catalog-conventions` (BKI / OID rules /
  catversion bump) and `access-method-apis` (per-AM strategy +
  support-function contracts and validators).
- **Canonical commit:** `0a6ea4001a9` — "Add a hash opclass for type
  'tid'." Touches `pg_opclass.dat`, `pg_opfamily.dat`, `pg_amop.dat`,
  `pg_amproc.dat`, `pg_proc.dat`, the C support funcs in
  `utils/adt/tid.c`, `catversion.h`, plus a `tidscan` regress test.
  Read it before starting; it's the minimal complete example.
- **Common pitfalls (one-line each):**
  - Wrong number of `amproc` rows — each AM's `*validate.c` will
    reject CREATE INDEX at runtime if the count doesn't match the
    AM's required-procs contract.
  - Forgot the cross-type family entries when the type already has a
    cross-type btree family (`amop`/`amproc` rows must be present for
    every `(lefttype, righttype)` your operators support).
  - Marked `opcdefault => 'f'` and then noticed the AM never picks
    your opclass without an explicit `USING <opclass>` clause in
    `CREATE INDEX`.

## File checklist (the FULL sweep)

Every row is mandatory unless explicitly noted "optional". `pg-feature-plan`
will refuse to drop these without a user override.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_opfamily.dat` | Add the `{ opfmethod, opfname }` row; opclass joins to it via `opcfamily`. One family per `(AM, type)` unless joining an existing cross-type family. [verified-by-code](source/src/include/catalog/pg_opfamily.dat:112,126) | [pg_opfamily.h.md](../files/src/include/catalog/pg_opfamily.h.md) | catalog-conventions |
| 2 | `src/include/catalog/pg_opclass.dat` | Add the `{ opcmethod, opcname, opcfamily, opcintype, opcdefault?, opckeytype? }` row. `opcdefault=t` (default) makes CREATE INDEX pick this opclass without `USING`. [verified-by-code](source/src/include/catalog/pg_opclass.h:13-16,73-77) | [pg_opclass.h.md](../files/src/include/catalog/pg_opclass.h.md) | catalog-conventions |
| 3 | `src/include/catalog/pg_amop.dat` | One row per supported `(strategy, lefttype, righttype, operator)`. Strategy numbers are AM-specific: btree=1..5 (`<`,`<=`,`=`,`>=`,`>`) [verified-by-code](source/src/include/access/stratnum.h:29-35); hash=1 (`=`) [verified-by-code](source/src/include/access/stratnum.h:41-43); gist/gin/spgist/brin: opclass-defined. | [pg_amop.h.md](../files/src/include/catalog/pg_amop.h.md) | catalog-conventions |
| 4 | `src/include/catalog/pg_amproc.dat` | One row per required support function. Procnum count is AM-specific: btree=`BTNProcs=6` (cmp, sortsupport, inrange, equalimage, options) [verified-by-code](source/src/include/access/nbtree.h:717-723); hash=2 mandatory (`HASHSTANDARD_PROC=1`, `HASHEXTENDED_PROC=2`) [verified-by-code](source/src/include/access/hash.h:355-357); gist=`GISTNProcs=12` (consistent, union, compress, decompress, penalty, picksplit, equal, distance, fetch, options, sortsupport, translate_cmptype) [verified-by-code](source/src/include/access/gist.h:32-44); gin=`GINNProcs=7` (compare, extractValue, extractQuery, consistent, comparePartial, triConsistent, options) [verified-by-code](source/src/include/access/gin.h:24-31); spgist=`SPGISTNProc=7` with 5 required [verified-by-code](source/src/include/access/spgist.h:23-31); brin=opclass-dependent (`BRIN_PROCNUM_OPCINFO`/`ADDVALUE`/`CONSISTENT`/`UNION` minimum) [verified-by-code](source/src/include/access/brin_internal.h:70-75). | [pg_amproc.h.md](../files/src/include/catalog/pg_amproc.h.md) | catalog-conventions |
| 5 | `src/include/catalog/pg_proc.dat` | Add `pg_proc` row for each support fn (C symbol → SQL function) that doesn't already exist. Required fields: `oid`, `descr`, `proname`, `prorettype`, `proargtypes`, `prosrc`. [verified-by-code](source/src/include/catalog/pg_proc.dat:2766-2767) | [pg_proc.h.md](../files/src/include/catalog/pg_proc.h.md) | catalog-conventions |
| 6 | `src/backend/utils/adt/<type>.c` | Implement the C support funcs (`hashXxx`, `hashXxxextended`, `btXxxcmp`, GiST `consistent`/`union`/…, etc.). Each with `PG_FUNCTION_INFO_V1` + `Datum f(PG_FUNCTION_ARGS)`. (NEW symbols, existing file in most cases.) | — | fmgr-and-spi |
| 7 | `src/include/<type>.h` *(optional)* | Prototype declarations for the new support functions if the type's header is the conventional home for them. | — | catalog-conventions |
| 8 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` to today's `YYYYMMDDN`. Required because any `.dat` change forces `initdb`. [verified-by-code](source/src/include/catalog/catversion.h:60) | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 9 | `src/test/regress/sql/<type>.sql` | Regress: build the index, run queries that should use it (`EXPLAIN` + result), exercise every strategy you registered. [verified-by-code](source/src/test/regress/sql/tidscan.sql) | — | testing |
| 10 | `src/test/regress/expected/<type>.out` | Expected output for above. | — | testing |
| 11 | `src/test/regress/sql/opr_sanity.sql` *(verify, not edit)* | The `opr_sanity` regress test cross-checks `pg_amop`/`pg_amproc`/`pg_opclass` for consistency. Re-run it; it will catch most registration mistakes (missing procs, wrong signatures, family/class mismatch). | — | testing |
| 12 | `doc/src/sgml/<am>.sgml` *(optional)* | If the AM's docs enumerate built-in opclasses (gist.sgml, gin.sgml, spgist.sgml, brin.sgml all do), add a row. `xindex.sgml` has the general "indexing extensibility" reference. [verified-by-code](source/doc/src/sgml/xindex.sgml) | — | catalog-conventions |

(`opcdefault` defaults to `t` via `BKI_DEFAULT(t)` [verified-by-code](source/src/include/catalog/pg_opclass.h:74); omit it unless you want a non-default opclass. `opckeytype` defaults to 0 — set it only when the on-disk index data differs from the input type [from-comment](source/src/include/catalog/pg_opclass.h:18-24).)

## Phases — suggested split for `pg-feature-plan`

The planner will use this as the §8 starting point. Each phase is a
self-contained chunk; the tree must build at the end of each phase.

1. **Phase 1 — Support functions.** Files: [6, 7 if used]. Write the
   C support functions and (if any) header prototypes; `pg_proc.dat`
   row in phase 2 will wire them up. Phase-end check: tree builds;
   the symbols are linkable.
2. **Phase 2 — Catalog wire-up.** Files: [1, 2, 3, 4, 5, 8]. Add
   opfamily + opclass rows; add `amop`/`amproc` rows for every
   strategy/proc the AM requires; add `pg_proc` rows for the new
   support fns; bump `CATALOG_VERSION_NO`. Run
   `src/include/catalog/duplicate_oids` to confirm no OID collision
   (project policy is globally unique OIDs
   [from-comment](source/src/include/catalog/duplicate_oids:8-11)).
   Phase-end check: `make` succeeds; `initdb` succeeds; `psql -c
   '\dAo+ <am>'` shows the new opclass.
3. **Phase 3 — Tests + docs.** Files: [9, 10, 11, 12]. Regress test
   that exercises every registered strategy; re-run `opr_sanity` to
   validate the catalog rows; optional SGML edit if the AM's docs
   list built-in opclasses. Phase-end check: `meson test -C
   dev/build-debug --suite regress` green, with `opr_sanity` and the
   new test both passing.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/access` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/backend/access`, `src/test/regress` |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/test/regress` |
| [`peter-geoghegan`](../personas/peter-geoghegan.md) | `src/include/access/nbtree.h`, `src/backend/access/nbtree` |
| [`alexander-korotkov`](../personas/alexander-korotkov.md) | `src/backend/access/gin` |
| [`david-rowley`](../personas/david-rowley.md) | `src/test/regress` |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include` |
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
| [`hash-bucket-split`](../idioms/hash-bucket-split.md) | shares files: `src/include/access/hash.h` |
| [`hash-overflow-pages`](../idioms/hash-overflow-pages.md) | shares files: `src/include/access/hash.h` |
| [`hash-page-layout`](../idioms/hash-page-layout.md) | shares files: `src/include/access/hash.h` |
| [`spgist-insert-and-picksplit`](../idioms/spgist-insert-and-picksplit.md) | shares files: `src/include/access/spgist.h` |
| [`spgist-scan-and-consistent`](../idioms/spgist-scan-and-consistent.md) | shares files: `src/include/access/spgist.h` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Missing required support procs** — the AM's `<am>validate.c`
  (e.g. `src/backend/access/hash/hashvalidate.c`,
  `src/backend/access/gist/gistvalidate.c`) runs at `amvalidate` time
  (CREATE OPERATOR CLASS, `pg_amcheck`, regress `opr_sanity`). It
  enumerates the family's `amproc` rows and emits `WARNING: ...
  family ... is missing support function ...`. Required-proc lists
  per AM are in the per-AM `*.h` headers cited in row 4.
  [verified-by-code](source/src/backend/access/hash/hashvalidate.c),
  [verified-by-code](source/src/backend/access/gist/gistvalidate.c)
- **Wrong strategy number for the operator semantics** — there's no
  type-checker forcing `amopstrategy => '3'` to mean `=`. If you
  register `=` under btree strategy 1 (`<`), the planner will
  generate wrong plans and queries will silently return wrong rows.
  Cross-check `stratnum.h` for btree/hash; for gist/gin/spgist/brin
  the opclass defines its own numbering scheme (consistent across
  the family) — document it in a comment near the `amop` rows.
  [verified-by-code](source/src/include/access/stratnum.h:29-43)
- **Opfamily reused across cross-type entries** — if you're adding a
  cross-type opclass (e.g. `tid_ops` accepting `tidvector` RHS),
  EVERY `(lefttype, righttype)` pair in the family must have full
  `amop`+`amproc` coverage. Partial coverage is silently broken;
  `opr_sanity` catches some but not all cases.
- **Forgot `BKI_LOOKUP` for `opfmethod`** — `pg_opclass.dat`'s
  `opcfamily` column expects `'<am>/<famname>'` form, not a bare OID.
  Same for `pg_amop.dat`'s `amopfamily`/`amopmethod`. Mismatched
  syntax produces an opaque `genbki.pl` error.
  [verified-by-code](source/src/include/catalog/pg_opclass.h:68)
- **`opcdefault=t` collision** — at most one opclass per
  `(opcmethod, opcintype)` may be default
  [from-comment](source/src/include/catalog/pg_opclass.h:13-16).
  Adding a second default for an AM/type combo isn't index-enforced
  but breaks user expectations and breaks CREATE INDEX defaulting
  semantics. If a default already exists, set `opcdefault => 'f'`.
- **Synchronization traps** (sibling files that must change
  together):
  - `pg_opclass.dat` ↔ `pg_opfamily.dat` — every `opcfamily`
    reference must resolve. `genbki.pl` errors loudly on this.
  - `pg_amop.dat` ↔ `pg_proc.dat` — every `amopopr` must point at an
    existing `pg_operator` row whose underlying function is in
    `pg_proc.dat`.
  - `pg_amproc.dat` ↔ `pg_proc.dat` — every `amproc` symbol must be
    a `pg_proc` row.
  - `pg_proc.dat` ↔ `src/backend/utils/adt/<type>.c` — every `prosrc`
    must be a `PG_FUNCTION_INFO_V1`-decorated C symbol the linker
    can find. Missing symbol → opaque link-time failure or runtime
    "function not found in shared library".
  - Any `.dat` edit ↔ `catversion.h` — bump or your cluster won't
    start [from-comment](source/src/include/catalog/catversion.h:26-29).

## Verification (exact test invocations)

```bash
# Build + initdb (catversion bump forces fresh initdb)
ninja -C dev/build-debug install
dev/install-debug/bin/initdb -D dev/data-debug

# Regression scope this scenario must exercise
meson test -C dev/build-debug --suite regress --test regress

# Specifically:
#  - opr_sanity     — catalog consistency cross-checks
#  - <type>         — your new test file from row 9
#  - create_index   — broad index-creation coverage

# Validate the opclass at SQL level (smoke test):
psql -c "SELECT amvalidate('<your_opclass_oid>'::regopclass::oid);"
# Returns true when the AM's *validate.c accepts the family.

# Per-AM validator code path:
#  - btree → src/backend/access/nbtree/nbtvalidate.c
#  - hash  → src/backend/access/hash/hashvalidate.c
#  - gist  → src/backend/access/gist/gistvalidate.c
#  - gin   → src/backend/access/gin/ginvalidate.c
#  - spgist → src/backend/access/spgist/spgvalidate.c
#  - brin  → src/backend/access/brin/brin_validate.c
```

If the change adds a brand-new test, name it explicitly: e.g.
`src/test/regress/sql/<type>_index.sql` + matching `expected/`. Add
it to the regress schedule (`src/test/regress/parallel_schedule`)
unless reusing an existing test file (the canonical commit reused
`tidscan.sql`).

## Cross-refs

- Companion skills: `.claude/skills/catalog-conventions/SKILL.md`,
  `.claude/skills/access-method-apis/SKILL.md`.
- Related scenarios: `scenarios/add-new-data-type.md`,
  `scenarios/add-new-index-am.md`, `scenarios/add-new-operator.md`,
  `scenarios/bump-catversion.md`, `scenarios/add-new-builtin-function.md`
  (when new support fns are needed).
- Idioms: `knowledge/idioms/catalog-conventions.md` (BKI, OID
  policy, catversion bump rules), `knowledge/idioms/fmgr.md`
  (PG_FUNCTION_INFO_V1 signature contract).
- Subsystems: `knowledge/subsystems/access-nbtree.md`,
  `knowledge/subsystems/catalog.md`,
  `knowledge/subsystems/include-access.md` (for `stratnum.h`,
  `amvalidate.h`).
- Issues: `knowledge/issues/<subsystem>.md` rows on opclass
  registration mistakes (catalog and per-AM validators).
- Reference patch (canonical_commit):
  `git -C source show 0a6ea4001a9`.
