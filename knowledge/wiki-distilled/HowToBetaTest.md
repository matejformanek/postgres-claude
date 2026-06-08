---
source_url: https://wiki.postgresql.org/wiki/HowToBetaTest
fetched_at: 2026-06-08T20:57:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: a contributor/tester helping shake out a beta — the durable testing taxonomy, not the dated PG-9.6 feature list
---

# Wiki distilled — HowToBetaTest

The page's version-specific content is dated (PG 9.6-era feature callouts),
but its **testing-method taxonomy and "what makes a useful beta bug report"
are durable**. Distilled to keep the lasting parts and flag the stale parts.

## Durable testing taxonomy (the lasting value)

- **Install & upgrade testing** — build with your real configure/contrib set;
  verify install, then **upgrade a populated cluster** (dump/restore *and*
  `pg_upgrade`) into the beta. [from-wiki]
- **Application compatibility** — run your app's existing test/regression
  suites against the beta; exercise popular ORMs/drivers (download the latest
  driver and run *its* regression tests against new syntax/features). [from-wiki]
- **Performance / benchmark** — repeatable runs on an isolated box, compared
  against the prior major version (pgbench or your own workload) across the
  alpha→beta cycle. [from-wiki]
- **Feature-integration** — combine multiple new features, and new-with-legacy
  features, and check the docs match observed behavior. [from-wiki]
- **Custom / stress workloads** — operations known to strain resources (big
  joins, ETL) or specifically targeted by the release's changes. [from-wiki]

## Reporting (durable)

- **`pgsql-bugs` is the preferred list for a suspected beta bug**; use
  `pgsql-hackers` only if you're already in the development discussion;
  `pgsql-general` for general testing reports. **No subscription needed to
  post**, or use the Bug Reporting Form. [from-wiki]
  [cross: knowledge/wiki-distilled/Mailing_Lists.md]
- **A useful report includes:** PG release/build, platform, install method, the
  exact test procedure, whether it failed, full results + error text, and
  enough to reproduce. **"Script the test so you can reproduce it"** is the
  single highest-leverage rule. **Follow up** through the cycle. [from-wiki]

## Beta-specific caveat (durable, easy to forget)

- **Catalog/on-disk format can change between betas** — a `CATALOG_VERSION_NO`
  bump between beta1 and beta2 means **you must `initdb` again**; you cannot
  pg_upgrade or binary-upgrade across a catversion change within the beta
  series. [inferred, from-wiki + cross: knowledge/wiki-distilled/Committing_checklist.md]

## Stale parts (do NOT quote as current)

- The page's enumerated "new features to test" are **PG 9.6-era** and must not
  be presented as the current release's feature set — for the live release, read
  the current beta's release notes instead. [from-wiki, dated]

## Links into corpus
- [[knowledge/wiki-distilled/Mailing_Lists.md]] — pgsql-bugs vs -hackers vs -general for the report.
- [[knowledge/wiki-distilled/CommitFest.md]] — Alpha/Beta come out of the CF cycle.
- [[knowledge/wiki-distilled/Committing_checklist.md]] — the version-stamp matrix behind the initdb-between-betas rule.
- [[knowledge/docs-distilled/bki.md]] — CATALOG_VERSION_NO / catversion mechanics.

## Caveats
- This is a low-churn but old page; treat its taxonomy as durable and its
  feature lists as historical. Re-confirm the report-destination URL/list on the
  live site. [inferred]
