---
source_url: https://www.postgresql.org/docs/current/rules-views.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Views and the Rule System

The single most clarifying fact about PG views: **a view is a relation with an
`ON SELECT DO INSTEAD` rewrite rule**, not a special object kind. The rewriter
(`rewriteHandler.c`) inlines it into the query tree before planning.

## A view *is* a rule

- `CREATE VIEW v AS SELECT ...` is essentially: an empty, storage-less table `v`
  **plus** a rule named **`_RETURN`**: `CREATE RULE "_RETURN" AS ON SELECT TO v
  DO INSTEAD SELECT ...`. (You can't write that by hand — tables may not carry
  `ON SELECT` rules.) [from-docs]
- The rule action lives in **`pg_rewrite`**. [from-docs]
  [verified-by-code, via [[knowledge/files/src/include/catalog/pg_rewrite.h.md]]]

## How `ON SELECT` rules are special

- They apply to **every** query that references the view as the **final rewrite
  step**, even inside an INSERT/UPDATE/DELETE. [from-docs]
- They **modify the query tree in place** rather than producing a new tree, and
  are constrained to **exactly one action**, an **unconditional `INSTEAD
  SELECT`** — which is precisely what makes them behave like views and stay safe
  for ordinary users. [from-docs]

## Expansion mechanics

- The rewriter walks the range table, finds entries with rules, and **replaces a
  view RTE with a subquery RTE** holding the rule's action query tree — so
  `SELECT * FROM v` becomes `SELECT ... FROM (SELECT ... FROM base ...) v`. [from-docs]
- **Privileges are preserved** via two extra non-joining RTEs (`v old` / `v
  new`) carrying the original reference's access-permission info so the executor
  still checks the caller's rights. The rewriter **skips `old`/`new` when
  recursing**, preventing infinite expansion of nested views. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/rewrite/rewriteHandler.c.md]]]

## Why views are read-only by default

- Naively rewriting an UPDATE/DELETE target into a subquery RTE yields a result
  relation the executor can't write — hence the default error. Three escape
  hatches: [from-docs]
  1. **Auto-updatable views** — simple single-base-relation views are rewritten
     to act on the underlying table (conditions in the `CREATE VIEW` docs).
  2. **`INSTEAD OF` triggers** — the rewriter expands the view, adds a
     **`wholerow`** target entry (views have no CTID) to identify the row, and
     hands it to the trigger.
  3. **`INSTEAD` rules** — user rules rewrite INSERT/UPDATE/DELETE into
     operations on base tables.
- Rules are evaluated before triggers and auto-rewrite; if none apply and the
  view isn't auto-updatable, the write errors. [from-docs]

## The payoff

Inlining views into one query tree gives the planner the *whole* picture — all
base tables, joins, view-supplied quals and user quals together — so even
multi-view joins can be optimized as a single query. [from-docs]
[cross: [[knowledge/docs-distilled/querytree.md]]]

## Links into corpus
- [[knowledge/subsystems/parser-and-rewrite.md]] — the rewrite subsystem synthesis.
- [[knowledge/files/src/backend/rewrite/rewriteHandler.c.md]] — view/RTE inlining + `old`/`new` perm RTEs.
- [[knowledge/files/src/backend/rewrite/rewriteDefine.c.md]] — `_RETURN` rule creation for CREATE VIEW.
- [[knowledge/files/src/include/catalog/pg_rewrite.h.md]] — where rule actions are stored.
- [[knowledge/docs-distilled/querytree.md]] — the tree this rewrite operates on.
- Skill: `parser-and-nodes` — query-tree node handling around rewrite.

## Gaps / follow-ups
- `INSTEAD` rules on INSERT/UPDATE/DELETE (the non-view rule machinery) and rule
  recursion limits are a sibling chapter (`rules-update`), not distilled here.
- Auto-updatable-view eligibility rules live in the `CREATE VIEW` reference page.
