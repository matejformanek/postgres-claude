---
path: src/test/modules/plsample/plsample.c
anchor_sha: e18b0cb7344
loc: 354
depth: read
---

# src/test/modules/plsample/plsample.c

## Purpose

A pedagogical, minimal procedural language handler. Demonstrates the contract
that every PL (PL/pgSQL, PL/Python, PL/Perl, …) must satisfy: a single C
function registered as `CREATE LANGUAGE ... HANDLER plsample_call_handler`
that receives a `PG_FUNCTION_ARGS` carrying enough context to know whether
it's a regular call, a trigger, or an event trigger, and to retrieve the
function's source text from `pg_proc.prosrc` and "execute" it. `[verified-by-code]`

This file is the canonical "show me how to write a PL handler" example for
extension authors; the real PLs follow the same skeleton.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `plsample_call_handler` | `plsample.c:39` | The single SQL-callable function registered as the language handler |
| `plsample_func_handler` (static) | `:93` | Body for regular function calls — fetches `pg_proc`, prints args, returns either source text (if `prorettype=TEXT`) or NULL |
| `plsample_trigger_handler` (static) | `:205` | Body for trigger calls — fetches `pg_proc`, prints trigger metadata (event, level, args), returns the original tuple |

## Internal landmarks

- `CALLED_AS_TRIGGER(fcinfo)` / `CALLED_AS_EVENT_TRIGGER(fcinfo)` dispatch on
  `fcinfo->context` shape (`:55-78`).
- Source text is retrieved via `SearchSysCache1(PROCOID, …)` then
  `SysCacheGetAttr(.. Anum_pg_proc_prosrc)` (`:116-132`, `:230-248`).
- A `PG_TRY` / `PG_FINALLY` wraps the dispatch (`:49-83`) so any cleanup
  (none in this skeleton, but real PLs free interpreter contexts here) is
  reached even on `ereport(ERROR)`.
- Per-function `MemoryContext` (`proc_cxt`) at `:141` shows the standard
  pattern: cache per-function state in a context that the function's
  lifetime owns, not in `CurrentMemoryContext`.
- For triggers the handler `SPI_connect()`s and `SPI_register_trigger_data()`
  so that `NEW`/`OLD` are reachable from any nested SQL (`:223-227`).

## Invariants & gotchas

- **Test module — never load in production.** This is a documentation
  artifact in C form, not a working interpreter.
- The trigger branch uses `PG_CATCH` + `PG_RE_THROW` (`:343-347`) — the
  comment says "Error cleanup code would go here". Real PLs put interpreter
  teardown here. Forgetting `PG_RE_THROW` would swallow errors and is the
  classic PG_TRY bug.
- The function branch's "return value" rule is non-standard: if
  `prorettype != TEXTOID` it returns NULL, else it returns the source text
  via the type's input function (`:183-197`). This is a placeholder; real
  PLs run the compiled body.
- `ReleaseSysCache` must match every `SearchSysCache` (`:163`, `:173`,
  `:194`, `:257`) — leaking a syscache pin is a subtle bug that only shows
  up under cache pressure.

## Cross-refs

- `source/src/pl/plpgsql/src/pl_handler.c` — the real PL/pgSQL handler that
  this skeleton models.
- `source/src/include/commands/trigger.h` — `TriggerData`, the `TRIGGER_FIRED_*`
  macros used by the trigger arm.
- `source/src/backend/utils/fmgr/funcapi.c` — `get_func_arg_info`, used
  here to enumerate argument names/modes.
- `knowledge/idioms/fmgr-and-spi.md` — once written, this is the example
  the doc should reference.
