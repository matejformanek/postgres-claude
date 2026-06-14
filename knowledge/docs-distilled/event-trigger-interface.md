---
source_url: https://www.postgresql.org/docs/current/event-trigger-interface.html
fetched_at: 2026-06-13T19:52:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Writing Event Trigger Functions in C (internals ch. 40.4)

The C ABI for event triggers (DDL-level hooks), parallel to row-level trigger
functions but with their own context struct and event set. Pairs with
`trigger-interface.md` (row triggers) and the `fmgr` idiom.

## Non-obvious claims

- **fmgr v1, no SQL args:** an event trigger function uses the version-1 function
  manager interface, declared to **return `event_trigger`**, and receives **no
  normal arguments** — only `fcinfo->context` pointing at an `EventTriggerData`. [from-docs]
- **Guard with `CALLED_AS_EVENT_TRIGGER(fcinfo)`** before casting the context; it
  expands to
  `((fcinfo)->context != NULL && IsA((fcinfo)->context, EventTriggerData))`. [from-docs]
- **Return a NULL pointer** from the function (i.e. `PG_RETURN_NULL()`-style null
  *pointer*) — do **not** set `isNull` true; the returned value is ignored. [from-docs]
- **`EventTriggerData`** (in `commands/event_trigger.h`): `NodeTag type` (always
  `T_EventTriggerData`), `const char *event`, `Node *parsetree`, `CommandTag tag`.
  [from-docs]
- **Event names** carried in `->event`: `"ddl_command_start"`, `"ddl_command_end"`,
  `"sql_drop"`, `"table_rewrite"`, `"login"` (the last is the PG17 login event). [from-docs]
- **🔑 The structure (and everything it points at, including `parsetree`) is
  read-only** — must not be altered. The parse-tree representation is internal and
  "subject to change without notice," so don't build a stable API on its shape. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/commands/event_trigger.c.md]] (if present;
  the firing machinery + `EventTriggerData` construction).
- Idiom: [[knowledge/idioms/fmgr.md]] (v1 calling convention, `CALLED_AS_*`
  guard pattern shared with row triggers).
- Siblings: `knowledge/docs-distilled/trigger-interface.md` (row-level analog),
  `knowledge/docs-distilled/trigger-datachanges.md`.
- Code anchor [unverified — not line-pinned this run]:
  `source/src/include/commands/event_trigger.h` (`EventTriggerData`,
  `CALLED_AS_EVENT_TRIGGER`).
