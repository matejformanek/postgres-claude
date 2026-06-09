# `src/include/utils/reltrigger.md`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Defines `Trigger` and `TriggerDesc` structs cached in `RelationData`.
Split out from `commands/trigger.h` purely to avoid an include cycle
through `rel.h` [from-comment: lines 19-20].

## Public API

### `Trigger` [verified-by-code: lines 23-45]

Mirrors columns of `pg_trigger`: `tgoid`, `tgname`, `tgfoid` (function
OID), `tgtype` (bitmask), `tgenabled`, `tgisinternal`, `tgisclone`,
`tgconstrrelid`/`tgconstrindid`/`tgconstraint` (FK constraint
linkage), `tgdeferrable`, `tginitdeferred`, `tgnargs`+`tgargs[]`,
`tgnattr`+`tgattr[]` (UPDATE columns), `tgqual` (WHEN clause text),
`tgoldtable`/`tgnewtable` (transition table names for OLD/NEW
TABLE).

### `TriggerDesc` [verified-by-code: lines 47-79]

Array of `Trigger` plus 23 boolean flags pre-summarizing which
trigger kinds exist (`trig_insert_before_row`,
`trig_update_after_statement`, … `trig_delete_old_table`). These
flags let executor skip the array entirely when no relevant trigger
is present.

## Invariants

- **INV-NO-ROW-TRUNCATE** [from-comment: line 71] There are no
  row-level TRUNCATE triggers; only statement-level.
- **INV-TRANSITION-TABLES** [verified-by-code: lines 74-78] Per-kind
  flags `trig_insert_new_table`, `trig_update_old_table`,
  `trig_update_new_table`, `trig_delete_old_table` track whether
  *any* trigger requests the corresponding transition table — when
  set, the executor must build the tuplestore.

## Trust boundary (Phase D)

- `tgfoid` is the OID of a SQL-callable function that will be
  invoked during DML. Execution runs in the *table-owner's* security
  context when the trigger is `tgisinternal=0` (regular trigger);
  the actual SECURITY DEFINER / INVOKER semantics live in
  `pg_proc.prosecdef` and are enforced by fmgr — this header just
  caches the OID.
- `tgqual` is a node-tree string parsed at trigger-build time. A
  malformed value (only writable by superuser via direct
  `pg_trigger` UPDATE) could crash backend during trigger setup.
- `tgnewtable`/`tgoldtable` are the names registered via the ENR
  mechanism (`queryenvironment.h`) — they bypass schema ACL because
  they shadow the host relation's name inside the trigger function
  scope.

## Cross-refs

- `utils/rel.h` — `RelationData.trigdesc`.
- `commands/trigger.h` — the actual trigger API; pulls in this
  header.
- `utils/queryenvironment.h` — transition tables registered as ENRs.
- `catalog/pg_trigger.h` — source of truth.

## Issues

- [ISSUE-DOC: per-kind flag inventory is hand-maintained alongside
  the executor switch — adding a new event kind requires touching
  multiple sites; no checklist link (low)] — lines 56-78.
