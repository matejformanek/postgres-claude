---
scenario: add-new-hook
when_to_use: I want to add a new extension hook point in the backend (planner_hook / ExecutorStart_hook / ProcessUtility_hook style) so loadable modules can observe or override behavior at a specific call site.
companion_skills: ["bgworker-and-extensions"]
related_scenarios: ["add-startup-hook", "add-new-guc"]
canonical_commit: 94f3ad3961a
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new extension hook

## Scope — what's in / out

**In scope:**
- One new `Xxx_hook` global of type `Xxx_hook_type`, declared in the
  matching `src/include/.../*.h` and defined (`= NULL`) in the .c file
  that owns the call site.
- A wrapping `if (Xxx_hook) Xxx_hook(...) else standard_Xxx(...);`
  pattern at the call site — or, for pure observation hooks, an
  unconditional `if (Xxx_hook) Xxx_hook(...)` after the work runs.
- Exporting (`PGDLLIMPORT`) so out-of-tree extensions on Windows can
  link the symbol.
- If the hook replaces a function (planner_hook, ProcessUtility_hook
  style), exposing a `standard_<name>` entry point so chained
  extensions can fall through.
- A test module under `src/test/modules/<name>/` that exercises the
  chain pattern (`prev_hook` save + call + restore) — many real
  patches add one even for tiny hooks.

**Out of scope:**
- Hooks added inside the postmaster / `PostgresMain` /
  `InitPostgres` startup lifecycle (different audience, different
  pitfalls) → see `add-startup-hook`.
- Adding a new bgworker that *uses* an existing hook → see
  `add-new-bgworker`.
- Adding a GUC that toggles your hook's behavior → see `add-new-guc`
  and union the checklists.
- "Object access" hook adjustments inside `objectaccess.c` — the
  shape is similar but the framework around it (`OAT_*` enum +
  `ObjectAccessType` argument) needs its own playbook.
- Catalog changes — hooks are pure runtime plumbing, no catversion
  bump, no `pg_proc.dat`.

## Pre-flight

- **Companion skills:** load `bgworker-and-extensions` (`_PG_init`
  pattern, `shared_preload_libraries`, chaining the previous hook,
  PGDLLIMPORT). It's the procedural counterpart to this playbook.
- **Canonical commit:** `94f3ad3961a` — *Add planner_setup_hook and
  planner_shutdown_hook* (Robert Haas, 2025-10-08). 27 inserted lines
  across two files (`planner.c` + `planner.h`), no tests, no docs —
  the minimum-viable shape of a "new hook" patch [verified-by-code](source/src/backend/optimizer/plan/planner.c:74-83). Read it before starting.
- **Discussion-list reality check:** adding a hook needs broad
  agreement on `pgsql-hackers`. A "we need this for one
  out-of-tree extension" justification is regularly rejected. Hooks
  that get committed tend to (a) compose with an in-tree feature
  (e.g. `extendplan.h`), (b) replace a uglier private patch
  reviewers are already aware of, or (c) be too small to argue with.
  `94f3ad3961a` is type (a); plan accordingly. [inferred]
- **Common pitfalls (one-line each):**
  - Forgot `PGDLLIMPORT` on the extern declaration — Windows builds
    of the calling extension fail to link [verified-by-code](source/src/include/optimizer/planner.h:33).
  - Made the hook *replace* the work but didn't export
    `standard_<name>` — extensions can no longer chain to the
    default behavior [verified-by-code](source/src/include/optimizer/planner.h:58-61).
  - Documented contract drift: the hook fires at a moment that
    later refactors silently move (e.g. before vs. after a memory
    context switch). Comment the call site explicitly.
  - Called the hook from a path that runs during recovery /
    bootstrap / single-user mode without thinking through what
    state is valid there.

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/<area>/<owner>.h` | Add `typedef <ret> (*Xxx_hook_type) (<args>);` immediately followed by `extern PGDLLIMPORT Xxx_hook_type Xxx_hook;`. Group with sibling hooks if the file already has any. PGDLLIMPORT is mandatory for Windows extension linkage [verified-by-code](source/src/include/optimizer/planner.h:28-33),[verified-by-code](source/src/include/executor/executor.h:76-92). If the hook *replaces* a function, also declare the `extern <ret> standard_Xxx(...)` entry point next to it [verified-by-code](source/src/include/optimizer/planner.h:58-61),[verified-by-code](source/src/include/tcop/utility.h:71-86). | (header-specific — `planner.h`, `executor.h`, `utility.h`, `analyze.h`) | bgworker-and-extensions |
| 2 | `src/backend/<area>/<owner>.c` | Define the global: `Xxx_hook_type Xxx_hook = NULL;` near the top of the file, alongside any sibling hook globals [verified-by-code](source/src/backend/optimizer/plan/planner.c:74),[verified-by-code](source/src/backend/executor/execMain.c:70-76),[verified-by-code](source/src/backend/tcop/utility.c:72). Then wrap the call site: `if (Xxx_hook) (*Xxx_hook)(...); else standard_Xxx(...);` for replacement hooks [verified-by-code](source/src/backend/tcop/utility.c:522-528), or `if (Xxx_hook) (*Xxx_hook)(...);` for observation hooks [verified-by-code](source/src/backend/parser/analyze.c:149-150). For replacement hooks, also split the existing implementation into `standard_Xxx()` so it remains callable. | [planner.c.md](../files/src/backend/optimizer/plan/planner.c.md) / [execMain.c.md](../files/src/backend/executor/execMain.c.md) / [utility.c.md](../files/src/backend/tcop/utility.c.md) / [analyze.c.md](../files/src/backend/parser/analyze.c.md) | bgworker-and-extensions |
| 3 | `src/test/modules/<name>/<name>.c` | (NEW or existing) Demo / test extension that installs the hook in `_PG_init`, saves the previous pointer (`prev_xxx_hook = xxx_hook; xxx_hook = my_func;`), and chains in the implementation (`if (prev_xxx_hook) prev_xxx_hook(...); else standard_xxx(...);`). The `delay_execution` test module is the smallest working example [verified-by-code](source/src/test/modules/delay_execution/delay_execution.c:36-72). | — | bgworker-and-extensions |
| 4 | `src/test/modules/<name>/Makefile` | (NEW if creating a new module) Standard PGXS Makefile naming `MODULES = <name>` and `REGRESS = <suite>`. Copy the pattern from `src/test/modules/delay_execution/Makefile`. | — | testing |
| 5 | `src/test/modules/<name>/meson.build` | (NEW if creating a new module) Meson companion: `test_install_libs += shared_module('<name>', files('<name>.c'), …)`. Copy from a sibling module; both build systems must be wired. | — | testing |
| 6 | `src/test/modules/meson.build` | (NEW-module only) Add `subdir('<name>')` so meson picks the module up. [verified-by-code](source/src/test/modules/meson.build) | — | testing |
| 7 | `src/test/modules/Makefile` | (NEW-module only) Add the module to `SUBDIRS = ...`. | — | testing |
| 8 | `src/test/modules/<name>/sql/<suite>.sql` and `expected/<suite>.out` | (NEW) Regression script that loads the extension and exercises the hook (e.g. via a side-effect GUC or log message). Mirrors `delay_execution/specs/`. | — | testing |
| 9 | `doc/src/sgml/xfunc.sgml` | Most hooks are *not* documented in the user manual (they're an internals API exposed only to extension authors via the header file). Update this only if the hook is part of a documented extension surface (e.g. the `shmem_request_hook` paragraph at lines around 3796-3819) [verified-by-code](source/doc/src/sgml/xfunc.sgml:3798). For the common case, the header comment IS the documentation. | — | — |
| 10 | `doc/src/sgml/release-NN.sgml` | Hook additions land in the release notes under "Source Code" (committer adds this at release-notes time; PR author can pre-stage it). [verified-by-code](source/doc/src/sgml/release-19.sgml) — `cac0f24eb57` ("doc PG 19 relnotes: add two optimizer hooks") shows the shape. | — | — |

(Use `—` in the per-file doc column for genuinely-new files or for
files whose per-file doc hasn't been written yet.)

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Header + global, no call site yet.** Files: [1, 2].
   Add the `typedef`, the `extern PGDLLIMPORT`, and the `= NULL`
   global. Don't touch the call site yet. Phase-end check:
   `meson compile -C dev/build-debug` succeeds. The hook is
   declared and defined but never invoked.

2. **Phase 2 — Wire the call site (+ `standard_<name>` if replacing).**
   Files: [2]. Insert the `if (Xxx_hook) ... else standard_Xxx(...)`
   guard. If this is a replacement hook, refactor the existing body
   into `standard_Xxx()` and export it in the header. Phase-end
   check: full regression — `meson test -C dev/build-debug
   --suite regress` — passes unchanged because no extension is
   installing the hook yet. A green run here proves the refactor
   into `standard_<name>` was behavior-preserving.

3. **Phase 3 — Demo / test module exercises the chain.** Files: [3-8].
   Write a minimal test module that saves `prev_xxx_hook`, installs
   its own, and verifies the chain by logging or by a side-effect
   GUC. Phase-end check: `meson test -C dev/build-debug --suite
   setup --suite <new-module-name>` (or whatever suite the module
   declares) passes. Run the regression twice: once with module
   loaded, once without, to confirm the hook is truly optional.

4. **Phase 4 — Docs + release notes.** Files: [9, 10]. Most hooks
   skip `xfunc.sgml` and only touch release notes; do whichever
   applies. Phase-end check: `meson test -C dev/build-debug --suite
   docs`.

## Pitfalls

- **Missing `PGDLLIMPORT`** — the build is green on Linux/macOS but
  any extension on Windows fails to link the symbol. Every existing
  in-tree hook uses `extern PGDLLIMPORT` — match them exactly
  [verified-by-code](source/src/include/optimizer/planner.h:33),[verified-by-code](source/src/include/executor/executor.h:78).
- **Replacement hook without an exported `standard_<name>`** — the
  first extension that installs your hook works; the second one
  (chained) can no longer fall through to the default behavior
  because it can't name the function it's supposed to delegate to.
  Always export both `if (hook)` and `standard_<name>` together
  [verified-by-code](source/src/include/optimizer/planner.h:58-61),[verified-by-code](source/src/include/tcop/utility.h:85-87).
- **Hook fires during recovery / single-user / bootstrap** — many
  call sites are not safe for arbitrary extension code in those
  modes (no transaction, no relcache, no syscache, no GUC). If your
  call site is reachable from those paths, either comment the
  contract or guard with `IsUnderPostmaster` / `IsBootstrapProcessingMode`.
  See `knowledge/issues/storage-ipc.md` for documented examples. [inferred]
- **Hook executed inside a critical section** — extension code that
  ereports or palloc-fails turns into PANIC. If the call site sits
  in a `START_CRIT_SECTION()` block, that's almost always a reason
  to reject the hook on -hackers. [inferred]
- **Forgot to save & restore the previous hook in the demo module**
  — works in single-extension testing, breaks chains. The
  `delay_execution` module shows the right pattern
  [verified-by-code](source/src/test/modules/delay_execution/delay_execution.c:36-72).
- **Hook signature change later** — once a hook ships in a release
  it's effectively an ABI commitment. Out-of-tree extensions pin to
  it. Pick the signature carefully; passing a context struct (so
  fields can be added without breaking callers) is friendlier than
  positional args.

- **Synchronization traps** (sibling files that must change together):
  - Header `extern PGDLLIMPORT Xxx_hook_type Xxx_hook;` ↔ .c
    `Xxx_hook_type Xxx_hook = NULL;` (declare in .h, define in
    exactly one .c).
  - Replacement-hook split ↔ `extern standard_Xxx()` in .h (must
    appear together; otherwise extensions can't chain).
  - New test module ↔ both `src/test/modules/meson.build` and
    `src/test/modules/Makefile` (each build system, every time).

## Verification (exact test invocations)

```bash
# Build with the new hook + test module
meson compile -C dev/build-debug

# Baseline: full regression with NO extension loaded — must be green
# (proves the call-site refactor into standard_<name> didn't regress)
meson test -C dev/build-debug --suite regress

# Exercise the demo extension that installs the hook
meson test -C dev/build-debug --suite setup
meson test -C dev/build-debug --test <new-module-name>

# If the hook intersects ProcessUtility / executor: run isolation too
meson test -C dev/build-debug --suite isolation

# Docs (only if you touched SGML)
meson test -C dev/build-debug --suite docs

# Manual smoke: load the demo extension via shared_preload_libraries,
# observe the hook fires.
echo "shared_preload_libraries = '<module-name>'" >> dev/data-debug/postgresql.conf
dev/install-debug/bin/pg_ctl -D dev/data-debug restart
psql -h /tmp -c "SELECT 1;"   # confirm log / side effect
```

If you genuinely created a brand-new regression test file under
`src/test/modules/<name>/sql/`, the test name is
`<name>/<suite>` in meson output; otherwise the existing test name
covers it.

## Cross-refs

- Companion skills: `.claude/skills/bgworker-and-extensions/SKILL.md`
  (the `_PG_init` + hook-chain pattern), `.claude/skills/extension-development/SKILL.md`.
- Related scenarios: `scenarios/add-startup-hook.md` (lifecycle
  hooks in `PostmasterMain` / `PostgresMain` / `InitPostgres` —
  different timing constraints), `scenarios/add-new-guc.md` (often
  paired: hook + GUC toggle), `scenarios/add-new-bgworker.md`,
  `scenarios/add-new-extension.md` (delivery vehicle for the demo).
- Idioms: `knowledge/idioms/process-utility-hook-chain.md` (the
  canonical chain pattern, with the `prev_hook` save/restore /
  invoke recipe).
- Subsystems: `knowledge/subsystems/optimizer.md` (where most
  planner hooks live), `knowledge/subsystems/executor.md` (the
  `ExecutorXxx_hook` family), `knowledge/subsystems/tcop.md`
  (`ProcessUtility_hook`), `knowledge/subsystems/parser-and-rewrite.md`
  (`post_parse_analyze_hook`), `knowledge/subsystems/libpq-backend.md`
  (`ClientAuthentication_hook`).
- Issues: `knowledge/issues/storage-ipc.md` (recovery / single-user
  / bootstrap state assumptions for hooks reachable from startup).
- Reference patch (canonical_commit): `git -C source show 94f3ad3961a`.
- Other small reference patches:
  - `4020b370f21` — *Allow for plugin control over path generation
    strategies* (two more optimizer hooks).
  - `f4122a8d50a` — *Add a hook in ExecCheckRTPerms()*.
  - `a5495cd8411` — *Add a hook to let loadable modules get control
    at ProcessUtility ...* (historical origin of
    `ProcessUtility_hook`).
