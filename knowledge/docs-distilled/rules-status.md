---
source_url: https://www.postgresql.org/docs/current/rules-status.html
chapter: "41.4 (cont.) Rules and Command Status (rules-status)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Rules and command status — rules-status

The subtle bit: when rules rewrite a query, which command tag (`INSERT 0 1`,
`UPDATE 3`, ...) does the client see? The answer drives a special case in the
rewriter + portal-run path (`pquery.c`).

## Non-obvious claims

- **The completion tag is `<cmdtype> <oid> <rows>`** (e.g. `INSERT 149592 1`);
  rule rewriting must decide what cmdtype/oid/rowcount to report when the
  executed tree(s) differ from what the user typed. [from-docs rules-status]
- **No unconditional `INSTEAD` rule → the original query runs and reports its
  status as usual.** [from-docs]
- **Conditional `INSTEAD` rules (but no unconditional) → the original still
  runs, but with the rules' qualifications *negated and ANDed* onto it.** That
  can reduce its processed row count, and the reported status changes
  accordingly. [from-docs]
- **Any unconditional `INSTEAD` rule → the original query is not executed at
  all,** so it can't supply the status. [from-docs]
- **The reported status then comes from the *last* `INSTEAD`-inserted query
  (conditional or not) whose command type matches the original.** [from-docs]
- **If no inserted query matches that requirement, the tag shows the original
  command type with zeroed row-count and OID.** [from-docs]
- **Programmer control via rule name:** because the *last-applied* matching
  `INSTEAD` rule sets the status, and rules fire in **alphabetical name
  order**, you make a specific rule win the status race by giving it the
  alphabetically last name among active rules. A genuinely non-obvious,
  load-bearing naming convention. [from-docs]

## Links into corpus

- Where the rewriter decides which tree carries the status:
  [[knowledge/files/src/backend/rewrite/rewriteHandler.c.md]].
- Where the portal computes and returns the completion tag:
  [[knowledge/files/src/backend/tcop/pquery.c.md]].
- The companion rule mechanics:
  [[knowledge/docs-distilled/rules-update.md]] and
  [[knowledge/docs-distilled/rule-system.md]].

## Caveats / verification

- All claims `[from-docs rules-status]`. The "last matching INSTEAD rule sets
  the tag, ties broken alphabetically" behavior is implemented across
  `source/src/backend/rewrite/rewriteHandler.c` (rule firing order) and the
  `QueryCompletion` plumbing in `source/src/backend/tcop/pquery.c` at anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
