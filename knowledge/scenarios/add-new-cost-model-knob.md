---
scenario: add-new-cost-model-knob
when_to_use: I want to add a new planner cost constant (Cost or non-Cost factor) used by `cost_*` functions, with a matching user-tunable GUC if the value should be reachable from SQL.
companion_skills: ["executor-and-planner", "gucs-config"]
related_scenarios: ["add-new-plan-node", "add-new-guc"]
canonical_commit: 0bd7af082ac
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new cost-model constant (and optional GUC)

## Scope — what's in / out

**In scope:**
- One new `DEFAULT_<NAME>_COST` (or `DEFAULT_<NAME>_FACTOR`) macro in
  `src/include/optimizer/cost.h`.
- Backing `double` global defined in
  `src/backend/optimizer/path/costsize.c`, initialised from the macro.
- Matching `extern PGDLLIMPORT double` declaration in
  `src/include/optimizer/optimizer.h` (where the *cost variables*
  actually live — `cost.h` only holds the macros and the `enable_*`
  flags) [verified-by-code](source/src/include/optimizer/optimizer.h:73-80).
- Use sites in `cost_seqscan` / `cost_index` / `cost_bitmap_heap_scan`
  / `cost_sort` / equivalent.
- Optional but typical: a `PGC_USERSET` real-typed GUC in
  `guc_parameters.dat` + a commented entry in `postgresql.conf.sample`
  + `<varlistentry>` in `doc/src/sgml/config.sgml` under
  "Planner Cost Constants".
- Optional: per-tablespace override via `reloptions.c` + `spccache.c`
  (only for I/O-style costs; cf. `seq_page_cost` / `random_page_cost`).

**Out of scope:**
- Adding a brand-new `enable_<feature>` boolean toggle — that's just a
  GUC; use `add-new-guc`.
- Adding a new `Path`/`Plan`/`PlanState` triple — that's
  `add-new-plan-node`. A cost knob may *support* such a node but doesn't
  build one.
- Changing an existing default (`DEFAULT_SEQ_PAGE_COST` etc.). That's
  not a code-shape change; it's a project-wide regression risk and
  requires `pgbench` / TPC-H validation, not this playbook.
- JIT cost thresholds (`jit_above_cost`, `jit_optimize_above_cost`):
  same shape but live in `src/backend/jit/jit.c`; not covered here.

## Pre-flight

- **Companion skills:** load `executor-and-planner` (where the cost
  functions live, what `startup_cost` vs `total_cost` mean, how
  `Path`s get costed) and `gucs-config` (`guc_parameters.dat` row
  shape, `boot_val`, `min` / `max`, `GUC_EXPLAIN` flag, sample-config
  update rule).
- **Canonical commit:** `0bd7af082ac` — *Invent recursive_worktable_factor
  GUC to replace hard-wired constant.* (Tom Lane, 2022-03-24). Six
  files changed: `cost.h` (macro + 1 line), `optimizer.h` (extern),
  `costsize.c` (define + replace literal), `guc.c` (GUC entry — today
  this lives in `guc_parameters.dat`), `postgresql.conf.sample`,
  `config.sgml`. This is the minimal-shape patch; read it first.
- **Common pitfalls (one-line each):**
  - Forgot the `extern` in `optimizer.h` — link errors from every
    `cost_*` translation unit.
  - Declared in `cost.h` instead of `optimizer.h` — the convention
    [verified-by-code](source/src/include/optimizer/cost.h:21-22) is
    "cost-estimation code uses the *variables*, not the constants" and
    the variables are externed from `optimizer.h`.
  - Forgot to update `postgresql.conf.sample` — every GUC change
    requires it, enforced by the [from-comment](source/src/include/optimizer/cost.h:21-23)
    "If you change these, update backend/utils/misc/postgresql.conf.sample".
  - Changed an existing default — broke every regression test that
    EXPLAIN's a plan. Don't.
  - New cost causes plan churn in regress tests — `select.out`,
    `join.out`, `partition_join.out`, `memoize.out` will all need
    expected-output deltas if the cost moves a real plan decision.
  - `boot_val` mismatched with the macro literal — startup looks fine
    until someone `RESET`s and gets a different number than `initdb`
    bootstrapped with.

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/optimizer/cost.h` | Add `#define DEFAULT_<NAME>_COST <value>` next to the other defaults [verified-by-code](source/src/include/optimizer/cost.h:24-30). Keep the comment block "If you change these, update backend/utils/misc/postgresql.conf.sample" applicable [from-comment](source/src/include/optimizer/cost.h:21-23). Note: the *extern* goes in `optimizer.h`, not here — `cost.h` only carries macros + `enable_*` flags + prototypes. | [cost.h.md](../files/src/include/optimizer/cost.h.md) | executor-and-planner |
| 2 | `src/include/optimizer/optimizer.h` | Add `extern PGDLLIMPORT double <name>_cost;` in the cost-variables block (lines 73-80) [verified-by-code](source/src/include/optimizer/optimizer.h:73-80). This is where every consumer outside `costsize.c` picks up the variable. `PGDLLIMPORT` is mandatory or Windows builds fail. | [optimizer.h.md](../files/src/include/optimizer/optimizer.h.md) | executor-and-planner |
| 3 | `src/backend/optimizer/path/costsize.c` | (a) Define `double <name>_cost = DEFAULT_<NAME>_COST;` in the variables block near `seq_page_cost` [verified-by-code](source/src/backend/optimizer/path/costsize.c:131-138). (b) Reference it in the relevant `cost_<thing>()` function(s) — usually `cost_seqscan` (lines 270+), `cost_index` (545+), `cost_bitmap_heap_scan` (1012+), `cost_tidscan` (1251+), `cost_sort` (2201+) [verified-by-code](source/src/backend/optimizer/path/costsize.c:263-2520). Update the doc-comment header at the top of the file that enumerates the cost units [from-comment](source/src/backend/optimizer/path/costsize.c:9-32). | [costsize.c.md](../files/src/backend/optimizer/path/costsize.c.md) | executor-and-planner |
| 4 | `src/backend/utils/misc/guc_parameters.dat` | (Only if user-tunable.) Add a Perl-hash row `{ name => '<name>_cost', type => 'real', context => 'PGC_USERSET', group => 'QUERY_TUNING_COST', short_desc => '…', flags => 'GUC_EXPLAIN', variable => '<name>_cost', boot_val => 'DEFAULT_<NAME>_COST', min => '0', max => 'DBL_MAX' }`. Place alphabetically; `seq_page_cost`'s entry at lines 2632-2640 is the template [verified-by-code](source/src/backend/utils/misc/guc_parameters.dat:2632-2640). `GUC_EXPLAIN` is needed so EXPLAIN's "Settings" line picks up changes [from-comment](source/src/include/utils/guc.h). The `c-headers` extra Perl pass turns this into the C struct at build time. | — | gucs-config |
| 5 | `src/backend/utils/misc/postgresql.conf.sample` | (Only if user-tunable.) Add a commented line under "Planner Cost Constants" (lines 454-460 [verified-by-code](source/src/backend/utils/misc/postgresql.conf.sample:454-460)): `#<name>_cost = <default>                # same scale as above`. Position matters — the sample file is sectioned and `check-postgres-conf-sample` regression compares the GUC table against this file. | — | gucs-config |
| 6 | `doc/src/sgml/config.sgml` | (Only if user-tunable.) Add a `<varlistentry id="guc-<name>-cost" xreflabel="<name>_cost">` block to the "Planner Cost Constants" section near line 6300 [verified-by-code](source/doc/src/sgml/config.sgml:6300-6360). Include `<primary>` indexterm, default, scale explanation, and any cross-refs to `seq_page_cost`. SGML validity is checked by `meson test --suite docs`. | — | — |
| 7 | `src/backend/access/common/reloptions.c` | (Only if per-tablespace override desired.) Add to the `RELOPT_KIND_TABLESPACE` validated list around line 471-480 and the `tab_opts[]` array around line 2234 [verified-by-code](source/src/backend/access/common/reloptions.c:471-480). Also extend `struct TableSpaceOpts` in `src/include/commands/tablespace.h:41-48` with a matching `float8` field [verified-by-code](source/src/include/commands/tablespace.h:41-48). | [reloptions.c.md](../files/src/backend/access/common/reloptions.c.md) | — |
| 8 | `src/backend/utils/cache/spccache.c` | (Only if per-tablespace override desired.) Extend `get_tablespace_page_costs()` (lines 184-205) [verified-by-code](source/src/backend/utils/cache/spccache.c:184-205) to return your knob, falling back to the global when `spc->opts` is NULL or the option is negative. Add a new accessor or new out-parameter — match the existing two-parameter pattern. Update declaration in `src/include/utils/spccache.h:16` [verified-by-code](source/src/include/utils/spccache.h:16). | [spccache.c.md](../files/src/backend/utils/cache/spccache.c.md) | — |
| 9 | `src/test/regress/sql/guc.sql` + matching `.out` | (Only if user-tunable.) Add a `SHOW <name>_cost;` plus a `SET <name>_cost TO …; RESET <name>_cost;` smoke test — pattern at `guc.sql:160` [verified-by-code](source/src/test/regress/sql/guc.sql:160) for `seq_page_cost`. Also check NaN / negative rejection if applicable. | — | testing |
| 10 | `src/test/regress/expected/*.out` (multiple) | Plan-shape EXPLAIN expected-output deltas. New knob with default 0 affects nothing; non-zero default likely shifts costs in `aggregates.out`, `memoize.out`, `partition_join.out`, `join_hash.out`, etc. Identify by running the full regress and inspecting `regression.diffs`. Update only if a real plan changed — never edit expected files to make tests "pass" without understanding why. | — | testing |
| 11 | `src/backend/optimizer/README` | (Optional but recommended for non-trivial knobs.) Add a short paragraph under "Costing" describing what the new variable represents and when it fires. Reference the canonical paper / comment from the discussion thread. | — | executor-and-planner |

(Use `—` in the per-file doc column for files that don't yet have a
per-file doc; otherwise the entry should exist in `knowledge/files/`
and link.)

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Macro + variable + extern, no use sites.** Files: [1, 2, 3a].
   Add the `#define` in `cost.h`, the `extern PGDLLIMPORT double` in
   `optimizer.h`, and the `double <name>_cost = DEFAULT_…;` definition
   in `costsize.c`. The variable is unused at this point. Phase-end
   check: `meson compile -C dev/build-debug` succeeds; the variable
   appears in `nm dev/install-debug/bin/postgres | grep <name>_cost`.

2. **Phase 2 — Wire into cost functions.** Files: [3b, 11].
   Replace the literal / add the multiplication term inside the
   relevant `cost_<thing>()` function(s). Update the file's leading
   comment block listing cost units [from-comment](source/src/backend/optimizer/path/costsize.c:9-32).
   If non-trivial, write a paragraph in `optimizer/README`. Phase-end
   check: `meson compile` clean; `EXPLAIN` on a representative query
   shows a different total cost from baseline (sanity).

3. **Phase 3 — GUC + sample.conf + docs.** Files: [4, 5, 6].
   Add the `guc_parameters.dat` row; mirror in `postgresql.conf.sample`
   with the same default; add a `<varlistentry>` in `config.sgml`.
   Phase-end check:
   `meson test -C dev/build-debug --suite docs` (SGML valid),
   `psql -c "SHOW <name>_cost;"` returns default,
   `psql -c "EXPLAIN (SETTINGS) SELECT …;"` lists it only when non-default.

4. **Phase 4 — Tests + plan-output reconciliation.** Files: [9, 10],
   plus [7, 8] if per-tablespace. Add the `guc.sql` smoke test. Run
   the full regress suite and reconcile any plan diffs:
   `meson test -C dev/build-debug --suite regress`. Each plan diff
   must be *explained* in the commit message — "X moved from
   index-scan to seq-scan because the new knob penalises Y by Z%".

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`cost-join-paths`](../idioms/cost-join-paths.md) | direct reference |
| [`cost-parallel-adjustments`](../idioms/cost-parallel-adjustments.md) | direct reference |
| [`cost-scan-paths`](../idioms/cost-scan-paths.md) | direct reference |
| [`cost-units-gucs`](../idioms/cost-units-gucs.md) | direct reference |
| [`guc-variables`](../idioms/guc-variables.md) | direct reference |
| [`jit-provider-and-context`](../idioms/jit-provider-and-context.md) | shares files: `src/backend/jit/jit.c` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **`extern` in the wrong header.** Putting `extern PGDLLIMPORT double
  <name>_cost;` in `cost.h` instead of `optimizer.h` compiles but
  splits the planner's "cost variables" group; downstream tooling
  (`pg_overexplain`, extension code, `auto_explain`) expects them all
  in one place [verified-by-code](source/src/include/optimizer/optimizer.h:73-80).
- **Missing `PGDLLIMPORT`.** Linux/macOS builds pass; Windows builds
  fail with unresolved external symbol. Always `PGDLLIMPORT` for
  globals exposed to extensions [from-comment](source/src/include/optimizer/cost.h:50).
- **`boot_val` literal vs macro.** Write `boot_val => 'DEFAULT_<NAME>_COST'`
  (the macro name as a string — the GUC generator emits it verbatim
  into the C struct), NOT `boot_val => '<numeric literal>'`. Drift
  between the macro and the GUC default is invisible until someone
  changes one.
- **`GUC_EXPLAIN` forgotten.** EXPLAIN's "Settings" line silently
  omits the knob when changed [from-comment](source/src/include/utils/guc.h).
  Confuses everyone reading explain output.
- **Cost-default change cascades through regress.** Even a tiny shift
  flips index-scan ↔ seq-scan boundaries on small tables in test
  fixtures. Run `meson test … --print-errorlogs` and read every
  EXPLAIN diff individually; never blanket-accept.
- **Forgot per-relation reloption hook.** If the knob is I/O-shaped
  (`seq_page_cost` family) users will expect `ALTER TABLESPACE … SET
  (<name>_cost = …)` to work; without [7, 8] it silently does nothing
  for that knob.
- **No issue register for optimizer-cost yet.** There's no
  `knowledge/issues/optimizer.md`. Surface new traps you hit here so
  the next pass can collect them.

- **Synchronization traps** (sibling files that must change together):
  - `cost.h` macro ↔ `costsize.c` definition (same default).
  - `costsize.c` definition ↔ `optimizer.h` extern (same name, same type).
  - `guc_parameters.dat` `boot_val` ↔ `cost.h` macro (use the macro
    name verbatim).
  - `guc_parameters.dat` row ↔ `postgresql.conf.sample` entry
    (same name, same default, same group).
  - `postgresql.conf.sample` ↔ `config.sgml` `<varlistentry>`
    (same name, same default printed, same section).
  - `reloptions.c` `tab_opts[]` ↔ `TableSpaceOpts` struct field
    ↔ `spccache.c` `get_tablespace_page_costs()` accessor
    (all three or none).

## Verification (exact test invocations)

```bash
# Build — picks up the new GUC into the parameters table
meson compile -C dev/build-debug

# Confirm symbol exists
nm dev/install-debug/bin/postgres | grep <name>_cost

# Smoke test the GUC
dev/install-debug/bin/postgres -D dev/data-debug -k /tmp &
psql -h /tmp -c "SHOW <name>_cost;"
psql -h /tmp -c "SET <name>_cost = 2.0; EXPLAIN (SETTINGS) SELECT 1;"

# Regress (the load-bearing suite — plan diffs surface here)
meson test -C dev/build-debug --suite regress

# Specifically the GUC test if you added a smoke entry
meson test -C dev/build-debug --suite regress --test regress

# Docs (SGML validity for the new <varlistentry>)
meson test -C dev/build-debug --suite docs

# postgresql.conf.sample drift check is part of the regress suite —
# it runs `check_guc` comparing GUC table to the sample file
```

If you add a brand-new test file (rare for a cost knob), name it
explicitly here.

## Cross-refs

- Companion skills: `.claude/skills/executor-and-planner/SKILL.md`,
  `.claude/skills/gucs-config/SKILL.md`.
- Related scenarios: `scenarios/add-new-plan-node.md`,
  `scenarios/add-new-guc.md`.
- Idioms: `knowledge/idioms/cost-units-gucs.md` (the canonical
  rundown of cost units and how they interact),
  `knowledge/idioms/cost-scan-paths.md` (where `cost_seqscan` /
  `cost_index` / `cost_bitmap_heap_scan` plug the knobs in),
  `knowledge/idioms/cost-join-paths.md` (join-side cost integration),
  `knowledge/idioms/cost-parallel-adjustments.md` (interaction with
  `parallel_*_cost`), `knowledge/idioms/guc-variables.md`.
- Subsystems: `knowledge/subsystems/optimizer.md`.
- Issues: no `knowledge/issues/optimizer.md` yet — when one is added,
  cross-link traps surfaced by cost-knob patches.
- Reference patch (canonical_commit): `git -C source show 0bd7af082ac`.
