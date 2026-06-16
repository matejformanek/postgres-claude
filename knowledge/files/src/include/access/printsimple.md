# `access/printsimple.h` — type-less tuple printer for debugging

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/printsimple.h`)

## Role
A bare-bones `DestReceiver` for tcop debugging that prints tuples without
going through fmgr's type output functions. Used for queries that run
before fmgr is fully initialized (the parallel walker, early bootstrap,
some single-user mode paths).

## Public API
- `printsimple(TupleTableSlot *slot, DestReceiver *self)` (`printsimple.h:19`)
  — the `DestReceiver`'s `receiveSlot` method.
- `printsimple_startup(DestReceiver *self, int operation, TupleDesc tupdesc)`
  (`printsimple.h:20`).

## Invariants
- Supports only a small fixed set of column types (text, int4, int8, oid,
  …) — verified by reading `src/backend/access/common/printsimple.c`.
  Anything else triggers `elog`. `[verified-by-code]`.
- Output format is whitespace-separated values with no quoting; not
  suitable for general result delivery. `[from-comment]` in printsimple.c.

## Notable internals
- A frontend-protocol detail: this is a `DestReceiver` plugged into the
  `T_None` / "internal" path; it does not produce CommandComplete or
  RowDescription messages in the way `printtup` does (see `printtup.h`).

## Trust-boundary / Phase D surface

**[ISSUE-defense-in-depth: limited type support means future use will
silently elog (informational)]** — Extending printsimple to a new type
requires explicit code change; well-scoped, but a contrib using this dest
will see errors on type drift. `printsimple.h:19`-`20`.

## Cross-refs
- `access/printtup.h` (sibling, not in this slice) — full type-aware printer.
- `tcop/dest.h` — `DestReceiver` interface.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-defense-in-depth: closed type set, elog on unknown (informational)]**
   — `printsimple.h:19`.
