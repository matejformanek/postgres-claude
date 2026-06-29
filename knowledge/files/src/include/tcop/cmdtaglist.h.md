# src/include/tcop/cmdtaglist.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 223 [verified-by-code]

## Role

X-macro file listing every `CMDTAG_*` (command tag) plus per-tag
flags. Command tags are the strings returned in `CommandComplete`
protocol messages (`SELECT 17`, `INSERT 0 5`, etc.) and the symbolic
values used in `pg_stat_activity.query_id` paths.

## Public API

- `PG_CMDTAG(symbol, text, event_trigger_ok, table_rewrite_ok,
  rowcount)` — invoked once per entry; consumer defines macro.
  Columns:
  - `symbol` — `CMDTAG_*` C enumerator.
  - `text` — wire string like `"ALTER TABLE"`.
  - `event_trigger_ok` — whether DDL of this kind can fire an
    event trigger (`pg_event_trigger`).
  - `table_rewrite_ok` — whether DDL can fire `table_rewrite`
    event trigger.
  - `rowcount` — whether COMPLETE message carries a row count
    (mostly DML).
- ~180 tags ranging from `CMDTAG_UNKNOWN` to
  `CMDTAG_WAIT`/`CMDTAG_VACUUM`/etc.

## Invariants

- INV-CMDTAG-NO-GUARD: header has **no include guard** —
  intentionally re-includable with different `PG_CMDTAG`
  expansions. Same pattern as `kwlist.h`.
- INV-CMDTAG-ALPHABETIC: entries MUST be alphabetized on the
  textual name; comment `:22-24` [from-comment] notes
  `GetCommandTagEnum()` does `bsearch` on this order. Manual
  edits that break order silently mis-resolve tags.
- INV-CMDTAG-FLAGS-COHERENT: a tag with `event_trigger_ok=true`
  must be a DDL command; the event-trigger fire machinery
  consults this column.
- INV-CMDTAG-ROWCOUNT-WIRE: tags with `rowcount=true` produce
  CommandComplete strings like `"INSERT 0 17"` (oid + count);
  changing this flag is a wire-protocol break for clients.

## Notable internals

- The cluster identification: this file is the **third X-macro
  site** in the corpus alongside `access/rmgrlist.h` (resource
  managers — A17 main) and `storage/lwlocklist.h` (lwlock IDs
  — A15). Common pattern: avoid duplicating list in C and
  header; consumer macro decides representation.
- Adding a command tag: append in alphabetic order, recompile.
  No catversion bump needed since tags are not persisted in
  catalog.

## Public consumers of this header

1. `tcop/cmdtag.c` — defines `PG_CMDTAG` to build the
   `CommandTagBehavior tag_behavior[]` lookup table AND the
   `CommandTag` enum.
2. `tcop/cmdtag.h` — declares the enum via different
   expansion.
3. `pg_dump`, `psql` — limited use for symbol-name display.

## Trust boundary / Phase D surface

- Pure data table; no direct trust boundary.
- **A11 echo (cleartext exposure indirect).** Command tags
  themselves don't carry parameters, so they don't leak
  literals. But event-trigger-firing on TAG=ALTER_USER /
  CREATE_ROLE etc. is the dispatch hook for an event-trigger
  function that DOES see the full statement via `tg_eventstr`
  — which CAN see the `PASSWORD '...'` text.
- **A8 echo (replication name-vs-oid).** Logical replication
  apply-side sets the `CMDTAG_*` for replayed DDL when
  custom DDL replication is in play; an attacker injecting
  a tag mismatch could confuse downstream event triggers.
- **PG18 additions.** Property-graph tags
  (`CMDTAG_CREATE_PROPERTY_GRAPH`,
  `CMDTAG_ALTER_PROPERTY_GRAPH`, etc.) appear in this list —
  new tags = new event-trigger surface.

## Cross-references

- `tcop/cmdtag.h` — `CommandTag` enum, `CommandTagBehavior`
  struct, `GetCommandTagEnum`, `GetCommandTagName`.
- `commands/event_trigger.h` — uses `event_trigger_ok` flag.
- `tcop/dest.h` — CommandComplete protocol message.
- A15 `storage/lwlocklist.h` + A17 `access/rmgrlist.h` —
  sibling X-macro pattern sites.

## Issues / drift

- `[ISSUE-DOC: alphabetic-order invariant relies on developer discipline; no CI lint reported (low)] — source/src/include/tcop/cmdtaglist.h:22-24`
- `[ISSUE-CODE: rowcount flag is wire-significant; changing TRUE→FALSE breaks libpq clients parsing CommandComplete; not flagged in header (low)] — source/src/include/tcop/cmdtaglist.h:26`
- `[ISSUE-TRUST: A11 echo — event-trigger handler sees full statement string including PASSWORD literals; this list is the dispatch table (medium)] — source/src/include/tcop/cmdtaglist.h:53-94`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new utility statement](../../../../scenarios/add-new-utility-statement.md)

<!-- scenarios:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
