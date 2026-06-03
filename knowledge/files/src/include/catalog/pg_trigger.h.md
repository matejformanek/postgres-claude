# pg_trigger.h

- **Source path:** `source/src/include/catalog/pg_trigger.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "trigger" system catalog (`pg_trigger`) — one row per trigger (including system-generated constraint triggers), holding the firing function, BEFORE/AFTER/INSTEAD timing, ROW/STATEMENT level, event mask (INSERT/UPDATE/DELETE/TRUNCATE), constraint linkage, transition-table names, and WHEN qual. [from-comment]

## Catalog definition

- `CATALOG(pg_trigger, 2620, TriggerRelationId)` — per-database. [verified-by-code]
- `FormData_pg_trigger` typedef; pointer alias `Form_pg_trigger`. [verified-by-code]
- `DECLARE_TOAST(pg_trigger, 2336, 2337)`. [verified-by-code]
- Indexes: non-unique on `tgconstraint` (2699); UNIQUE on `(tgrelid, tgname)` (2701); PKEY on `oid` (2702). [verified-by-code]
- `DECLARE_ARRAY_FOREIGN_KEY((tgrelid, tgattr), pg_attribute, (attrelid, attnum))`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| tgrelid | Oid | BKI_LOOKUP | pg_class |
| tgparentid | Oid | BKI_LOOKUP_OPT | pg_trigger |
| tgname | NameData | — | — |
| tgfoid | Oid | BKI_LOOKUP | pg_proc |
| tgtype | int16 | — | — (bitmask, see macros) |
| tgenabled | char | — | — |
| tgisinternal | bool | — | — |
| tgconstrrelid | Oid | BKI_LOOKUP_OPT | pg_class |
| tgconstrindid | Oid | BKI_LOOKUP_OPT | pg_class |
| tgconstraint | Oid | BKI_LOOKUP_OPT | pg_constraint |
| tgdeferrable | bool | — | — |
| tginitdeferred | bool | — | — |
| tgnargs | int16 | — | — |
| tgattr | int2vector | BKI_FORCE_NOT_NULL | — (array FK to pg_attribute) |
| tgargs | bytea | BKI_FORCE_NOT_NULL (varlena) | — |
| tgqual | pg_node_tree | (varlena, nullable) | — |
| tgoldtable | NameData | (varlena, nullable) | — |
| tgnewtable | NameData | (varlena, nullable) | — |

## Key declarations beyond FormData

- `tgtype` bit positions (**on-disk values** — these bits are read back from the catalog):
  - `TRIGGER_TYPE_ROW       (1<<0)` — 0 means STATEMENT.
  - `TRIGGER_TYPE_BEFORE    (1<<1)`
  - `TRIGGER_TYPE_INSERT    (1<<2)`
  - `TRIGGER_TYPE_DELETE    (1<<3)`
  - `TRIGGER_TYPE_UPDATE    (1<<4)`
  - `TRIGGER_TYPE_TRUNCATE  (1<<5)`
  - `TRIGGER_TYPE_INSTEAD   (1<<6)` — non-adjacent to BEFORE within `TRIGGER_TYPE_TIMING_MASK`. [verified-by-code]
- Masks: `TRIGGER_TYPE_LEVEL_MASK`, `TRIGGER_TYPE_TIMING_MASK`, `TRIGGER_TYPE_EVENT_MASK`. [verified-by-code]
- Setter/getter macros: `TRIGGER_CLEAR_TYPE`, `TRIGGER_SETT_{ROW,STATEMENT,BEFORE,AFTER,INSTEAD,INSERT,DELETE,UPDATE,TRUNCATE}`, `TRIGGER_FOR_{ROW,BEFORE,AFTER,INSTEAD,INSERT,DELETE,UPDATE,TRUNCATE}`, and `TRIGGER_TYPE_MATCHES(type, level, timing, event)`. [verified-by-code]
- `TRIGGER_USES_TRANSITION_TABLE(namepointer)` — non-NULL pointer test. [verified-by-code]
- **`tgenabled` is a `char` accepting `'O'` (origin/default), `'D'` (disabled), `'R'` (replica), `'A'` (always)** — the canonical home of the `session_replication_role` character constants used by both pg_trigger AND pg_rewrite, but the header does not define named macros for them. [from-comment]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related per-file docs: `pg_rewrite.h.md` (shares `tgenabled`/`ev_enabled` char codes).
- Related backend: `source/src/backend/commands/trigger.c`, `source/src/backend/commands/tablecmds.c`.

## Potential issues

- **[ISSUE-ONDISK-CONTRACT: tgtype bit assignment is an on-disk format]** `pg_trigger.h:97-103` — the seven `TRIGGER_TYPE_*` bit positions are stored verbatim in pg_trigger rows; renumbering or repurposing any bit silently corrupts every existing trigger row. Header documents the bits as `tgtype` payload but does not say "do not change these numbers". [verified-by-code]
- **[ISSUE-ONDISK-CONTRACT: tgenabled chars never given symbolic names]** `pg_trigger.h:47-48` — `tgenabled` is `char` and the four valid letters (`'O'`,`'D'`,`'R'`,`'A'`) are documented only in the column comment as "WRT session_replication_role". Other catalogs (pg_constraint.contype, etc.) follow the same chars-as-API pattern with named macros; this one does not. [verified-by-code]
- **[ISSUE-INV: TIMING_MASK bits are non-adjacent — comment warns but masks could trip up patches]** `pg_trigger.h:108-110` — `TRIGGER_TYPE_TIMING_MASK = BEFORE | INSTEAD`; AFTER is encoded as zero. Patches that add a new timing (e.g. statement-level INSTEAD) must respect that AFTER==0 is implicit. Header has the warning comment; flagging here for reviewers. [verified-by-code]

## Tally

`[verified-by-code]=14 [from-comment]=2`
