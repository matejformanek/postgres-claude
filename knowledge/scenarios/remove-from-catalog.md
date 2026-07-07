---
scenario: remove-from-catalog
when_to_use: I want to REMOVE one or more entries from `pg_operator.dat` / `pg_proc.dat` / `pg_aggregate.dat` / `pg_cast.dat` — typically because a new keyword, sigil, or lexer rule is reserving the character/name for a different purpose.
companion_skills: ["parser-and-nodes", "catalog-conventions"]
related_scenarios: ["add-new-sql-keyword", "bump-catversion", "add-new-operator", "add-new-cast", "add-new-builtin-function"]
canonical_commit: e18b0cb7344
last_verified_commit: e18b0cb7344
---

# Scenario — Remove entries from a system catalog

## Scope — what's in / out

**In scope:**
- Dropping one or more rows from `pg_operator.dat`, `pg_proc.dat`,
  `pg_aggregate.dat`, `pg_cast.dat`, `pg_type.dat`, or any other
  `src/include/catalog/*.dat` file.
- The downstream sweep that comes with the removal:
  - `opr_sanity` / `type_sanity` regression diffs.
  - Orphaned `descr =>` fields when the row carried the description
    for a sibling proc.
  - Cross-catalog references (`pg_amop`, `pg_amproc`, `pg_opclass`,
    `pg_opfamily`, `pg_depend` snapshots) that pointed at the removed
    row.
  - `catversion.h` bump (always required — initdb invalidates).
  - `contrib/*/sql/` tests that use the removed entry by name.
- The audit must run BEFORE the removal commit, not after — see
  `add-new-sql-keyword.md` row 18 for the composite case where a new
  lexer token forces a removal.

**Out of scope:**
- Renaming an entry (write the new entry + remove the old in the
  same commit; both halves still apply here for the removal side).
- Removing a contrib extension's own catalog rows (handled by the
  extension's `--N.M-N.M+1.sql` upgrade script, not the core catalog
  files).
- Dropping a whole catalog (e.g. retiring `pg_largeobject_metadata`)
  — that's a much larger change-class, escalate to the user.

## Pre-flight

- **Companion skills:** load `parser-and-nodes` (for the lexer /
  operator interaction context) and `catalog-conventions` (for the
  `.dat` syntax + initdb cycle).
- **Canonical commit:** *(no clean upstream example as of
  e18b0cb7344 — most upstream removals are bundled with broader
  renames or refactors.)* The **sesvars calibration Phase 0** is the
  reference implementation: it dropped 6 `@` unary operator rows
  (`int2abs`, `int4abs`, `int8abs`, `float4abs`, `float8abs`,
  `numeric_abs`) from `pg_operator.dat` because the new `@{ident}`
  lexer rule hijacked the `@` prefix. The Phase 0 commit in
  `postgresql-dev-feature-sesvars` is the worked example.
- **Common pitfalls (one-line each):**
  - `opr_sanity` "functions with descriptions" check fails because
    `descr =>` lived on the operator row and the proc row inherits
    it via the operator→proc pointer (F6).
  - `opr_sanity.sql` / `type_sanity.sql` queries that enumerate by
    name produce expected-output diffs that need regeneration.
  - `pg_amop` / `pg_amproc` / `pg_opclass` / `pg_opfamily` carry
    orphaned references — initdb may even fail to come up.
  - `catversion.h` not bumped — silent on-disk catalog incompat for
    anyone with a populated data dir.
  - Contrib tests use the removed entry by name and break only
    under `--suite contrib-*`, which `--suite regress` doesn't
    cover (R13 ladder; F12 origin).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_operator.dat` (or `pg_proc.dat` / `pg_aggregate.dat` / `pg_cast.dat` / etc.) | Delete the rows you're removing. Keep nearby `oid =>` comments intact. The actual deletion is the smallest part of the change — the audit below is the load-bearing work. | [pg_operator.dat.md](../files/src/include/catalog/pg_operator.dat.md) | catalog-conventions |
| 2 | `src/include/catalog/pg_proc.dat` — backfill orphaned `descr =>` | **REQUIRED audit when removing operator / aggregate / cast rows.** PG's catalog convention puts the human description on the operator row's `descr =>` field; the operator→proc pointer carries it across, and `opr_sanity`'s "functions with descriptions" check counts on the proc inheriting one. Removing the operator orphans the underlying proc w.r.t. descriptions. Fix: backfill `descr => '...'` directly on each affected proc row in `pg_proc.dat`. Origin: sesvars F6 retro — Phase 0 dropped 6 `@` operators and immediately failed `opr_sanity`; resolution was to add `descr => 'absolute value'` to the 6 `*abs` proc rows in `pg_proc.dat`. | [pg_proc.dat.md](../files/src/include/catalog/pg_proc.dat.md) | catalog-conventions |
| 3 | `src/test/regress/sql/opr_sanity.sql` + `expected/opr_sanity.out` | The sanity tests enumerate catalog contents by name and structure. Removing rows shifts the output of "operators with no commutator" / "functions with descriptions" / "operators whose negators are also operators" queries. Re-record expected output after the catalog change lands. The test suite is in `src/test/regress`; doesn't auto-regenerate. | — | testing |
| 4 | `src/test/regress/sql/type_sanity.sql` + `expected/type_sanity.out` | Same shape as `opr_sanity` but for `pg_type` and related. Run + diff after the change. Removing operators that participate in type I/O paths is the case to watch. | — | testing |
| 5 | `src/include/catalog/pg_amop.dat`, `pg_amproc.dat`, `pg_opclass.dat`, `pg_opfamily.dat` | **REQUIRED audit for orphaned references.** If the removed operator participated in any operator class (btree comparison, hash, gist strategy, etc.), there's a row in one of these `.dat` files that points at it by `oid` or by `amopopr =>`. initdb will fail loudly if these dangle. Grep each file for the removed `oid =>` value. | — | catalog-conventions |
| 6 | `src/include/catalog/catversion.h` | **REQUIRED — always bump on any catalog `.dat` change.** Catalog removals invalidate existing data directories; the catversion bump is the user-visible "you must initdb" signal [from-comment](source/src/include/catalog/catversion.h:26-38). Composite trigger: see also `scenarios/bump-catversion.md`. | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| 7 | `contrib/*/sql/` and `contrib/*/expected/` (e.g. `pg_stat_statements/sql/squashing.sql`) | **REQUIRED grep step + sync trap.** Grep every `contrib/*/sql/` file for the removed entry by name (operator symbol, function name, type name). Contrib modules often exercise built-in operators by name to test code paths (e.g. `pg_stat_statements/sql/squashing.sql` used `@ '-1'::int4` to exercise the "no constants squashing for OpExpr" guarantee). Removing the entry breaks the contrib test silently under `--suite regress` because contrib has its own suite. Origin: sesvars F12 — the R12 end-gate caught `pg_stat_statements/regress` failing because the removed `@` unary made `@ '-N'` unparseable; fix was to switch the test to `~ '-N'::int4`. Sync-trap shape: see also R13 in `pg-implement-discipline.md` (catalog phases MUST include `--suite contrib-*` in the phase-end check). | — | testing |
| 8 | `src/test/regress/sql/<group>.sql` + `expected/<group>.out` | Same shape as row 7 but for the in-tree regress suite. The 6 sesvars `@` unary removals broke `float4.sql`, `float8.sql`, and `numeric.sql` because they exercised `@ -1.5` syntax directly. Grep `src/test/regress/sql/*.sql` for the removed entry and either rewrite the test to use a different operator or remove the line. | — | testing |
| 9 | `doc/src/sgml/func.sgml` (and siblings) | If the removed entry was documented in the functions/operators reference, edit the SGML to drop the row. The doc build won't fail on a missing entry (no script enforces docs↔catalog alignment) — the user will just see a stale doc entry pointing at a non-existent operator. Easy to miss. | — | — |
| 10 | `src/backend/utils/adt/<name>.c` (the underlying C function) | If the removed operator was the SOLE caller of an underlying C function (e.g. `int8abs`, `float4abs`), decide: keep the C function (it may be called from other places, or you may want to keep it for symmetry) OR remove it. In the sesvars Phase 0 case, the `*abs` C functions were KEPT — only the operator wrapper was dropped, so `abs(x)` (the SQL function form) still works. Document the decision in the commit message. | — | — |

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Audit (no edits).** Run the greps:
   ```bash
   grep -n 'oid => ''<OID>''' source/src/include/catalog/*.dat
   grep -n '<op-symbol>' source/src/test/regress/sql/*.sql
   grep -rn '<op-symbol>' source/contrib/*/sql/
   ```
   Document findings in the plan's §3 table. No code changes yet —
   this is the pre-flight that prevents Phase 2 from regressing
   silently.

2. **Phase 2 — Catalog removal + descr backfill + catversion bump.**
   Files: [1, 2, 6]. Drop the catalog rows, backfill `descr =>` on
   orphaned procs, bump `catversion.h`. Phase-end check:
   `meson compile -C dev/build-debug` succeeds, `initdb` runs clean
   on a fresh data dir.

3. **Phase 3 — Sanity + regress test fixup.** Files: [3, 4, 8].
   Run the regress suite, regenerate expected output for
   `opr_sanity`, `type_sanity`, and any in-tree test that used the
   removed entry. Phase-end check:
   `meson test -C dev/build-debug --suite regress` is green.

4. **Phase 4 — Contrib fixup.** Files: [7]. Edit any contrib
   `sql/` file that exercised the removed entry; regenerate
   expected. Phase-end check:
   `meson test -C dev/build-debug --suite regress
   --suite contrib-pg_stat_statements --suite contrib-…` is green.
   **This phase is INVISIBLE to `--suite regress` alone (R13).**

5. **Phase 5 — Docs sweep.** Files: [9]. Edit `func.sgml` and
   siblings if the removed entry was user-documented.
   Phase-end check: `meson test --suite docs` is green.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **`opr_sanity` "functions with descriptions" check.** The most
  surprising failure mode: removing the operator orphans the proc
  description because `descr =>` lived on the operator row and
  flowed across via the operator→proc pointer. Fix in `pg_proc.dat`
  by adding `descr => '...'` directly to each affected proc row.
  Origin: sesvars F6.
- **`pg_amop` / `pg_amproc` references.** If the operator
  participates in any opclass (btree comparison, hash, gist
  strategy), the opclass `.dat` row points at the operator by `oid`.
  initdb will fail loudly. Grep all `pg_am*.dat` and `pg_op*.dat`
  for the removed `oid` BEFORE the removal commit.
- **Contrib tests silently break.** Per-phase
  `--suite regress` covers `src/test/regress` ONLY. Contrib tests
  (`pg_stat_statements`, `btree_gin`, `intarray`, …) live in
  separate meson suites and fall out of the per-phase gate. R13 in
  `pg-implement-discipline.md` codifies this: catalog phases MUST
  run `--suite regress` PLUS `--suite contrib-*` in the phase-end
  check. Origin: sesvars F12 — `pg_stat_statements/squashing.sql`
  used the removed `@ '-N'` unary and only failed at the R12
  end-gate.
- **`catversion.h` not bumped.** Every catalog `.dat` change
  invalidates existing data directories. Forgetting the bump means
  users with old data dirs get silent inconsistencies. Always bump
  in the same commit as the catalog edit
  [from-comment](source/src/include/catalog/catversion.h:26-38).
- **Docs drift.** No script enforces `func.sgml` ↔ catalog
  alignment. The doc build keeps passing with a stale entry. Grep
  `doc/src/sgml/*.sgml` for the removed operator/function name.

- **Synchronization traps** (sibling files that must change together):
  - Catalog `.dat` row removal ↔ `pg_proc.dat` `descr =>` backfill
    (when removing operators/aggregates/casts) ↔ `catversion.h`
    bump. All three in the same commit.
  - `opr_sanity.sql` ↔ `expected/opr_sanity.out` — must be
    regenerated together; the test harness diffs them.
  - In-tree regress (`float4.sql`, `float8.sql`, `numeric.sql`,
    `opr_sanity.sql`, etc.) ↔ contrib tests
    (`pg_stat_statements/sql/squashing.sql`, etc.). Both must be
    audited; the contrib half is invisible to `--suite regress`.

## Verification (exact test invocations)

```bash
# Full build — picks up the catalog regen and catversion bump
meson compile -C dev/build-debug

# Fresh initdb to confirm catversion bump landed cleanly
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug

# Regress + sanity tests
meson test -C dev/build-debug --suite regress

# Contrib suites — REQUIRED for catalog removals (R13)
meson test -C dev/build-debug --suite regress --suite contrib-pg_stat_statements
meson test -C dev/build-debug                # all suites, the R12 backstop

# Docs sweep
meson test -C dev/build-debug --suite docs

# Grep-based confirmation
grep -rn '<removed-symbol>' source/src/test/regress/sql/ source/contrib/*/sql/
# Expect: empty (or only intentionally-rewritten references).
```

## Cross-refs

- Companion skills: `.claude/skills/parser-and-nodes/SKILL.md`,
  `.claude/skills/catalog-conventions/SKILL.md`.
- Related scenarios: `scenarios/add-new-sql-keyword.md` (row 18 of
  that scenario forwards here when a new lexer token forces a
  catalog removal as part of reserving the sigil),
  `scenarios/bump-catversion.md` (this scenario forces a bump),
  `scenarios/add-new-operator.md` (the inverse direction),
  `scenarios/add-new-cast.md`,
  `scenarios/add-new-builtin-function.md`.
- Idioms: `knowledge/idioms/catalog-conventions.md`.
- Subsystems: `knowledge/subsystems/catalog.md`.
- Issues: `knowledge/issues/catalog.md`.
- Origin retro: `sessions/2026-06-16-sesvars-calibration-findings.md`
  F6 (proc-descr orphan) + F12 (contrib silently breaks).
- Discipline rule: `pg-implement-discipline.md` R13 (phase-end check
  scope ladder — catalog phases MUST include `--suite contrib-*`).
