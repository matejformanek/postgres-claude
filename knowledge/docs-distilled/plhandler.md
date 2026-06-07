---
source_url: https://www.postgresql.org/docs/current/plhandler.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 58: Writing a Procedural Language Handler

How a new PL (plpgsql, plperl, plpython, pltcl — or a third-party one) hooks into
the server. A PL is **three C functions** registered with `CREATE LANGUAGE`, the
core dispatching through them via fmgr. This is the producer side of the
privileged-sandbox boundary the A9/A10 sweeps mapped from the consumer side.

## The three functions

1. **Call handler (required).** Version-1 C function returning `language_handler`.
   Every call of *any* function written in the PL is routed here. The handler
   reads which function to run from `flinfo->fn_oid` — **the OID of the
   user's function, NOT the handler's** — and fetches its `pg_proc` row to get
   the source text (`prosrc`) etc. [from-docs]
   [verified-by-code, source/src/include/fmgr.h — `FunctionCallInfoBaseData`,
   `flinfo->fn_oid`; via knowledge/idioms/fmgr.md]
2. **Inline handler (optional).** Takes one `internal` arg, returns void. Invoked
   for `DO` blocks; the arg is a pointer to an `InlineCodeBlock` carrying the
   anonymous block's source. Languages without it can't be used in `DO`. [from-docs]
3. **Validator (optional).** Takes one `oid`, returns void. Called at the end of
   `CREATE FUNCTION` to syntax/type-check the new function body. [from-docs]

## fmgr details the handler must honor

- **`flinfo->fn_oid`** identifies the target function (not the handler). [from-docs]
- **`flinfo->fn_extra`** is the handler's per-function cache slot: starts NULL,
  the handler may stash parsed/compiled state there to avoid re-parsing on every
  call. **Must be allocated in `flinfo->fn_mcxt`** (or a longer-lived context) so
  it survives for the function's lifetime — allocating in a transient context is a
  use-after-free bug. [from-docs] [verified-by-code, source/src/include/fmgr.h —
  `fn_extra`, `fn_mcxt`]
- **Trigger detection:** when the function is fired as a trigger,
  `fcinfo->context` points to a `TriggerData` node instead of being NULL; the
  `CALLED_AS_TRIGGER(fcinfo)` macro is the idiomatic test. The handler must give
  the PL's code a way to reach the trigger data. [from-docs]
  [verified-by-code, source/src/include/commands/trigger.h — `CALLED_AS_TRIGGER`]
- Event-trigger calls similarly arrive via `EventTriggerData` /
  `CALLED_AS_EVENT_TRIGGER`. [inferred, from-docs]

## The validator's responsibilities (security-relevant)

- **MUST call `CheckFunctionValidatorAccess()` first.** This guards against a user
  invoking the validator directly on a function they shouldn't (the validator runs
  with the definer's assumptions); skipping it is a privilege bug. [from-docs]
  [verified-by-code, source/src/backend/commands/proclang.c —
  `CheckFunctionValidatorAccess`]
- **MUST honor `check_function_bodies`** (GUC): when off, skip the expensive
  body checks. `pg_dump` restores with `check_function_bodies=off` so that
  functions referencing not-yet-created objects can be defined out of order; a
  validator that ignores the GUC breaks restore. [from-docs]
  [verified-by-code, source/src/backend/utils/misc/guc_tables.c —
  `check_function_bodies`]
- Errors are reported with `ereport()`, which aborts the surrounding
  `CREATE FUNCTION` transaction. [from-docs]

## `CREATE LANGUAGE` / `pg_language` wiring

- `lanplcallfoid` → call handler OID; `laninline` → inline handler OID (0 if
  none); `lanvalidator` → validator OID (0 if none). [from-docs]
  [verified-by-code, source/src/include/catalog/pg_language.h]
- `lanpltrusted` marks trusted vs untrusted. A **trusted** language can be used by
  any user (the handler is responsible for sandboxing — see the A9/A10 trust-gate
  findings); an **untrusted** language requires the function owner to be
  superuser. The core enforces the superuser check on untrusted PLs; everything
  past that is the handler's problem. [from-docs] [verified-by-code,
  source/src/include/catalog/pg_language.h — `lanpltrusted`]

## Reference implementations the chapter points at

- `src/test/modules/plsample` — minimal worked C template for a new PL. [from-docs]
- `src/pl/` — the four in-tree PLs (plpgsql, plperl, plpython, pltcl). [from-docs]

## Links into corpus

- [[knowledge/issues/plpgsql.md]] — consumer-side: trusted-PL gate enforced
  exactly twice in `pl_handler.c`; EXECUTE has zero injection defense.
- [[knowledge/issues/plperl.md]] / [[knowledge/issues/plpython.md]] /
  [[knowledge/issues/pltcl.md]] — the cross-PL trust-gate ranking (Tcl Safe ≥
  Perl opcode-mask > plpgsql nothing; plpython untrusted-only).
- [[knowledge/idioms/fmgr.md]] — the `fn_oid`/`fn_extra`/`fn_mcxt` mechanics this
  chapter relies on.
- [[knowledge/idioms/catalog-conventions.md]] — `pg_language` row layout.
- fmgr-and-spi + error-handling skills.

## Gaps / follow-ups

- `src/backend/commands/proclang.c` (`CreateProceduralLanguage`,
  `CheckFunctionValidatorAccess`) has no per-file corpus doc yet; the
  `[verified-by-code]` cites above are pointer-level. A read would let
  `knowledge/issues/plpgsql.md`'s "gate enforced twice" claim cite both the
  handler-side AND this catalog-side check.
