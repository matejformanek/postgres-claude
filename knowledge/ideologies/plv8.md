# plv8 — a JavaScript PL that embeds a full V8 isolate per database user

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `plv8/plv8` @ branch `r3.2`. All `file:line` cites below point into that
> repo (not `source/`), since this doc characterizes an *external* extension's
> divergence from core idioms. Cites verified against the files fetched on
> 2026-06-09 (see Sources footer). This entry extends the A10 procedural-language
> sweep (`knowledge/issues/{plperl,plpython,pltcl}.md`) with a fourth PL.

## Domain & purpose

plv8 is "a PostgreSQL procedural language powered by the V8 Javascript Engine"
(`README.md:1-4`) `[from-README]`: you write SQL-callable functions, DO blocks,
triggers, and window functions in JavaScript, and plv8 compiles + runs them in an
embedded V8 (`CREATE EXTENSION plv8; … DO $$ plv8.elog(NOTICE, "hi"); $$ LANGUAGE
plv8;`, `README.md:Running/Testing`). It is the fourth PL the corpus has
characterized, and the most instructive comparison point for the A10 trust-gate
ranking, because its sandbox model is structurally different from all three of
plperl (opcode mask), plpython (no sandbox, untrusted-only), and pltcl (Safe
slave interpreter): plv8's isolation comes from V8 itself being a **pure-compute
JS VM with no ambient host bindings** — there is no filesystem, no network, no
`require`, no process access unless plv8 explicitly injects it. Written in C++,
linking libv8.

## How it hooks into PG

plv8 is a standard PL handler trio — `plv8_call_handler`, `plv8_call_validator`,
`plv8_inline_handler` (DO blocks), each `PG_FUNCTION_INFO_V1`
(`plv8.cc:56-71`) `[verified-by-code]` — registered via the usual
`CREATE LANGUAGE`/`pg_language` machinery, so (like all four PLs, per A10) it
delegates ACL gating entirely to fmgr/`pg_language`. Beyond the trio it adds two
**non-standard SQL-callable management functions** that have no analogue in the
core PLs: `plv8_reset()` and `plv8_info()` (`plv8.cc:63-64`) `[verified-by-code]`,
which tear down / introspect the per-user V8 state described below.

Three custom GUCs configure the embedded engine
(`plv8.cc:335-439`) `[verified-by-code]`:

| GUC | Effect |
|---|---|
| `plv8.start_proc` | a JS procedure run once when a user's context is first created (`:335-350`, executed at `:1838`) — plv8's analogue of plperl `on_init` |
| `plv8.v8_flags` | **raw passthrough to the engine** — `V8::SetFlagsFromString(plv8_v8_flags)` (`:369-384`, `:460-461`) feeds arbitrary V8 command-line flags into the embedded VM |
| `plv8.memory_limit` | caps V8 heap (MB); enforced by a custom array-buffer allocator + near-heap-limit GC callback (`:424-439`, `:307-318`) |

Cross-ref `[[knowledge/idioms/fmgr]]`, `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/idioms/error-handling]]`, `[[knowledge/idioms/memory-contexts]]`,
`.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. One full V8 `Isolate` + `Context` per database user, cached for backend lifetime

The defining structure is `plv8_context` (`plv8.h:115-125`) `[verified-by-code]`:
a `v8::Isolate *`, a `Persistent<Context>`, plus persistent object templates for
the `plv8` receiver, plans, cursors, and window objects. plv8 keeps a global
`ContextVector` of these, **one per `user_id`** — the call handler selects the
current user's context by scanning `ContextVector[i]->user_id == GetUserId()`
(`plv8.cc:572-577`), and the per-function compiled-`Function` cache is keyed on
`cache->user_id == ctx->user_id` (`:555`, `:1276`, `:1314`)
`[verified-by-code]`. Creating a context spins up a fresh isolate
(`CreateIsolate`, `:303-318`) with its own array-buffer allocator and resource
constraints, registers it in `ContextVector` (`:1833`), then runs `start_proc`
(`:1838`). This is a much heavier per-user sandbox than plperl's per-user Perl
interpreter (A10): a complete, independent JS VM with its own heap and GC per
role. The cost echoes the A10 "per-user interpreter never evicted" finding —
under transaction poolers the `ContextVector` accumulates one V8 isolate per
distinct role the backend ever served, which is exactly why plv8 had to add
`plv8_reset()` as an explicit escape hatch (`:570-587`, `killPlv8Context` at
`:548` disposes the isolate). Cross-ref `[[knowledge/architecture/process-model]]`,
`knowledge/issues/plperl.md` (per-user interpreter lifetime).

### 2. A triple error-model bridge: JS exception ↔ C++ exception ↔ PG `ereport`/`longjmp`

The core PLs bridge two error models; plv8 bridges three. `plv8.h:47-72`
`[verified-by-code]` defines `js_error` ("represents exceptions in JavaScript")
and `pg_error` (with the pointed comment "Instances of the class should be thrown
only in PG_CATCH block", `:70-72`). Every V8 entry point is wrapped in
`PG_TRY()`/`PG_CATCH()` (`plv8.cc:938/984`, `1399/1403`, `1430/1434`,
`1464/1468`) so a Postgres `ereport(ERROR)` `longjmp` is caught and re-thrown as
a C++ exception across V8's C++ frames; symmetrically, each handler ends with
`catch (js_error& e) { e.rethrow(); }` (`:540`, `:683`, `:1238`) turning a
JavaScript exception back into a Postgres error. V8's own failure modes —
interrupt, `execution timeout exceeded`, `Out of memory` — are likewise funneled
into `throw js_error(...)` (`:833-846`, `:1618-1625`). This is the same
exception-model-reconciliation problem `[[knowledge/ideologies/pg_duckdb]]`
(`InvokeCPPFunc`) and `[[knowledge/ideologies/pgrx]]` (`pg_guard_ffi_boundary`)
solve, but with the extra JS-exception layer V8 interposes. Cross-ref
`[[knowledge/idioms/error-handling]]`.

### 3. Sandboxing by *absence of host bindings* — the strongest PL sandbox in the corpus, but with a raw `v8_flags` escape

Where plperl maintains a drift-prone opcode mask and pltcl uses a Safe slave
interpreter (A10), plv8's trust model is that V8 is a pure JS compute engine: a
freshly-created `Context` has no `require`, no `fs`, no `process`, no network —
only what plv8 wires onto the receiver/global templates (`SetupCursorFunctions`,
`SetupWindowFunctions`, the `plv8` object, `plv8.cc:1810-1830`)
`[verified-by-code]`. There is nothing to mask or to remove because the dangerous
surface was never present; this makes trusted-`plv8` arguably the cleanest PL
sandbox documented so far (stronger than Tcl Safe, which removes commands from an
otherwise-capable interpreter). **The qualifier:** `plv8.v8_flags`
(`plv8.cc:369-384`) is a raw `V8::SetFlagsFromString` passthrough — a superuser
who sets it (it is processed at `_PG_init`/option time) can toggle arbitrary V8
engine flags, including ones affecting JIT/security posture. That GUC is the
single widest non-JS lever and the one worth a Phase-D note. Cross-ref
`knowledge/issues/pltcl.md`, `knowledge/issues/plperl.md`, the
`pl-trust-gates` idiom candidate flagged in A10.

### 4. A second heap, with its own memory cap, outside Postgres MemoryContexts

V8's JS heap is not a Postgres `MemoryContext`, so the OOM-throws-`ereport`
contract (`memory-contexts` skill) does not cover it. plv8 reimplements a bound:
`CreateIsolate` installs a custom `ArrayAllocator(plv8_memory_limit * 1_MB)` and
`ResourceConstraints` (`plv8.cc:307-312`), an `OOMErrorHandler`, a
`GCEpilogueCallback`, and a `NearHeapLimitHandler` that forces collection as the
heap approaches `plv8_memory_limit` (`:217-225`, `:316-318`)
`[verified-by-code]`. Core PG has no per-function memory ceiling because all
allocation flows through contexts that are reset per query; plv8 must add one
because the JS heap lives entirely outside that discipline. The Converter class
*does* keep a `MemoryContext m_memcontext` (`plv8.h:168`) for the Datum-marshalling
side, so the boundary is explicit: PG memory for Datums, V8 heap for JS objects.
Cross-ref `[[knowledge/idioms/memory-contexts]]`.

## Notable design decisions (cited)

- **`plv8_info()` exposes per-user V8 heap stats as JSON** — it walks
  `ContextVector`, and for each context emits the `user` name (via
  `GetUserNameFromId`) plus `GetMemoryInfo` (`plv8.cc:625-636`)
  `[verified-by-code]`. A monitoring surface that reveals which roles have live
  JS contexts and how much V8 heap each holds — a mild info-leak in the
  A11/A14 "monitoring-as-extraction" family if granted broadly.
- **Window-function + SRF support need C++ destructor RAII** — `WindowFunctionSupport`
  and the SRF helper are classes specifically "because the destructor" must run
  cleanup (`plv8.h:201-204,245-247`), threading C++ object lifetimes through
  Postgres' `longjmp`-based control flow (the reason the PG_TRY wrapping in §2 is
  load-bearing).
- **`start_proc` runs before the context is fully usable** — it is invoked right
  after `ContextVector.push_back` with a comment that code may "recursively …
  want the global context" (`plv8.cc:1828-1838`), so the context is registered
  *before* the startup proc runs — an ordering footgun if `start_proc` errors.
- **Per-user function cache stores `prosrc`** — `killPlv8Context` `pfree`s a
  cached `prosrc` per function (`plv8.cc:557-562`), i.e. plv8 caches the
  JavaScript source text per (user, function) in the backend, freed only on reset.
- **Dialect note / corpus gap:** older plv8 shipped `plcoffee`/`plls`
  (CoffeeScript/LiveScript) dialects; the queued manifest named `coffee-script.cc`,
  but the `r3.2` tree no longer contains it (only `plv8.control.common` remains) —
  the dialect transpilers appear dropped or relocated in 3.2. Marked `[unverified]`
  pending a closer look; this doc characterizes the plain-JS handler only.

## Links into corpus

- `knowledge/issues/plperl.md`, `knowledge/issues/plpython.md`,
  `knowledge/issues/pltcl.md` — the A10 PL sweep this extends; plv8 is the fourth
  data point for the **cross-PL trust-gate ranking** (V8-no-host-bindings ≥ Tcl
  Safe > Perl opcode-mask > plpgsql nothing; plpython untrusted-only).
- `[[knowledge/idioms/fmgr]]` — the `plv8_call_handler`/`validator`/
  `inline_handler` trio + `plv8.execute`/`plv8.prepare` SPI bridge.
- `[[knowledge/idioms/error-handling]]` — the JS↔C++↔`ereport` triple bridge
  (`js_error`/`pg_error` + PG_TRY/PG_CATCH + `e.rethrow()`).
- `[[knowledge/idioms/memory-contexts]]` — the V8 second heap and its custom
  `memory_limit` enforcement outside PG contexts.
- `[[knowledge/idioms/bgworker-and-parallel]]` — `plv8.start_proc` /
  `plv8.v8_flags` / `plv8.memory_limit` custom GUCs.
- `[[knowledge/ideologies/pg_duckdb]]`, `[[knowledge/ideologies/pgrx]]` — the
  same C++/Rust ↔ `ereport`/`longjmp` boundary problem, here with an added JS layer.
- `.claude/skills/extension-development/SKILL.md`, `.claude/skills/error-handling/SKILL.md`,
  `.claude/skills/gucs-bgworker-parallel/SKILL.md`.

## Anthropology takeaway

plv8 completes the PL quartet and sharpens the corpus's trust-gate thesis: the
*strongest* sandbox is the one built on an engine that never had host capabilities
to begin with (V8), not one that subtracts them after the fact (Tcl Safe, Perl
opcode mask). Its three structural taxes — a full per-user VM cached for backend
life, a triple error-model bridge, and a second heap needing its own memory cap —
are the recurring price of hosting *any* foreign engine inside a Postgres backend
(cf. pg_duckdb's DuckDB, pgrx's Rust runtime). **Phase-D notes:** (a)
`plv8.v8_flags` raw passthrough is the widest superuser lever; (b) `ContextVector`
isolate accumulation under poolers is the A10 per-user-interpreter leak at V8
scale, with `plv8_reset()` as the only manual remedy; (c) `plv8_info()` is a
new "monitoring-as-extraction" site.

## Sources

Fetched 2026-06-09 (branch `r3.2`):

- `https://api.github.com/repos/plv8/plv8/git/trees/r3.2?recursive=1`
  @ 2026-06-09 → HTTP 200 (tree listing; confirmed no `coffee-script.cc` in r3.2).
- `https://raw.githubusercontent.com/plv8/plv8/r3.2/README.md`
  @ 2026-06-09 → HTTP 200 (1839 bytes).
- `https://raw.githubusercontent.com/plv8/plv8/r3.2/plv8.h`
  @ 2026-06-09 → HTTP 200 (9588 bytes; plv8_context, js_error/pg_error, Converter).
- `https://raw.githubusercontent.com/plv8/plv8/r3.2/plv8.cc`
  @ 2026-06-09 → HTTP 200 (65609 bytes; handlers, per-user context vector,
  CreateIsolate, GUCs, PG_TRY bridging — cited regions deep-read, rest skimmed).

All cites are `[verified-by-code]` against the fetched `.h`/`.cc` (handler trio +
management fns, `plv8_context` struct, `ContextVector` per-user selection, isolate
creation + memory-limit callbacks, GUC definitions, PG_TRY/PG_CATCH + rethrow
bridging) except the end-user feature narrative (JS functions/triggers/window
funcs, V8-as-pure-VM sandbox claim) which is `[from-README]`/`[inferred]` from the
template-setup code, and the dropped-dialect note which is `[unverified]`. The
SPI bridge (`plv8.execute`/`plv8.prepare`), type marshalling (`plv8_type.cc`), and
window/SRF helpers were skimmed, not deep-read.
