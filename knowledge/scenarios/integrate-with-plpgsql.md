---
scenario: integrate-with-plpgsql
when_to_use: My new feature (keyword, expression, syntax surface) must work inside PL/pgSQL — DO blocks, functions, procedures — not just in top-level SQL.
companion_skills: ["parser-and-nodes", "executor-and-planner"]
related_scenarios: ["add-new-sql-keyword", "add-new-node-type", "add-new-utility-statement", "add-new-expression-eval-step"]
canonical_commit: e18b0cb7344
last_verified_commit: e18b0cb7344
---

# Scenario — Integrate a new feature with PL/pgSQL

## Scope — what's in / out

**In scope:**
- A feature implemented at the core SQL layer (new keyword, new
  Expr Node, new utility statement, new expression-eval step) that
  must ALSO be reachable from inside PL/pgSQL DO blocks, function
  bodies, and procedure bodies.
- The PL/pgSQL-side touchpoints needed to:
  - Recognize the new token in PL/pgSQL's hand-written scanner
    (`pl_scanner.c`).
  - Parse the new syntax in PL/pgSQL's grammar (`pl_gram.y`),
    especially when PL/pgSQL has its own statement-level production
    that wraps SQL.
  - Execute the new statement / expression through PL/pgSQL's
    executor (`pl_exec.c`).
  - Dispatch through PL/pgSQL's outer handler (`pl_handler.c`) if a
    new entry point is needed.
  - Carry any new PL/pgSQL-side statement / type enums (`plpgsql.h`).
- The regression coverage: PL/pgSQL test SQL exercising the feature
  inside DO blocks, function bodies, savepoints, RAISE expressions,
  GET DIAGNOSTICS, and the parameter-mixing surface.

**Out of scope:**
- The core SQL-layer implementation itself — see
  `scenarios/add-new-sql-keyword.md` (token / kwlist), `add-new-node-type.md`
  (Expr Node), `add-new-utility-statement.md` (Stmt), or
  `add-new-expression-eval-step.md` (EEOP). This scenario is the
  PL/pgSQL composition layer; it ALWAYS unions with at least one of
  those.
- Other PLs (`plperl`, `plpython3u`, `pltcl`) — each has its own
  scenario shape (not yet written; defer until needed).
- ECPG host-language integration — see `add-new-sql-keyword.md` row
  8 (`pgc.l` sync trap).

**Trigger phrase:** "the feature must work inside DO blocks", "
SELECT INTO @var inside a function", "PL/pgSQL direct SET", "GET
DIAGNOSTICS support", "RAISE … USING ...".

## Pre-flight

- **Companion skills:** load `parser-and-nodes` (for the gram.y /
  parse-tree side) and `executor-and-planner` (for the SPI /
  expression-evaluator interaction PL/pgSQL uses to dispatch SQL
  through SPI).
- **Canonical example:** *(no clean upstream single-commit example
  — PL/pgSQL integration is usually woven into the feature's main
  patch series.)* The **sesvars calibration Phase 9** is the
  reference implementation: it added PL/pgSQL direct `SET @x := …`
  (no `EXECUTE format(...)` workaround) and `SELECT col INTO @v`
  support, touching `pl_gram.y`, `pl_scanner.c`, `pl_exec.c`,
  `pl_handler.c`, `plpgsql.h`, and the PL/pgSQL regress suite. The
  Phase 9 commit in `postgresql-dev-feature-sesvars` is the worked
  example.
- **Common pitfalls (one-line each):**
  - `pl_gram.y` `%token <str>` block at lines 247-250 not synced
    with core `gram.y` — Bison-assigned numeric token IDs shift
    silently and PL/pgSQL's integer comparisons in `pl_scanner.c`
    break (sesvars F2 — this is the same trap row 17 of
    `add-new-sql-keyword.md` cites).
  - `pl_scanner.c` is **hand-written** (not Flex-generated) —
    adding a new lexical state or recognizing a new
    character-class prefix means hand-editing the state machine.
  - PL/pgSQL has its own statement-type enum (`PLpgSQL_stmt_type`
    in `plpgsql.h`) and adding a new statement requires a new
    enum tag + new struct + new exec-side dispatch case in
    `pl_exec.c`'s big switch.
  - Forgetting to add the test inside a DO block — feature works
    at top level, breaks the moment a user wraps it in `DO $$ … $$`.

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/pl/plpgsql/src/pl_gram.y` | **Always touched if your feature added a new core gram.y `%token <str>`.** Lines 247-250 carry a sibling `%token <str>` block prefixed with "Keep this list in sync with backend/parser/gram.y!" [from-comment](source/src/pl/plpgsql/src/pl_gram.y:240-241). Failing to sync shifts Bison-assigned numeric token IDs in `gram.h` and breaks PL/pgSQL's integer comparisons in `pl_scanner.c` (F2). Beyond the token-sync row: if PL/pgSQL needs to PARSE the new syntax at its own statement level (vs. just passing it through to the core SQL parser via SPI), add a new `plpgsql_stmt_*` production here. | — | parser-and-nodes |
| 2 | `src/pl/plpgsql/src/pl_scanner.c` | **Hand-written scanner** (not Flex-generated). Edit only if the new feature introduces a token type or character-class prefix that PL/pgSQL's scanner doesn't currently recognize. Look for `internal_yylex()` and `pl_scanner_init()`; PL/pgSQL re-uses core's scan-keywords table but has its own state machine for `<<label>>`, `IF … THEN`, `END IF`, etc. If your feature is a pure expression that PL/pgSQL passes through to the core SQL parser (via SPI), this file usually doesn't need an edit — but the token-ID-shift trap from row 1 still applies. | — | parser-and-nodes |
| 3 | `src/pl/plpgsql/src/pl_exec.c` | **Statement executor.** ~270 KB monster file with the big `switch (stmt->cmd_type)` dispatcher in `exec_stmt()` (plus its tail-call variants `exec_stmts`, `exec_stmt_block`). If your feature adds a new PL/pgSQL statement type, add a new case here and implement it. If your feature is a pure expression, the existing `exec_eval_expr()` path through SPI usually carries it — but expressions that produce side effects (like sesvars assignment `@x := ...`) may need explicit handling to ensure the side effect is committed in PL/pgSQL's expected order vs. transaction boundaries. | — | executor-and-planner |
| 4 | `src/pl/plpgsql/src/pl_handler.c` | **Outer dispatcher** — the entry point `plpgsql_call_handler` / `plpgsql_inline_handler` (DO blocks) / `plpgsql_validator`. Edit only if your feature changes the lifecycle (new GUC needs initialization here, new memory context, new per-function setup). Most features touch this only for a GUC-init line; some don't touch it at all. | — | executor-and-planner |
| 5 | `src/pl/plpgsql/src/plpgsql.h` | **Type and statement enums.** Add a new `PLPGSQL_STMT_*` tag to the `PLpgSQL_stmt_type` enum + a new struct `PLpgSQL_stmt_xxx` for the per-statement payload. The struct's first field MUST be `PLpgSQL_stmt_type cmd_type;` so the dispatcher in `pl_exec.c` can route on it. If your feature adds new datum kinds (PL/pgSQL's variable representation), also add to `PLpgSQL_datum_type`. | — | executor-and-planner |
| 6 | `src/pl/plpgsql/src/pl_comp.c` | Edit only if PL/pgSQL's compile-time analysis needs to recognize the new construct (e.g. variable lookup, type checking, namespace resolution). Pure-expression features that flow through SPI usually don't touch this file. | — | parser-and-nodes |
| 7 | `src/pl/plpgsql/src/pl_funcs.c` | Edit only if you added a new `PLpgSQL_stmt_*` struct that needs a tree-walker case (similar to `nodeFuncs.c` for core Expr Nodes). The walker family here is smaller — `plpgsql_dumptree` for debug output and stmt-type→name mapping. | — | parser-and-nodes |
| 8 | `src/test/regress/sql/plpgsql.sql` + `expected/plpgsql.out` | The PL/pgSQL regress suite. Add test cases exercising the new feature inside: a DO block, a function body, a procedure body (if applicable), a savepoint, RAISE expression interpolation, GET DIAGNOSTICS, and parameter-mixing (function arguments + the new feature in the body). | — | testing |
| 9 | `src/pl/plpgsql/src/expected/plpgsql_*.out` (per-suite expected) | If your feature interacts with PL/pgSQL's per-feature test suites (`plpgsql_call`, `plpgsql_control`, `plpgsql_transaction`, …) regenerate the relevant expected outputs. | — | testing |
| 10 | The feature's own SQL test file | **REQUIRED — composes with R14 own-test-suite rule.** Add explicit DO-block test cases inside your feature's `src/test/regress/sql/<feature>.sql`, not only in `plpgsql.sql`. The reasoning: PL/pgSQL integration is part of the *feature's* surface contract, so the feature owns the coverage, not just the cross-cutting plpgsql suite. Sesvars ships `sessvar_advanced.sql` with DO-block exercises of `SET @x := …`, `SELECT INTO @v`, savepoint rollback, etc. | — | testing |

## Phases — suggested split for `pg-feature-plan`

Always unions with at least one of `add-new-sql-keyword`,
`add-new-node-type`, `add-new-utility-statement`, or
`add-new-expression-eval-step`. The phases below cover the
PL/pgSQL-specific add-on; core-side phases run first.

1. **Phase A — Token sync (do this IMMEDIATELY after the core gram.y
   token-add).** Files: [1]. If your core change added a new
   `%token <str>` in `backend/parser/gram.y`, add the same token to
   `src/pl/plpgsql/src/pl_gram.y:247-250`. This is the F2 trap;
   skipping it shifts Bison-assigned token IDs and silently breaks
   PL/pgSQL parsing of `:=`, `1..N`, etc. Phase-end check: full
   regress (`meson test --suite regress`) — the trap surfaces as
   ~30+ unrelated PL/pgSQL test failures, so the full suite is
   load-bearing here, not just `plpgsql`.

2. **Phase B — Statement type + struct (only if adding a PL/pgSQL
   statement).** Files: [5, 6 if compile-time]. Add the new
   `PLPGSQL_STMT_*` enum tag and matching struct in `plpgsql.h`.
   Wire compile-time recognition in `pl_comp.c` if needed.
   Phase-end check: `meson compile` succeeds.

3. **Phase C — Grammar production + executor dispatch.** Files:
   [1, 3]. Add the new `plpgsql_stmt_*` production to `pl_gram.y`.
   Add the executor case in `pl_exec.c`'s `exec_stmt()` switch.
   Phase-end check: targeted smoke test (DO block exercising the
   new statement) plus full PL/pgSQL regress.

4. **Phase D — Handler / scanner edits (rare).** Files: [2, 4].
   Edit `pl_scanner.c` if a new lexical state is needed. Edit
   `pl_handler.c` if the lifecycle changes. Phase-end check: full
   regress.

5. **Phase E — Tests.** Files: [8, 9, 10]. Add tests in `plpgsql.sql`,
   any affected per-feature plpgsql suites, AND the feature's own
   `<feature>.sql` with DO-block coverage (R14). Phase-end check:
   full regress green, including `--suite regress` and the
   feature-specific tests.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`tom-lane`](../personas/tom-lane.md) | `src/pl`, `src/test/regress` |
| [`david-rowley`](../personas/david-rowley.md) | `src/test/regress` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/test/regress` |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/test/regress` |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/pl` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`error-context-callbacks`](../idioms/error-context-callbacks.md) | shares files: `src/pl/plpgsql/src/pl_exec.c` |
| [`spi`](../idioms/spi.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **F2 — pl_gram.y token-block desync.** This is the single most
  important trap in this scenario. Any new `%token <str>` in core
  gram.y MUST also land in `pl_gram.y:247-250`. The comment in the
  source says it explicitly. Not enforced by any script — the
  symptom is silent: PL/pgSQL's `pl_scanner.c` does integer
  comparisons against `gram.h`-assigned IDs (e.g.
  `if (tok == COLON_EQUALS)`), and the IDs shift on every new
  token. ~30 unrelated PL/pgSQL test failures cluster on this trap
  when missed (origin: sesvars F2 retro).
- **PL/pgSQL has its own statement-type enum.** Unlike core, where
  Node types are auto-discovered by `gen_node_support.pl`,
  PL/pgSQL's `PLpgSQL_stmt_type` enum is hand-maintained. Adding a
  new statement = enum tag + struct + dispatcher case + walker
  case (in `pl_funcs.c` if you want debug-dump coverage).
- **Expression side effects vs. PL/pgSQL's transaction boundaries.**
  If your feature is a *side-effecting* expression (assignment,
  `nextval()`-shaped), think carefully about how the side effect
  composes with PL/pgSQL's savepoint and rollback semantics. Sesvars
  Phase 9 hit this with `@x := ...` inside savepoint blocks —
  ROLLBACK to savepoint had to undo session-variable writes too.
  Tests in `<feature>.sql` should cover this explicitly.
- **DO blocks vs. function bodies vs. procedures.** Three subtly
  different parse paths. A feature can work in one and break in
  another. Always exercise all three in the test file.
- **GET DIAGNOSTICS / RAISE USING.** If your feature produces a
  value that users will want to inspect (an error code, an OID, a
  count), think about whether `GET DIAGNOSTICS` should be able to
  reach it and whether `RAISE … USING` should be able to interpolate
  it. Often a no-op for your feature, but worth deciding explicitly.

- **Synchronization traps** (sibling files that must change together):
  - **Core `gram.y` `%token <str>` block ↔
    `src/pl/plpgsql/src/pl_gram.y:247-250` `%token <str>` block.**
    The PRIMARY trap (F2). Same comment shows in
    `add-new-sql-keyword.md` row 17.
  - `plpgsql.h` `PLpgSQL_stmt_type` enum tag ↔ `pl_exec.c` dispatcher
    case ↔ `pl_gram.y` production ↔ `pl_funcs.c` walker case (if
    debug-dump matters).
  - Feature's own `<feature>.sql` ↔ `plpgsql.sql` — coverage in
    both, not just the cross-cutting one (R14).

## Verification (exact test invocations)

```bash
# Full build
meson compile -C dev/build-debug

# Full regress — the F2 trap surfaces as wide PL/pgSQL failures,
# so this is the load-bearing check, not just the plpgsql test
meson test -C dev/build-debug --suite regress

# Targeted PL/pgSQL test
meson test -C dev/build-debug --suite regress --test plpgsql

# Per-feature PL/pgSQL suites (if your feature touches them)
meson test -C dev/build-debug --suite regress --test plpgsql_call
meson test -C dev/build-debug --suite regress --test plpgsql_control
meson test -C dev/build-debug --suite regress --test plpgsql_transaction

# Smoke-test DO block
dev/install-debug/bin/psql -c "DO \$\$ BEGIN <your-feature>; END \$\$;"

# Smoke-test in a function body
dev/install-debug/bin/psql <<EOF
CREATE OR REPLACE FUNCTION t() RETURNS void AS \$\$
BEGIN
  <your-feature>;
END;
\$\$ LANGUAGE plpgsql;
SELECT t();
EOF
```

## Cross-refs

- Companion skills: `.claude/skills/parser-and-nodes/SKILL.md`,
  `.claude/skills/executor-and-planner/SKILL.md`.
- Related scenarios:
  `scenarios/add-new-sql-keyword.md` (row 17 cites the same F2
  trap; this scenario expands the broader PL/pgSQL surface),
  `scenarios/add-new-node-type.md`,
  `scenarios/add-new-utility-statement.md`,
  `scenarios/add-new-expression-eval-step.md`.
- Idioms: `knowledge/idioms/spi.md` (PL/pgSQL routes most SQL
  through SPI; understanding SPI is the prereq for editing
  `pl_exec.c`).
- Subsystems: `knowledge/subsystems/plpgsql.md`,
  `knowledge/subsystems/parser-and-rewrite.md`.
- Issues: `knowledge/issues/plpgsql.md`.
- Origin retro: `sessions/2026-06-16-sesvars-calibration-findings.md`
  F2 (token-ID shift) and the post-MVP Phase 9 work that added
  direct `SET @x := …` / `SELECT INTO @v` PL/pgSQL support.
