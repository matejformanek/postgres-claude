# Queue: pg-quality-auditor — issue-register triage side

Format: `[status] <subsystem>.md <file:line> | <type>/<severity> | seeded=<YYYY-MM-DD>`
Seed rule: auto-seed from `knowledge/issues/<subsystem>.md` registers — any
`open` row whose **Date** column is older than 30 days. Refilled when empty.

ISSUE mode (day-of-year mod 3 == 2, or a rotation target) pops the head
`[pending]` row, re-fetches the cited `<path>:<line>` at the anchor SHA, and
triages: still-present → bump the register Status to `open · triaged <date>`;
fixed-upstream → mark `landed` + `git log -S`; reproducer drifted → patch the
file:line + inline tag.

## Activation note (2026-07-03, pg-quality-auditor)

The 2026-06-13 seeding note predicted this queue would stay structurally
empty until ~2026-07-02, when the earliest `open` register cluster
(dated 2026-06-02) crosses the 30-day staleness threshold. **That
threshold is now crossed** (today 2026-07-03). First activation:
**635** `open` rows dated ≤2026-06-03 are eligible; **~159** of them
carry a concrete `file:line` cite (the drift-checkable subset). Rather
than dump all 635 into this append-only file, the queue seeds
incrementally — this run triaged the 19 line-cited `pg_upgrade` rows
(a coherent Phase-D data-leak-relevant register) and staged the next
security-relevant registers (`pg_rewind`, `pg_basebackup`,
`pg_amcheck`) as `[pending]`. Future runs pop the pending head and
refill from the remaining registers (`common`, `libpq`, `psql`,
`utils`, `utils-adt`, `catalog`, `initdb`, `pg_dump`) when this
drains.

Seed-loop convention (established this run): a row triaged `still-present`
gets `[done:<date>]` here AND `open · triaged <date>` in its register
row; the Status keeps the word `open` so the 30-day Date-based
re-seed still finds it on the next cycle, but the `triaged` stamp lets
a future seed skip rows triaged within the last 30 days (prioritize
least-recently-triaged).

## Entries

[done:2026-07-03] pg_upgrade.md check.c:1117 | trust-boundary/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md exec.c:187 | shell-injection/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md option.c:429 | trust-boundary/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md pg_upgrade.c:749 | shell-injection/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md util.c:189 | secret-scrub/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md check.c:998 | correctness/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md controldata.c:592 | correctness/likely | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md info.c:850 | correctness/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md multixact_read_v18.c:256 | correctness/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md option.c:82 | correctness/maybe | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md exec.c:119 | info-disclosure/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md info.c:597 | undocumented-invariant/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md check.c:113 | stale-todo/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md option.c:27 | stale-todo/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md pg_upgrade.c:56 | stale-todo/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md pg_upgrade.h:439 | stale-todo/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md check.c:1879 | dead-code/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md option.c:286 | dead-code/nit | still-present@b542d5566705
[done:2026-07-03] pg_upgrade.md relfilenumber.c:308 | dead-code/nit | still-present@b542d5566705

[done:2026-07-04] pg_rewind.md file_ops.c:65,225,201,285,302,268 | trust-boundary/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md file_ops.c:285 | trust-boundary/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md file_ops.c:478 | path-traversal/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md pg_rewind.c | trust-boundary/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md parsexlog.c:324 | trust-boundary/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md filemap.c:846 | stale-todo/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md libpq_source.c:562 | trust-boundary/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md libpq_source.c:583 | trust-boundary/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md pg_rewind.c:531 | state-transition/likely | drifted+2@a5422fe3bd7e (was :529; re-anchored register+per-file doc)
[done:2026-07-04] pg_rewind.md pg_rewind.c:748 | stale-todo/nit | drifted+2@a5422fe3bd7e (was :746)
[done:2026-07-04] pg_rewind.md filemap.c:112 | undocumented-invariant/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md filemap.c:761 | dead-code/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md filemap.c:588 | undocumented-invariant/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md libpq_source.c:363 | undocumented-invariant/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_rewind.md pg_rewind.c:1000 | dead-code/nit | drifted+2@a5422fe3bd7e (was :998)
[done:2026-07-04] pg_basebackup.md pg_basebackup.c:1145-1150 | trust-boundary/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_basebackup.md pg_basebackup.c:1357 | trust-boundary/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_basebackup.md streamutil.c:367-394 | trust-boundary/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_basebackup.md pg_basebackup.c:2858 | path-traversal/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_basebackup.md pg_createsubscriber.c:1460,214,47-48 | secret-scrub/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_basebackup.md pg_recvlogical.c:582 | wire-protocol/maybe | drifted+4@a5422fe3bd7e (was :578; re-anchored register+per-file doc)
[done:2026-07-04] pg_basebackup.md receivelog.c:541 | stale-todo/nit | mis-cite-fixed@a5422fe3bd7e (was pg_basebackup.c:542; FIXME actually in receivelog.c:541 — re-anchored register+both per-file docs)
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:585-594 | state-transition/likely | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:207,1719 | state-transition/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:547-564 | state-transition/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:1062-1083,1088-1097,1156-1166,1305 | info-disclosure/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:719-723,816 | correctness/maybe | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:978-980 | undocumented-invariant/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:1086 | undocumented-invariant/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:677-683 | correctness/nit | still-present@a5422fe3bd7e
[done:2026-07-04] pg_amcheck.md pg_amcheck.c:2167,2208 | dead-code/nit | still-present@a5422fe3bd7e

## Refill 2026-07-04 (pg-quality-auditor) — libpq register, 15 line-cited open rows

[pending] libpq.md fe-auth.c:941 | correctness/likely | seeded=2026-07-04
[pending] libpq.md fe-auth.c:1219 | correctness/likely | seeded=2026-07-04
[pending] libpq.md pqmq.c:255-263 | question/maybe | seeded=2026-07-04
[pending] libpq.md pqmq.c:205-207 | correctness/nit | seeded=2026-07-04
[pending] libpq.md pqmq.c:172-194 | undocumented-invariant/nit | seeded=2026-07-04
[pending] libpq.md pqformat.c:413-441 | correctness/maybe | seeded=2026-07-04
[pending] libpq.md pqformat.c:511-550 | correctness/maybe | seeded=2026-07-04
[pending] libpq.md pqformat.c:97 | undocumented-invariant/nit | seeded=2026-07-04
[pending] libpq.md pqexpbuffer.c:213 | correctness/maybe | seeded=2026-07-04
[pending] libpq.md libpq-be-fe.h:244-257 | correctness/maybe | seeded=2026-07-04
[pending] libpq.md libpq-be-fe.h:69-119 | undocumented-invariant/maybe | seeded=2026-07-04
[pending] libpq.md pqformat.h:99-124 | undocumented-invariant/maybe | seeded=2026-07-04
[pending] libpq.md pqformat.h:170-187 | stale-todo/nit | seeded=2026-07-04
[pending] libpq.md hba.h:117 | leak/maybe | seeded=2026-07-04
[pending] libpq.md hba.h:42 | undocumented-invariant/maybe | seeded=2026-07-04
