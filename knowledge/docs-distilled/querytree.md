---
source_url: https://www.postgresql.org/docs/current/querytree.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — The Query Tree

The shape of the `Query` node that flows parser → rewriter → planner. Reading
this first makes `parsenodes.h` and the rewrite/planner per-file docs legible.
The rule system sits between parser and planner and rewrites these trees.

## What it is

- A query tree is the **decomposed internal form of one SQL statement**, with
  each clause stored as a separate field rather than as text. The rewriter takes
  parser-produced query trees + the rules in **`pg_rewrite`** and emits **zero or
  more** query trees. [from-docs]
- You can dump the stages with the debug GUCs **`debug_print_parse`**,
  **`debug_print_rewritten`**, **`debug_print_plan`** (and
  `debug_pretty_print`). [from-docs]
  [verified-by-code, via [[knowledge/files/src/include/nodes/parsenodes.h.md]]]

## The parts

- **Command type** — a simple enum: `SELECT` / `INSERT` / `UPDATE` / `DELETE`
  (/ `MERGE` / `UTILITY`). [from-docs]
- **Range table** — the list of relations the query touches (roughly the `FROM`
  entries plus result/aux relations). Entries are **referenced by *number*, not
  by name**, which is what lets rule-merging tolerate duplicate names. [from-docs]
- **Result relation** — an **index into the range table** naming where rows are
  written. **Empty for `SELECT`**; set for INSERT/UPDATE/DELETE. [from-docs]
- **Target list** — the list of output expressions: [from-docs]
  - SELECT: the items between `SELECT` and `FROM` (`*` already expanded by the parser).
  - INSERT: the `VALUES`/`SELECT` expressions; rewrite adds entries for
    defaulted columns.
  - UPDATE: the `SET col = expr` expressions; the planner copies old values for
    untouched columns and adds a **CTID** (or whole-row var for views) so the
    executor can find the physical row.
  - DELETE: no normal target list — just the planner-added CTID/whole-row entry.
- **Qualification** — the boolean `WHERE`/`HAVING` expression deciding which rows
  the operation applies to. [from-docs]
- **Join tree** — the structure of `FROM`: a flat list for simple queries, a
  nested `JoinExpr` shape for explicit (esp. outer) joins; `ON`/`USING`
  restrictions hang as quals on join nodes, and the **top-level `WHERE` is stored
  as the qualification on the top join-tree node** (so FROM+WHERE are unified
  here). [from-docs]
- **Others** — `ORDER BY`, `GROUP BY`, etc. are present but peripheral to rule
  processing. [from-docs]

## Why the unified form is powerful

Because view definitions get inlined into the *same* query tree (via the rule
system), the planner sees every table to scan, every join relationship, and both
view-supplied and user-supplied quals in one structure — enabling whole-query
optimization across views. [from-docs]
[cross: [[knowledge/docs-distilled/rules-views.md]]]

## Links into corpus
- [[knowledge/subsystems/parser-and-rewrite.md]] — parse-analyze → rewrite synthesis.
- [[knowledge/files/src/include/nodes/parsenodes.h.md]] — the actual `Query` struct fields.
- [[knowledge/files/src/backend/rewrite/rewriteHandler.c.md]] — where range-table/view inlining happens.
- [[knowledge/architecture/query-lifecycle.md]] — the parse→rewrite→plan→execute arc.
- Skill: `parser-and-nodes` — adding/altering Node types that ride this tree.

## Gaps / follow-ups
- Field-exact names (`Query.rtable`, `resultRelation`, `targetList`,
  `jointree`, `jointree->quals`) live in `parsenodes.h`; this doc keeps the
  doc-level part names, cross-check the header before coding.
