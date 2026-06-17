---
source_url: https://www.postgresql.org/docs/current/rules-update.html
chapter: "41.4 Rules on INSERT, UPDATE, and DELETE (rules-update)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Rules on INSERT/UPDATE/DELETE — rules-update

How the rewriter (`rewriteHandler.c`) turns a data-modifying query into zero or
more query trees via `pg_rewrite` rule templates. The mirror image of view
(SELECT) rules, but with different firing order and the `NEW`/`OLD`
pseudo-relations. Pairs with [[knowledge/docs-distilled/querytree.md]].

## Non-obvious claims

- **Rules don't mutate the query tree in place — they emit zero or more *new*
  trees and may discard the original.** This is the structural difference from
  triggers (which run at execution time on the unchanged plan). [from-docs
  rules-update]
- **`pg_rewrite` stores only *templates*.** The action query trees reference
  `NEW`/`OLD` range-table entries that must be substituted before use.
  [from-docs]
- **`NEW`/`OLD` substitution rules:** a `NEW` reference is replaced by the
  matching target-list entry from the original query; if absent, `NEW` becomes
  `OLD` (for UPDATE) or null (for INSERT). `OLD` references are replaced by
  references to the result relation. [from-docs]
- **Firing order flips by command:** for `ON INSERT`, the original query (unless
  `INSTEAD`-suppressed) runs **before** rule actions; for `ON UPDATE`/`ON
  DELETE`, the original runs **after** the rule actions. A genuinely
  counterintuitive asymmetry. [from-docs]
- **`DO ALSO` (one action, no qual) → 2 trees** (action + original). **`DO
  INSTEAD` → 1 or 2** depending on qualification, never "action + original"
  unnegated. [from-docs]
- **Qualified `INSTEAD` splits into two trees:** (1) action + (rule qual AND
  original qual), (2) the **original query with the *negated* rule qual added**
  — so rows not matching the rule still get the original behavior. Qualified
  `ALSO` instead ANDs both quals onto the action tree. [from-docs]
- **Recursion is detected and errored.** Generated action trees are fed back
  through the rewriter; a rule whose action has the *same* command type AND
  result relation as the rule itself would loop forever — PG detects and
  reports this rather than hanging. [from-docs]
- **View (SELECT) rules are applied *after* update rules**, on the produced
  trees; view rewriting can't introduce new update actions, so update rules
  needn't re-run on its output. [from-docs]
- **Volatile functions are a footgun:** rule expansion can cause a volatile
  function in the original query to be **executed more times than expected**.
  [from-docs]
- **`RETURNING` in a rule references the pseudo-relation RTEs** (`OLD`/`NEW` as
  extra range-table entries), not the literal old/new row versions in the
  result relation. [from-docs]

## Links into corpus

- The rewriter that performs this expansion:
  [[knowledge/files/src/backend/rewrite/rewriteHandler.c.md]].
- The query-tree representation rules operate on:
  [[knowledge/docs-distilled/querytree.md]] and
  [[knowledge/docs-distilled/rule-system.md]].
- The SELECT-rule (view) counterpart:
  [[knowledge/docs-distilled/rules-views.md]].
- How command status survives rewriting:
  [[knowledge/docs-distilled/rules-status.md]].

## Caveats / verification

- All claims `[from-docs rules-update]`. The substitution + qual-negation +
  recursion-detection logic is in
  `source/src/backend/rewrite/rewriteHandler.c` (`rewriteTargetView`,
  `ApplyRetrieveRule`, `fireRules`) at anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
