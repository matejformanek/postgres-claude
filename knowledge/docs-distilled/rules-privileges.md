---
source_url: https://www.postgresql.org/docs/current/rules-privileges.html
chapter: "41.5 Rules and Privileges (rules-privileges)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Rules and privileges — rules-privileges

Why views are a privilege-delegation tool: a rewritten query is checked against
the **rule/view owner's** privileges, not the invoker's — and why that needs
`security_barrier` + `LEAKPROOF` to be safe against row leakage.

## Non-obvious claims

- **Relations pulled in by a rule are checked against the *rule owner's*
  privileges, not the invoking user's.** This is the whole mechanism behind
  "grant SELECT on a view without granting on the underlying table." [from-docs
  rules-privileges]
- **Exception: `security_invoker` views** use the invoking user's privileges
  for their SELECT rules instead of the owner's. [from-docs]
- **Privilege checks are per-rule-level**, so chained views (a view over a
  view) each check at their own level — no privilege escalation, but legitimate
  layering works. [from-docs]
- **Without `security_barrier`, a cheap user-supplied function/operator in
  `WHERE` can run *before* the view's own qualification** and observe rows the
  user shouldn't see (the classic `tricky()`-emits-NOTICE leak). [from-docs]
- **`security_barrier` blocks that pushdown:** functions/operators aren't fed
  row values until after the view has filtered. [from-docs]
- **`LEAKPROOF` is the escape hatch:** only functions marked `LEAKPROOF` (and
  thus guaranteed not to leak via error or side effect) may be pushed down past
  a security barrier. [from-docs]
- **Index-scan consequence:** on a security-barrier view (or an RLS table), an
  index scan can't be chosen if the `WHERE` operator belongs to the index's
  operator family but its underlying function is **not** `LEAKPROOF` — a real
  plan-shape / performance cost. [from-docs]
- **`security_barrier` views can plan far worse** than plain views: the fastest
  plan is rejected whenever it would compromise security. [from-docs]
- **It is not a covert-channel guarantee:** users can still infer data via
  `EXPLAIN` plans, timing, or optimizer statistics; the barrier only stops
  direct value leakage into functions. [from-docs]

## Links into corpus

- The rewriter that attaches owner-privilege checks to rule-expanded RTEs:
  [[knowledge/files/src/backend/rewrite/rewriteHandler.c.md]].
- The data-modifying rule mechanics:
  [[knowledge/docs-distilled/rules-update.md]] and the view side
  [[knowledge/docs-distilled/rules-views.md]].
- The leakproof/qual-pushdown decision is the optimizer's; see the planner
  file docs under `knowledge/files/src/backend/optimizer/`.

## Caveats / verification

- All claims `[from-docs rules-privileges]`. `security_barrier` /
  `security_invoker` handling lives in
  `source/src/backend/rewrite/rewriteHandler.c` + the reloptions; the
  leakproof-pushdown gate is in the planner (`restrictinfo` / qual placement)
  at anchor `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
