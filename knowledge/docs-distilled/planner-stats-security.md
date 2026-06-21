---
source_url: https://www.postgresql.org/docs/current/planner-stats-security.html
fetched_at: 2026-06-20T19:55:00Z
anchor_sha: dc5116780846
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Planner Statistics and Security (How the Planner Uses Statistics §70.2)

The "selectivity estimation can leak other users' data" leaf of the planner-stats
chapter. The threat: the planner, while estimating selectivity, **executes a
user-provided operator on values pulled from `pg_statistic`** (e.g. comparing a
query constant to a stored most-common-value). A malicious or careless operator
implementation can exfiltrate those stored values — which may belong to a table
the querying user cannot read.

## The leak mechanism

- Selectivity estimators run a real operator (the one in the query, or a related
  one) against stored statistics to decide, e.g., whether a stored MCV matches a
  query constant — this requires invoking the `=` operator on the stored value.
  [from-docs]
- An operator can **leak its operands** by logging them, writing them to another
  table, or surfacing them in an error message — so executing it on another
  user's statistics is a real exfiltration channel. [from-docs]

## The defenses

- **`pg_statistic` is superuser-only.** Ordinary users cannot read the catalog
  directly, so they can't learn other users' table contents from it. [from-docs]
  (The user-facing `pg_stats` view exposes a privilege-filtered subset; this
  section frames the protection around the underlying `pg_statistic` table.)
- **The leakproof-or-privilege rule:** all built-in selectivity estimators
  require, before using statistics that need operator execution, that the current
  user EITHER has `SELECT` on the table/columns involved, OR the operator is
  marked **`LEAKPROOF`**. If neither holds, the estimator **behaves as if no
  statistics exist** and the planner falls back to default assumptions. [from-docs]
- **Finding leakproof operators:** psql's `\do+` meta-command shows which
  operators are marked leakproof. [from-docs]

## Scope of the restriction

- The rule applies **only** when the planner would need to **execute a
  user-defined operator** on `pg_statistic` values. **Generic** statistics —
  null fraction, number of distinct values — carry no operator execution and are
  usable **regardless of access privileges**. [from-docs]
- **Security-barrier views / RLS interaction:** when a user reads through a
  security-barrier view, the planner may want statistics from an underlying
  table the user can't access. Those stats are used **only if the operator is
  leakproof**; otherwise they're silently skipped. There is **no direct feedback**
  — the only symptom is a possibly-suboptimal plan. [from-docs]
- **Extension authors:** third-party selectivity-estimation functions that touch
  statistics with user-defined operators must follow the same rules; the doc
  defers to the PostgreSQL source for the pattern. [from-docs]

## Why it matters for a reviewer

- A patch that adds a new selectivity estimator touching `pg_statistic` is a
  **security-relevant** change: it must honor the same `SELECT`-privilege /
  `LEAKPROOF` gate, or it reopens the leak channel. This is exactly the class of
  "looks like a perf tweak, is actually a data-leak" review reflex. [inferred]
- Marking an operator `LEAKPROOF` is a **trust assertion**: it tells the planner
  the operator is safe to run on data the caller can't see. Mismarking it is the
  bug. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/planner-stats.md` — the parent chapter (how
  estimation works); this leaf is its security caveat.
- `knowledge/docs-distilled/row-estimation-examples.md`,
  `knowledge/docs-distilled/multivariate-statistics-examples.md` — the
  estimation machinery the leak rides on.
- `knowledge/idioms/analyze-mcv-histogram-correlation.md`,
  `knowledge/idioms/extended-statistics-statext.md` — what's stored in
  `pg_statistic` / `pg_statistic_ext_data`.
- `knowledge/idioms/security-barrier-views.md`,
  `knowledge/idioms/row-security-policy-application.md` — the RLS / barrier
  mechanism whose statistics-side hole this closes.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/planner-stats-security.html (PG18).
- `LEAKPROOF` semantics and `pg_proc.proleakproof` are corroborated across the
  RLS corpus; verify `pg_statistic`/`pg_stats` privilege code against anchor
  `dc5116780846` before quoting line numbers in a plan.
