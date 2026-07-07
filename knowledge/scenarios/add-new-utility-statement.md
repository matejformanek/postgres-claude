---
scenario: add-new-utility-statement
when_to_use: I want to add a new top-level utility statement (a CREATE / DROP / ALTER / verb-style command) that the parser produces as `XxxStmt` and the backend dispatches via `standard_ProcessUtility`.
companion_skills: ["parser-and-nodes"]
related_scenarios: ["add-new-sql-keyword", "add-new-node-type"]
canonical_commit: 447aae13b03
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new utility statement

## Scope — what's in / out

**In scope:**
- A brand-new top-level utility command: parser produces a new
  `XxxStmt` Node, `standard_ProcessUtility` gains a `case T_XxxStmt`,
  the impl lives in a new (or existing) `src/backend/commands/<name>.c`.
- The full dispatch sweep: `ClassifyUtilityCommandAsReadOnly`, the
  main switch, `CreateCommandTag`, `GetCommandLogLevel`, plus
  `UtilityReturnsTuples` / `UtilityTupleDescriptor` if the statement
  returns rows. `[verified-by-code]`
  (`src/backend/tcop/utility.c:130-130`, `597-597`, `2385-2385`,
  `3290-3290`, `2042-2042`, `2101-2101`).
- A new `CMDTAG_<NAME>` row in `src/include/tcop/cmdtaglist.h`. The
  command tag is what shows up as the `Q` row's `tag` and what
  drivers see in `PQcmdStatus()`. `[verified-by-code]`
  (`src/include/tcop/cmdtaglist.h:1-30`).
- New SGML reference page at `doc/src/sgml/ref/<name>.sgml`, wired
  via `doc/src/sgml/ref/allfiles.sgml` + `doc/src/sgml/reference.sgml`.
- tab-completion support in `src/bin/psql/tab-complete.in.c`.
- Regression / TAP test that exercises the new statement.

**Out of scope:**
- Adding a *new keyword* the statement uses — that's
  `scenarios/add-new-sql-keyword.md`. Most new utility statements
  also need a new keyword, so the planner will union the two
  checklists. `[inferred]`
- Introducing a brand-new Node *kind* outside the parsenodes
  family (e.g. a new Plan node) — `scenarios/add-new-node-type.md`.
  `XxxStmt` itself is a parsenode and only requires editing
  `parsenodes.h` + regenerating the node support files, not a
  separate scenario.
- Extending an existing statement with a new sub-clause (e.g. a new
  `VACUUM` option) — one-line edits to the existing `case`, not a
  full new dispatch site.

## Pre-flight

- **Companion skills:** load `parser-and-nodes` — it covers
  `gram.y` productions, `makeNode()` / `nodeTag()`, and the
  `gen_node_support.pl` regeneration step that picks up the new
  Node from `parsenodes.h`.
  `[verified-by-code]`
  (`.claude/skills/parser-and-nodes/SKILL.md`).
- **Canonical commit:** `447aae13b03` — *"Implement WAIT FOR
  command"* (Alexander Korotkov, 2025-11-05). A clean 21-file
  textbook utility-statement patch: new `WaitStmt`, new `WAIT FOR
  LSN` grammar production with a new `WAIT` keyword, new
  `src/backend/commands/wait.c`, the full dispatch sweep in
  `utility.c` (including tuple-returning helpers), new
  `CMDTAG_WAIT_FOR`, new `wait_for.sgml`, tab-complete entry, and a
  TAP test. Read it before starting — it shows the shape end-to-end,
  including the tuple-returning variant which is the more
  interesting case. `[verified-by-code]`
  (`git -C source show 447aae13b03`).
- **Common pitfalls (one-line each):**
  - Forgetting one of the four `nodeTag()` switches in `utility.c`
    (read-only classify, main dispatch, command tag, log level) —
    the missing site silently falls through to `elog(ERROR,
    "unrecognized node type")` or to a wrong tag. `[verified-by-code]`
    (`src/backend/tcop/utility.c:130, 597, 2385, 3290`).
  - Tuple-returning utility but no `UtilityReturnsTuples` /
    `UtilityTupleDescriptor` entry — `pquery.c` won't initialise a
    receiver, the rows go nowhere. `[verified-by-code]`
    (`src/backend/tcop/utility.c:2042-2150`).
  - Missing `event-trigger.sgml` update when the new statement
    routes through `ProcessUtilitySlow` — see banner comment at
    `utility.c:534-545`: *"When adding or moving utility commands,
    check that the documentation in event-trigger.sgml is kept up
    to date."* `[from-comment]`
    (`src/backend/tcop/utility.c:534-545`).
  - Forgetting `ProcessUtility_hook` semantics — extensions
    intercept *before* `standard_ProcessUtility`. If your statement
    has security checks that an extension must not be able to
    bypass, document the hook order explicitly. `[from-comment]`
    (`src/backend/tcop/utility.c:518-530`).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/nodes/parsenodes.h` | Add `typedef struct XxxStmt { NodeTag type; ... } XxxStmt;` near the other utility-stmt typedefs (~4500-4600 for new entries). Triggers `T_XxxStmt` enum addition + `gen_node_support.pl` regen of copy/equal/out/read. `[verified-by-code]` (`src/include/nodes/parsenodes.h:4596-4601` for `WaitStmt`). | [parsenodes.h.md](../files/src/include/nodes/parsenodes.h.md) | parser-and-nodes |
| 2 | `src/backend/parser/gram.y` | Add the production rule (`XxxStmt: KEYWORD ... { ... }`), the typed non-terminal declaration (`%type <node> XxxStmt`), and a `| XxxStmt` line in the `stmt:` rule. `[verified-by-code]` (`src/backend/parser/gram.y:314, 1167, 17265-17266` for `WaitStmt`). | [gram.y.md](../files/src/backend/parser/gram.y.md) | parser-and-nodes |
| 3 | `src/include/parser/kwlist.h` | If the statement needs a new keyword (typical) add the `PG_KEYWORD(...)` row. The reserved-ness category (UNRESERVED / TYPE_FUNC_NAME / COL_NAME / RESERVED) determines whether the word can still be used as an identifier. `[verified-by-code]` (`src/include/parser/kwlist.h` — see `add-new-sql-keyword.md` for the full keyword sweep). | — | parser-and-nodes |
| 4 | `src/backend/commands/<name>.c` | (NEW) The actual implementation. Contains the `Exec<Xxx>Stmt(ParseState *pstate, XxxStmt *stmt, bool isTopLevel, ...)` entry point that the dispatch switch calls. Permission checks, locking, work happens here. `[verified-by-code]` (`src/backend/commands/wait.c:34` for `ExecWaitStmt`). | — | parser-and-nodes |
| 5 | `src/include/commands/<name>.h` | (NEW) Public declaration of `Exec<Xxx>Stmt()` (and any tuple-desc helper). Included by `utility.c`. `[verified-by-code]` (`src/include/commands/wait.h:19-21`). | — | parser-and-nodes |
| 6 | `src/backend/commands/Makefile` | Add `<name>.o` to the `OBJS` list — alphabetically sorted. `[verified-by-code]` (git show 447aae13b03 `src/backend/commands/Makefile`). | — | parser-and-nodes |
| 7 | `src/backend/commands/meson.build` | Add `'<name>.c'` to the `backend_sources` list. Build will silently skip the new file otherwise. `[verified-by-code]` (git show 447aae13b03 `src/backend/commands/meson.build`). | — | parser-and-nodes |
| 8 | `src/backend/tcop/utility.c` (`ClassifyUtilityCommandAsReadOnly`) | Add `case T_XxxStmt:` to one of the existing read-only-classification groups (strictly RO / RO-in-RO-txn / writes-WAL). Decides whether the command is rejected in a read-only transaction, in parallel mode, or during recovery. `[verified-by-code]` (`src/backend/tcop/utility.c:130-300`). | [utility.c.md](../files/src/backend/tcop/utility.c.md) | parser-and-nodes |
| 9 | `src/backend/tcop/utility.c` (main switch in `standard_ProcessUtility`) | Add `case T_XxxStmt: Exec<Xxx>Stmt(...); break;`. Decide whether to go through `ProcessUtilitySlow` (needed iff event-trigger support or `pg_event_trigger_ddl_commands()` visibility is required). `[verified-by-code]` (`src/backend/tcop/utility.c:597, 950-1075`). | [utility.c.md](../files/src/backend/tcop/utility.c.md) | parser-and-nodes |
| 10 | `src/backend/tcop/utility.c` (`CreateCommandTag`) | Add `case T_XxxStmt: tag = CMDTAG_<NAME>; break;`. Without this, the command tag returned to the client is `CMDTAG_UNKNOWN`. `[verified-by-code]` (`src/backend/tcop/utility.c:2385, 3032`). | [utility.c.md](../files/src/backend/tcop/utility.c.md) | parser-and-nodes |
| 11 | `src/backend/tcop/utility.c` (`GetCommandLogLevel`) | Add `case T_XxxStmt: lev = LOGSTMT_<DDL\|MOD\|ALL>; break;`. Drives whether `log_statement = ddl` etc. logs this command. `[verified-by-code]` (`src/backend/tcop/utility.c:3290, 3657`). | [utility.c.md](../files/src/backend/tcop/utility.c.md) | parser-and-nodes |
| 12 | `src/backend/tcop/utility.c` (`UtilityReturnsTuples` + `UtilityTupleDescriptor`) — *only if* the statement returns rows | Add `case T_XxxStmt: return true;` to `UtilityReturnsTuples` and `case T_XxxStmt: return Xxx<Stmt>ResultDesc(...);` to `UtilityTupleDescriptor`. Otherwise `pquery.c` skips receiver setup. `[verified-by-code]` (`src/backend/tcop/utility.c:2042-2150`, `src/backend/tcop/pquery.c:1744` for the `IsA(utilityStmt, WaitStmt)` snowflake). | [utility.c.md](../files/src/backend/tcop/utility.c.md), [pquery.c.md](../files/src/backend/tcop/pquery.c.md) | parser-and-nodes |
| 13 | `src/include/tcop/cmdtaglist.h` | Add `PG_CMDTAG(CMDTAG_<NAME>, "<NAME>", <event_trigger_ok>, <table_rewrite_ok>, <returns_oid>)`. Keep the list alphabetically grouped. `[verified-by-code]` (`src/include/tcop/cmdtaglist.h:61, 76, 223` — sample existing entries). | — | parser-and-nodes |
| 14 | `src/tools/pgindent/typedefs.list` | Add `XxxStmt` so `pgindent` formats the type-name correctly. Patch will fail review otherwise. `[verified-by-code]` (`src/tools/pgindent/typedefs.list:3431` for `WaitStmt`). | — | coding-style |
| 15 | `src/bin/psql/tab-complete.in.c` | Add the keyword(s) to the top-level command-list array (around line 1279 for the alphabetical `R-W` row) and add a `Matches("<KEYWORD>", ...)` branch with sub-option completion. `[verified-by-code]` (`src/bin/psql/tab-complete.in.c:1283, 5549` for `WAIT FOR`). | [tab-complete.in.c.md](../files/src/bin/psql/tab-complete.in.c.md) | psql |
| 16 | `doc/src/sgml/ref/<name>.sgml` | (NEW) Per-statement reference page. Use a sibling page (e.g. `wait_for.sgml`, `checkpoint.sgml`) as a starting template; required sections are `<refsynopsisdiv>`, `Description`, `Parameters`, `Notes`, `Examples`, `Compatibility`, `See Also`. `[verified-by-code]` (git show 447aae13b03 `doc/src/sgml/ref/wait_for.sgml`). | — | — |
| 17 | `doc/src/sgml/ref/allfiles.sgml` | Add `<!ENTITY <name> SYSTEM "<name>.sgml">`. Without this the new SGML file is orphaned by the docs build. `[verified-by-code]` (`doc/src/sgml/ref/allfiles.sgml:195` for `&waitFor;`). | — | — |
| 18 | `doc/src/sgml/reference.sgml` | `&<entity>;` reference under the correct sub-tree (SQL commands list or app commands list). `[verified-by-code]` (git show 447aae13b03 `doc/src/sgml/reference.sgml`). | — | — |
| 19 | `doc/src/sgml/event-trigger.sgml` (*if* command supports event triggers) | If you routed through `ProcessUtilitySlow` for event-trigger firing, add a row to the support matrix. Banner comment at `utility.c:544-545` mandates this. `[from-comment]` (`src/backend/tcop/utility.c:544-545`). | — | — |
| 20 | `src/test/regress/sql/<existing-or-new>.sql` + `expected/*.out` | Regression test calling the statement; if it returns rows assert the result, if it has side effects assert via observable state. Add the test name to `parallel_schedule` or `serial_schedule` if new. `[inferred]` | — | testing |
| 21 | `src/test/recovery/t/0NN_<name>.pl` (or another TAP suite) — *if* the command needs a multi-node / standby scenario | TAP test under the appropriate suite. `WaitStmt` lives in `src/test/recovery/t/049_wait_for_lsn.pl`. `[verified-by-code]` (git show 447aae13b03 `src/test/recovery/t/049_wait_for_lsn.pl`). | — | testing |

Generated files that pick up the new Node automatically (do *not*
hand-edit, but verify rebuild touches them):
`src/backend/nodes/{copyfuncs.funcs.c,equalfuncs.funcs.c,outfuncs.funcs.c,readfuncs.funcs.c}`
and `src/include/nodes/nodetags.h`. Driven by
`src/backend/nodes/gen_node_support.pl` from `parsenodes.h`.
`[verified-by-code]` (`src/backend/nodes/gen_node_support.pl`).

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Grammar + Node.** Files: [1, 2, 3, 14]. Add the typedef
   to `parsenodes.h`, write the production rule in `gram.y`, add the
   keyword to `kwlist.h` if needed, register the typedef in
   `typedefs.list`. Phase-end check: `meson compile -C dev/build-debug`
   succeeds; verify
   `dev/build-debug/src/backend/nodes/{copy,equal,out,read}funcs.funcs.c`
   each contain a freshly-generated case for `XxxStmt`, and
   `src/include/nodes/nodetags.h` has `T_XxxStmt`.
2. **Phase 2 — Impl + dispatch.** Files: [4, 5, 6, 7, 8, 9, 10, 11,
   12, 13]. Write `Exec<Xxx>Stmt()` in the new commands/ file, expose
   it via the new header, wire the four `nodeTag()` switches plus
   the tuple-desc helpers if relevant, add the `CMDTAG_*` row.
   Phase-end check: `meson compile` clean; `psql -c '<NEW STATEMENT>'`
   reaches the new `Exec<Xxx>Stmt()` (set a breakpoint or add a
   `DEBUG1` log).
3. **Phase 3 — Tab-complete + docs.** Files: [15, 16, 17, 18, 19].
   Add tab-completion, the new ref page, the entity wiring,
   event-trigger table row. Phase-end check:
   `meson compile -C dev/build-debug alldocs` succeeds, the new
   page renders, and tab-complete fires after the keyword in
   `psql`.
4. **Phase 4 — Tests.** Files: [20, 21]. Regression + TAP coverage
   for happy path, permission failure, read-only / standby
   rejection, and parallel-mode rejection (per how you classified
   the command in step 8). Phase-end check:
   `meson test -C dev/build-debug --suite regress` and any TAP
   suite added pass.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/backend/nodes` (+3) |
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/tcop` |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/bin` |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/bin/psql` |
| [`tom-lane`](../personas/tom-lane.md) | `src/backend/commands` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`error-handling`](../idioms/error-handling.md) | direct reference |
| [`node-types`](../idioms/node-types.md) | shares files: `src/backend/nodes/gen_node_support.pl`, `src/include/nodes/parsenodes.h` |
| [`plan-cache`](../idioms/plan-cache.md) | shares files: `src/backend/tcop/utility.c` |
| [`process-utility-hook-chain`](../idioms/process-utility-hook-chain.md) | shares files: `src/backend/tcop/utility.c` |
| [`security-barrier-views`](../idioms/security-barrier-views.md) | shares files: `src/include/nodes/parsenodes.h` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **The four-switch trap.** `utility.c` has FOUR independent
  `switch (nodeTag(parsetree))` blocks (`ClassifyUtilityCommandAsReadOnly`,
  `standard_ProcessUtility`, `CreateCommandTag`, `GetCommandLogLevel`)
  plus two more tuple-related ones (`UtilityReturnsTuples`,
  `UtilityTupleDescriptor`). Missing any of the first three
  produces a runtime error or a wrong tag; missing the last two
  silently swallows result rows.  `[verified-by-code]`
  (`src/backend/tcop/utility.c:130, 597, 2042, 2101, 2385, 3290`).
- **`ProcessUtilitySlow` vs fast path.** Anything that fires event
  triggers, generates `pg_event_trigger_ddl_commands()` output, or
  needs to be visible in `ddl_command_start` / `ddl_command_end`
  hooks must route through `ProcessUtilitySlow`. Pure side-effect
  commands (CHECKPOINT, VACUUM, WAIT FOR) call their `Exec<Xxx>`
  directly from the main switch. `[from-comment]`
  (`src/backend/tcop/utility.c:534-545`).
- **`ProcessUtility_hook` ordering.** Extensions can intercept the
  utility before `standard_ProcessUtility` runs; if your statement
  does authorisation, the hook can be used to bypass it unless the
  check also lives in `Exec<Xxx>Stmt()`. Don't put security checks
  *only* in a pre-dispatch helper. `[from-comment]`
  (`src/backend/tcop/utility.c:518-530`).
- **Read-only and parallel-mode classification.** Choosing the
  wrong group in `ClassifyUtilityCommandAsReadOnly` either rejects
  the statement on standbys for no reason, or worse, lets it run
  when it shouldn't. Read the comment block at `utility.c:130-330`
  end-to-end — the categories are documented case by case.
  `[from-comment]` (`src/backend/tcop/utility.c:130-330`).
- **Tuple-returning utilities need `pquery.c` snowflakes.** When a
  utility returns rows, `pquery.c` has occasional special-cases via
  `IsA(utilityStmt, XxxStmt)` for portal strategy or
  describe-message handling. Grep for the existing tuple-returning
  utilities (`ExplainStmt`, `FetchStmt`, `ExecuteStmt`,
  `VariableShowStmt`, `WaitStmt`) and mirror the pattern.
  `[verified-by-code]` (`src/backend/tcop/pquery.c:1744`).
- **Forgetting `pgindent` typedef.** Without
  `src/tools/pgindent/typedefs.list` row, `pgindent` mis-formats
  every `XxxStmt *foo` declaration and CI's pgindent check fails.
  `[verified-by-code]` (`src/tools/pgindent/typedefs.list:3431`).
- **Synchronization traps (must change together):**
  - `parsenodes.h` ↔ generated copy/equal/out/read funcs — rebuild
    must regenerate; if `nodetags.h` doesn't gain `T_XxxStmt`, the
    Node won't dispatch.
  - All four switches in `utility.c` ↔ each other — easy to add to
    one and forget the others.
  - `kwlist.h` ↔ `gram.y` keyword list ↔ `psqlscan.l` /
    `ecpg/pgc.l` — if you added a new keyword, the keyword scenario
    enumerates the full sweep.
  - SGML `ref/<name>.sgml` ↔ `ref/allfiles.sgml` ↔ `reference.sgml`
    — orphaned ref pages don't get built.

## Verification (exact test invocations)

```bash
# Build picks up the new Node, generated funcs, and dispatch.
meson compile -C dev/build-debug

# Regression scope: at minimum the new statement's own .sql/.out,
# plus any existing suite the categorisation might affect.
meson test -C dev/build-debug --suite regress

# Tuple-returning utilities: portal tests can surface mis-wired
# UtilityReturnsTuples.
meson test -C dev/build-debug --suite regress --test portals

# Read-only / standby behaviour (the recovery suite is where most
# new utility-statement TAP tests land).
meson test -C dev/build-debug --suite recovery

# Tab-complete coverage — TAP test under the psql suite.
meson test -C dev/build-debug --suite psql

# Docs build verifies the new SGML page is wired correctly.
meson compile -C dev/build-debug alldocs
```

If you added a brand-new test (`src/test/regress/sql/<name>.sql` or
`src/test/recovery/t/0NN_<name>.pl`), name it explicitly here and
add it to the test schedule.

## Cross-refs

- Companion skills: `.claude/skills/parser-and-nodes/SKILL.md`,
  `.claude/skills/psql/SKILL.md` (tab-completion patterns),
  `.claude/skills/coding-style/SKILL.md` (pgindent / typedefs.list).
- Related scenarios: `scenarios/add-new-sql-keyword.md` (almost
  always unioned in), `scenarios/add-new-node-type.md` (if the
  utility introduces a *non-Stmt* node — usually it doesn't).
- Idioms: `knowledge/idioms/catalog-conventions.md` (for the
  "generated files, don't hand-edit" discipline that mirrors
  parsenodes regen), `knowledge/idioms/error-handling.md` (for the
  `ereport()` patterns in `Exec<Xxx>Stmt()`).
- Subsystems: `knowledge/subsystems/tcop.md`,
  `knowledge/subsystems/parser-and-rewrite.md`,
  `knowledge/subsystems/commands.md`.
- Files / dataflow: `knowledge/files/process-utility-hook-chain.md`
  (the dispatch path that the new `case T_XxxStmt` lands on),
  `knowledge/files/parser-pipeline.md` (how the grammar production
  becomes a `XxxStmt` Node), `knowledge/files/cursor-and-portal.md`
  (relevant if the utility returns tuples).
- Reference patch (canonical_commit):
  `git -C source show 447aae13b03` — the full 21-file `WAIT FOR`
  patch. Read it before drafting your own.
