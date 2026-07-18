# pg_rewrite.h

- **Source path:** `source/src/include/catalog/pg_rewrite.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "rewrite rule" system catalog (`pg_rewrite`) — one row per CREATE RULE rule, holding the rule's event type, enable flag, INSTEAD flag, optional WHEN qualification, and the action query tree. Primary key is `(ev_class, rulename)` since Postgres 7.3. [from-comment]

## Catalog definition

- `CATALOG(pg_rewrite, 2618, RewriteRelationId)` — per-database. [verified-by-code]
- `FormData_pg_rewrite` typedef; pointer alias `Form_pg_rewrite`. [verified-by-code]
- `DECLARE_TOAST(pg_rewrite, 2838, 2839)` — `ev_action` (serialized Query tree) can be very large. [verified-by-code]
- Indexes: PKEY on `oid` (2692); UNIQUE on `(ev_class, rulename)` (2693). [verified-by-code]
- Syscache: `RULERELNAME`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| rulename | NameData | — | — |
| ev_class | Oid | BKI_LOOKUP | pg_class |
| ev_type | char | — | — |
| ev_enabled | char | — | — |
| is_instead | bool | — | — |
| ev_qual | pg_node_tree | BKI_FORCE_NOT_NULL (varlena) | — |
| ev_action | pg_node_tree | BKI_FORCE_NOT_NULL (varlena) | — |

## Key declarations beyond FormData

- None in this header. `ev_type` accepts single-char codes for the CMD_* family (`'1'` SELECT, `'2'` UPDATE, `'3'` INSERT, `'4'` DELETE), and `ev_enabled` accepts `'O'/'D'/'R'/'A'` matching `session_replication_role`. Those character literals are defined in `src/include/rewrite/prs2lock.h` and `src/include/catalog/pg_trigger.h` respectively, NOT here. [inferred]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related per-file docs: `pg_trigger.h.md` (shares the `'O'/'D'/'R'/'A'` enable-char convention).
- Related backend: `source/src/backend/rewrite/rewriteDefine.c`, `source/src/backend/rewrite/rewriteHandler.c`.

## Potential issues

- **[ISSUE-ONDISK-CONTRACT: ev_type / ev_enabled characters are on-disk values but defined out of file]** `pg_rewrite.h:39-40` — both `char` columns hold values whose meaning lives in *other* headers. A reader of pg_rewrite.h cannot tell what `ev_type = '2'` means without grep. The header should at minimum cross-reference where the codes are defined. [verified-by-code]

## Tally

`[verified-by-code]=10 [from-comment]=1 [inferred]=1`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/view-pushdown-via-rewriter.md](../../../../idioms/view-pushdown-via-rewriter.md)

- [idioms/node-types-and-lists.md](../../../../idioms/node-types-and-lists.md)