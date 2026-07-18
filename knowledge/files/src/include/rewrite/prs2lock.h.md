# src/include/rewrite/prs2lock.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 46 [verified-by-code]

## Role

In-memory representation of **rewrite rules** loaded from `pg_rewrite`.
The name "prs2lock" is a historical fossil from POSTGRES Rule System
II — these used to be tied to ProductionRule "locks" in the old
RuleSystem. Today only the rewriter remains (the planner rules
machinery is gone).

## Public API

- `RewriteRule` (`:24-32`):
  - `Oid ruleId` — pg_rewrite OID.
  - `CmdType event` — INSERT / UPDATE / DELETE / SELECT.
  - `Node *qual` — WHERE-like qual for the rule.
  - `List *actions` — list of Query nodes the rule expands to.
  - `char enabled` — 'O' origin / 'D' disabled / 'A' always /
    'R' replica.
  - `bool isInstead` — INSTEAD vs ALSO.
- `RuleLock` (`:40-44`):
  - `int numLocks`, `RewriteRule **rules` — set of rules
    applicable to one relation.

## Invariants

- INV-RULELOCK-NAME-FOSSIL: header comment `:36-38` [from-comment]
  acknowledges "not really 'locks', the name is kept for
  historical reasons". Refactoring is folklore-blocked.
- INV-RULE-RELCACHE-CACHED: `RuleLock *rd_rules` lives on the
  `RelationData` in relcache. Invalidated on pg_rewrite catalog
  change.
- INV-RULE-ENABLED-CHAR: `enabled` field semantics borrowed from
  `pg_rewrite.ev_enabled` — same SET SESSION_REPLICATION_ROLE
  interaction as triggers.
- INV-RULE-ACTIONS-LIST-OF-QUERY: each entry in `actions` is a
  fully parse-analyzed `Query`, stored in `pg_rewrite.ev_action`
  as a serialized node tree. Deserialized via
  `stringToNode` (A14 surface).

## Notable internals

- The classic INSTEAD-OF view-update support: a SELECT rule on
  a view rewrites every reference to that view as an inline
  subquery of `actions[0]`.
- Rule firing in `rewriteHandler.c` happens BEFORE planning,
  AFTER parse-analysis.

## Trust boundary / Phase D surface

- **A14 echo — pg_rewrite.ev_action deserialization.**
  Loading a relation with rules pulls the serialized node tree
  through `stringToNode`. A corrupt pg_rewrite row (manual
  catalog poke, replication of a malicious upstream) could
  crash the rewriter via crafted node tags.
- **A7 ruleutils security-clause loss echo.** The rewriter
  expands rules and views; an RLS qual on a referenced table
  must propagate into the expanded actions. Bugs here are the
  classic "view bypasses RLS" issue.
- **`isInstead` rule + `qual=NULL`.** An ALWAYS-INSTEAD rule
  with no qual replaces the original statement entirely. A
  user with WRITE on a view but not the underlying table can
  be granted write access via an INSTEAD-OF UPDATE rule —
  whether RLS on the underlying table still applies is the
  classic boundary.
- **`enabled='R'` (replica)** is the only mode that fires
  during logical-replication apply (A8 echo). A
  misconfigured replica-mode INSTEAD rule on a publication
  table can drop replicated rows silently.

## Cross-references

- `rewrite/rewriteHandler.h` — main entry point.
- `rewrite/rewriteDefine.h` — DDL: CREATE / DROP RULE.
- `catalog/pg_rewrite.h` — catalog definition.
- `utils/relcache.h` — `RelationData.rd_rules`.
- `nodes/parsenodes.h` — `CmdType`, `Query`.
- A7 / A8 phase-D notes.

## Issues / drift

- `[ISSUE-DOC: "RuleLock" name is misleading; historical fossil noted in comment but field naming still confuses new readers (low)] — source/src/include/rewrite/prs2lock.h:36-38`
- `[ISSUE-TRUST: A14 echo — pg_rewrite.ev_action is a node-tree string deserialized by readfuncs; hostile catalog content surface (medium)] — source/src/include/rewrite/prs2lock.h:24-32`
- `[ISSUE-TRUST: enabled='R' replica-mode rules fire during logical apply; can silently DROP rows or rewrite to side-effecting query (medium)] — source/src/include/rewrite/prs2lock.h:30`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
