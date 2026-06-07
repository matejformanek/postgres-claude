---
source_url: https://www.postgresql.org/docs/current/custom-scan.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
note: docs page body rendered as ToC-only via the markdown converter; the callback contract below is taken from the authoritative header source/src/include/nodes/extensible.h at the anchor SHA.
---

# Docs distilled — Chapter 60: Writing a Custom Scan Provider

The most invasive extension surface short of a table AM: a loadable module
injects its **own plan node** into the plan tree. Three pluggable scopes — path,
plan, exec — each a struct of function pointers, plus a name-keyed registry so a
parallel worker can rebuild the node after the plan is serialized across a DSM
boundary. The official chapter renders as ToC-only through our fetch pipeline, so
every callback here is cited to `extensible.h` directly. The three-step model
the chapter does state: **(1) generate paths during planning, (2) convert chosen
path to a plan, (3) execute the plan.** [from-docs]

## Step 1 — paths (`CustomPathMethods`)

- Struct at `source/src/include/nodes/extensible.h:88`. [verified-by-code]
- `const char *CustomName;` (`:89`) — the human-readable provider name. [verified-by-code]
- `Plan *(*PlanCustomPath)(...)` (`:91-94`) — turn a chosen `CustomPath` into a
  `CustomScan` plan node (args: root, rel, best_path, tlist, clauses,
  custom_plans). [verified-by-code]
- `List *(*ReparameterizeCustomPathByChild)(...)` (`:95-97`) — re-express the
  path for a partition child (parameterized-path / partitionwise-join support).
  [verified-by-code]
- **How a provider gets the chance to add a path:** it installs
  `set_rel_pathlist_hook` (base-rel paths) and/or `set_join_pathlist_hook` (join
  paths) in `_PG_init`, and inside the hook calls `add_path` with a `CustomPath`.
  [from-docs] [verified-by-code, source/src/backend/optimizer/path/allpaths.c +
  joinpath.c — the two hook call sites; via knowledge/subsystems/optimizer.md]

## Step 2 — plan (`CustomScanMethods`)

- Struct at `extensible.h:103`. [verified-by-code]
- `const char *CustomName;` (`:104`). [verified-by-code]
- `Node *(*CreateCustomScanState)(CustomScan *cscan);` (`:107`) — build the
  `CustomScanState` (the executor-time node) from the serialized plan node.
  [verified-by-code]

## Step 3 — exec (`CustomExecMethods`, `extensible.h:112`)

**Required** (`:115-119`):
- `BeginCustomScan(node, estate, eflags)` — executor setup.
- `ExecCustomScan(node)` → `TupleTableSlot *` — return one tuple (or empty slot at EOF).
- `EndCustomScan(node)` — teardown.
- `ReScanCustomScan(node)` — restart.

**Optional — mark/restore** (`:122-123`): `MarkPosCustomScan`, `RestrPosCustomScan`
— only needed if the node can sit under a merge join that backs up.

**Optional — parallel** (`:126-137`): `EstimateDSMCustomScan`,
`InitializeDSMCustomScan`, `ReInitializeDSMCustomScan`,
`InitializeWorkerCustomScan`, `ShutdownCustomScan` — the DSM
estimate/init/worker-attach/shutdown cycle a parallel-aware node implements
(mirrors the `Estimate/InitializeDSM/InitializeWorker` pattern in `nodeXxx.c`).
[verified-by-code]

**Optional — EXPLAIN** (`:140-141`): `ExplainCustomScan(node, ancestors, es)`.
[verified-by-code]

## The registry — why name-keyed (the load-bearing gotcha)

- `extern void RegisterCustomScanMethods(const CustomScanMethods *methods);`
  (`extensible.h:144`) and
  `extern const CustomScanMethods *GetCustomScanMethods(const char *CustomName,
  bool missing_ok);` (`:145-146`). [verified-by-code]
- **Why it exists:** a plan tree is serialized (`outfuncs`/`readfuncs`) to ship to
  a **parallel worker**, but C function pointers can't be serialized. The
  `CustomScan` node carries the provider's `CustomName` *string*; the worker calls
  `GetCustomScanMethods(name)` to recover the methods table by name. A provider
  that intends to be parallel-safe MUST `RegisterCustomScanMethods` in `_PG_init`
  of every backend (i.e. via `shared_preload_libraries`), or the worker's lookup
  fails. [inferred — from the serialize-by-name design] [verified-by-code,
  registry API present at extensible.h:144-146]
- Same `Register*/Get*` pattern exists for `ExtensibleNode` (`RegisterExtensibleNodeMethods`)
  used to carry custom private data through copy/out/read funcs. [verified-by-code,
  source/src/include/nodes/extensible.h — `ExtensibleNodeMethods`]

## Links into corpus

- [[knowledge/subsystems/executor.md]] — the `ExecInitNode`/`ExecProcNode`/
  `ExecEndNode`/`ExecReScan` dispatch the `CustomExecMethods` mirror, and the
  parallel DSM estimate/init pattern.
- [[knowledge/subsystems/optimizer.md]] — `set_rel_pathlist_hook` /
  `set_join_pathlist_hook` / `add_path`, the path-injection points.
- [[knowledge/docs-distilled/fdwhandler.md]] — sibling "inject a scan node"
  surface; FDW is the cooked version, custom-scan is the raw one.
- [[knowledge/docs-distilled/parallel-query.md]] — the DSM/worker model the
  parallel callbacks plug into.
- executor-and-planner + gucs-bgworker-parallel skills.

## Gaps / follow-ups

- The official prose subsections (60.1/60.2/60.3) did not render through the fetch
  pipeline (ToC-only). If a future run can obtain the rendered prose, re-verify
  the "required vs optional" split against the chapter wording (currently taken
  from the `extensible.h` comment grouping). No per-file corpus doc yet for
  `src/backend/executor/nodeCustom.c`.
