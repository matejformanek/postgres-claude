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

[done:2026-07-07] libpq.md fe-auth.c:941 | correctness/likely | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md fe-auth.c:1219 | correctness/likely | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqmq.c:255-263 | question/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqmq.c:205-207 | correctness/nit | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqmq.c:172-194 | undocumented-invariant/nit | still-present@a8c2547eaac7 (range holds; +AmRepackWorker/PROCSIG_REPACK branch inserted since seed, pattern intact)
[done:2026-07-07] libpq.md pqformat.c:413-441 | correctness/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqformat.c:511-550 | correctness/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqformat.c:97 | undocumented-invariant/nit | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqexpbuffer.c:213 | correctness/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md libpq-be-fe.h:244-257 | correctness/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md libpq-be-fe.h:69-119 | undocumented-invariant/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqformat.h:99-124 | undocumented-invariant/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md pqformat.h:170-187 | stale-todo/nit | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md hba.h:117 | leak/maybe | still-present@a8c2547eaac7
[done:2026-07-07] libpq.md hba.h:42 | undocumented-invariant/maybe | still-present@a8c2547eaac7

## Refill 2026-07-07 (pg-quality-auditor) — common register, 21 line-cited open rows

libpq register fully drained this run (15 rows all still-present@a8c2547eaac7).
Next security-relevant frontend/shared register: `common` (src/common +
src/include/common) — the Phase D data-leak surface continues here (checksum,
manifest, compression, crypto, secret-scrub). All rows dated 2026-06-03, well
past the 30-day staleness threshold.

[done:2026-07-10] common.md md5_common.c:151,170 | secret-scrub/likely | still-present@d92e98340fcb
[done:2026-07-10] common.md blkreftable.c:595-601,652-655 | trust-boundary/likely | still-present@d92e98340fcb
[done:2026-07-10] common.md blkreftable.c:666-672 | dos/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md blkreftable.c:907 | trust-boundary/likely | still-present@d92e98340fcb
[done:2026-07-10] common.md parse_manifest.c:811-878 | trust-boundary/likely | still-present@d92e98340fcb
[done:2026-07-10] common.md checksum_helper.h:20-27 | trust-boundary/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md controldata_utils.c:209-252 | state-transition/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md pg_lzcompress.c:255-256 | undocumented-invariant/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md jsonapi.c:431-432,952-953,983-984 | dos/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md jsonapi.c:1400-1407 | dos/nit | still-present@d92e98340fcb
[done:2026-07-10] common.md archive.c:53-54 | trust-boundary/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md file_utils.c:301-340 | correctness/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md file_perm.c:37 | undocumented-invariant/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md checksum_helper.c:96-134 | undocumented-invariant/nit | still-present@d92e98340fcb
[done:2026-07-10] common.md checksum_helper.c:200-227 | undocumented-invariant/nit | still-present@d92e98340fcb
[done:2026-07-10] common.md restricted_token.c:151 | trust-boundary/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md compression.c,compression.h:17-20 | undocumented-invariant/likely | still-present@d92e98340fcb
[done:2026-07-10] common.md compression.c:304-327 | trust-boundary/maybe | still-present@d92e98340fcb
[done:2026-07-10] common.md compression.c:191,318,468 | correctness/nit | still-present@d92e98340fcb
[done:2026-07-10] common.md cryptohash.c:78-83 | stale-todo/nit | still-present@d92e98340fcb
[done:2026-07-10] common.md instr_time.c:411 | stale-todo/nit | still-present@d92e98340fcb

## Refill 2026-07-10 (pg-quality-auditor) — psql register, 21 line-cited open rows

common register fully drained this run (21 rows all still-present@d92e98340fcb,
0 drift, 0 upstream fixes). Next security-relevant frontend register: `psql`
(src/bin/psql) — the A4 secret-scrub + "psql as RCE primitive" clusters continue
the Phase D data-leak surface (credential-to-disk/memory, server-byte trust,
path/shell injection). All rows dated 2026-06, past the 30-day staleness threshold.

[done:2026-07-12] psql.md input.c:148-167 | secret-scrub/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md mainloop.c:431 | secret-scrub/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md common.c:1158 | secret-scrub/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md startup.c:249-302 | secret-scrub/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md command.c:2604-2607 | secret-scrub/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md settings.h:103 | info-disclosure/maybe | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md input.c:452 | path-traversal/maybe | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md describe.c:1917-2192 | info-disclosure/maybe | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md tab-complete.in.c:6305 | info-disclosure/maybe | seeded=2026-07-10 | drifted-14@54cd6fc83176 (→:6291; def 6912; register+per-file tag re-anchored)
[done:2026-07-12] psql.md common.c:741-755 | trust-boundary/nit | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md prompt.c:342-354 | info-disclosure/maybe | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md command.c:861-865 | trust-boundary/nit | seeded=2026-07-10 | drifted@54cd6fc83176 (→:252-256; :861-865 now \conninfo; guard 252-256/impl 2784; register re-anchored)
[done:2026-07-12] psql.md variables.c:281 | injection/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md common.c:862-920 | trust-boundary/nit | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md tab-complete.in.c:7041-7066 | trust-boundary/maybe | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md large_obj.c:151 | path-traversal/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md large_obj.c:187 | path-traversal/likely | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md copy.c:293,312 | shell-injection/nit | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md command.c:4690-4694 | shell-injection/nit | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md prompt.c:317-339 | shell-injection/maybe | seeded=2026-07-10 | still-present@54cd6fc83176
[done:2026-07-12] psql.md startup.c:830-835 | trust-boundary/nit | seeded=2026-07-10 | still-present@54cd6fc83176

## Refill 2026-07-12 (pg-quality-auditor) — utils register, 18 line-cited open rows

psql register fully drained this run (21 rows triaged @54cd6fc83176: 19 still-present,
2 drifted+re-anchored — tab-complete.in.c:6305→6291 requote_identifier, command.c:861-865
→252-256 \restrict guard). Next security-relevant backend register: `utils`
(src/backend/utils/adt + fmgr) — the server-file-read (`genfile.c`), XXE (`xml.c`),
privilege-default (`acl.c`), and binary-protocol DoS (`*recv`) clusters. Rows dated
2026-06, past the 30-day staleness threshold.

[done:2026-07-13] utils.md genfile.c:53-92 | trust-boundary/likely | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md genfile.c:65 | path-traversal/likely | seeded=2026-07-12 | still-present@eed6c0d33e09 (Log_directory escape :71-82)
[done:2026-07-13] utils.md xml.c:2046,1319 | xxe/likely | seeded=2026-07-12 | still-present@eed6c0d33e09 (loader :2046/setter :1319 exact; no XML_PARSE_NONET)
[done:2026-07-13] utils.md xml.c:2042 | stale-todo/nit | seeded=2026-07-12 | still-present@eed6c0d33e09 (comment @:2043-2044, ≤2-line drift)
[done:2026-07-13] utils.md formatting.c:3907 | dos/likely | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md formatting.c:6236 | correctness/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md encode.c:282-306 | dos/likely | seeded=2026-07-12 | still-present@eed6c0d33e09 (SIMD path added, also no CFI)
[done:2026-07-13] utils.md tsvector.c:461 | dos/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md tsquery.c:1240 | dos/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md multirangetypes.c:352 | dos/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md pg_dependencies.c (+ statext/mvdistinct.c:310, dependencies.c:557) | trust-boundary/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09 (dependencies.c:557 + mvdistinct.c:310 Assert exact)
[done:2026-07-13] utils.md ruleutils.c:5900-5965 | info-disclosure/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09 (make_viewdef @:5903)
[done:2026-07-13] utils.md name.c:57 vs :90 | wire-protocol/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md numutils.c:947 vs :983 | wire-protocol/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09 (:983→def :984, ≤1-line)
[done:2026-07-13] utils.md expandeddatum.c:88-145 | undocumented-invariant/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md windowfuncs.c:559 | correctness/maybe | seeded=2026-07-12 | still-present@eed6c0d33e09
[done:2026-07-13] utils.md tsvector_op.c:926 | correctness/maybe | seeded=2026-07-12 | drifted@eed6c0d33e09 (→:376,380 add_pos clamp; :926 is maxpos scan; register+per-file doc re-anchored)
[done:2026-07-13] utils.md ri_triggers.c:288 | correctness/maybe | seeded=2026-07-12 | drifted@eed6c0d33e09 (→def :4010 decl :295; :288 now ri_NullCheck; register re-anchored, per-file doc already correct)

## Refill 2026-07-13 (pg-quality-auditor) — utils-adt register, 18 line-cited open rows

utils register (utils.md) line-cited pending drained this run (18 rows triaged
@eed6c0d33e09: 16 still-present, 2 re-anchored — tsvector_op.c:926→:376,380
add_pos clamp, ri_triggers.c:288→def:4010/decl:295). Next in the recipe's
register list: `utils-adt` (src/backend/utils/adt scalar/basic-types register,
seeded by pg-file-backfiller) — finer per-function cites, rows dated
2026-06-03/09/16, all past the 30-day staleness threshold. (Cross-check: its
ri_triggers row independently reads :295,4010, confirming today's re-anchor.)

[done:2026-07-15] utils-adt.md bool.c:44-92 | undocumented-invariant/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md name.c:338-342 | undocumented-invariant/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md enum.c:135-141 | undocumented-invariant/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md cash.c:191,407 | undocumented-invariant/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md cash.c:226,240-241 | stale-todo/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md pg_lsn.c:272 | undocumented-invariant/maybe | seeded=2026-07-13
[done:2026-07-15] utils-adt.md uuid.c:550 | question/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md encode.c:644-658 | question/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md encode.c:174,412,834 | undocumented-invariant/maybe | seeded=2026-07-13
[done:2026-07-15] utils-adt.md ascii.c:92 | undocumented-invariant/maybe | seeded=2026-07-13
[done:2026-07-15] utils-adt.md ascii.c:187 | question/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md pg_locale_builtin.c:293-295 | info-disclosure/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md pg_locale_builtin.c:285-290 | correctness/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md ri_triggers.c:2185 | injection/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md ri_triggers.c:1004 | undocumented-invariant/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md ri_triggers.c:295,4010 | correctness/maybe | seeded=2026-07-13
[done:2026-07-15] utils-adt.md xml.c:2042 | stale-todo/nit | seeded=2026-07-13
[done:2026-07-15] utils-adt.md xml.c:4449-4451 | correctness/nit | seeded=2026-07-13

## Refill 2026-07-16 (pg-quality-auditor) — catalog register, 29 symbol-cited open rows

utils-adt register (utils-adt.md) line-cited pending drained on 2026-07-15. Next
in the recipe's register list: `catalog` (src/include/catalog/ `pg_*.h` headers,
seeded 2026-06-02 by the A1 catalog-headers sweep). These rows are **symbol/pattern
cited** (header + field/macro name) rather than `file:line`, so drift = "the cited
symbol / on-disk-char / struct-pun is still present in the header at the anchor."
All 29 concretely-checkable rows triaged @8f71f64deee6: **28 still-present, 1
claim-overstated** (pg_control.h version-bump obligation IS documented at :33 + :95
— annotated in-register, downgrade to nit at next re-seed; no code drift). Zero
upstream fixes, zero line-drift — catalog format-defining headers are stable by
design. Remaining ~39 catalog rows (propgraph empty-comment cluster, publication,
statistic_ext char-code, seclabel/shseclabel, auth_members, etc.) staged for the
next catalog pass. After catalog fully drains: `initdb`, `pg_dump` per the recipe.

[done:2026-07-16] catalog.md pg_statistic.h stavalues1..5 | leak/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (anyarray :121-125)
[done:2026-07-16] catalog.md pg_statistic_ext_data.h stxdmcv+stxdexpr | leak/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (:43-44)
[done:2026-07-16] catalog.md pg_authid.h rolpassword-no-TOAST | question/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (text :48, no DECLARE_TOAST)
[done:2026-07-16] catalog.md pg_largeobject_metadata.h lomacl-no-TOAST | leak/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (aclitem[1] :40)
[done:2026-07-16] catalog.md pg_parameter_acl.h parname-canon/text_ops | question/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (text_ops unique idx :57)
[done:2026-07-16] catalog.md pg_user_mapping.h umoptions-secret | question/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (text[1] :41)
[done:2026-07-16] catalog.md pg_replication_origin.h roident-uint16 | invariant/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (Oid :43, WAL-fit comment :39-40)
[done:2026-07-16] catalog.md pg_control.h version-bump-obligation | invariant/confirmed | seeded=2026-06-02 | claim-overstated@8f71f64deee6 (obligation documented :33+:95; nit at re-seed)
[done:2026-07-16] catalog.md pg_control.h rmgr-info-renumber | invariant/confirmed | seeded=2026-06-02 | still-present@8f71f64deee6 (no anti-renumber warning)
[done:2026-07-16] catalog.md pg_class.h RELKIND/RELPERSISTENCE/REPLICA_IDENTITY chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:171+ no on-disk warning)
[done:2026-07-16] catalog.md pg_attribute.h ATTRIBUTE_IDENTITY/GENERATED chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:133)
[done:2026-07-16] catalog.md pg_type.h TYPTYPE/TYPCATEGORY/TYPALIGN/TYPSTORAGE chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:280+)
[done:2026-07-16] catalog.md pg_proc.h PROKIND/PROVOLATILE/PROPARALLEL/PROARGMODE chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6
[done:2026-07-16] catalog.md pg_operator.h oprkind l/b | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:46-47)
[done:2026-07-16] catalog.md pg_am.h amtype i/t | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:65-66)
[done:2026-07-16] catalog.md pg_collation.h collprovider_name-omits-DEFAULT | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (switch :84-88 omits 'd' :74)
[done:2026-07-16] catalog.md pg_subscription.h substream/subtwophasestate/suborigin chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:65-123)
[done:2026-07-16] catalog.md pg_subscription_rel.h SUBREL_STATE-IPC-mixing | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:66-76; IPC-only now flagged :75)
[done:2026-07-16] catalog.md pg_trigger.h tgtype-bits-no-renumber-warning | undocumented-invariant/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (:96-103)
[done:2026-07-16] catalog.md pg_trigger.h tgenabled-no-symbolic-names | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:47)
[done:2026-07-16] catalog.md pg_attribute.h attlen/attbyval/attalign-mirror | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:58-102 prose only)
[done:2026-07-16] catalog.md pg_proc.h proargtypes-struct-pun | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:97 no static-assert)
[done:2026-07-16] catalog.md pg_index.h indkey-struct-pun | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:50-51)
[done:2026-07-16] catalog.md pg_partitioned_table.h partattrs-struct-pun | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:42-46 rationale comment, no enforcement)
[done:2026-07-16] catalog.md pg_foreign_table.h relkind='f'-invariant | undocumented-invariant/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (ftrelid :32, not schema-enforced)
[done:2026-07-16] catalog.md pg_extension.h extconfig/extcondition-parallel-arrays | undocumented-invariant/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (:43-45)
[done:2026-07-16] catalog.md pg_subscription.h subconninfo-ACL-doc-drift | doc-drift/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (header now reminds :39; ACL still in system_views.sql)
[done:2026-07-16] catalog.md pg_subscription_rel.h state/LSN-coupling | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@8f71f64deee6 (:37-45)
[done:2026-07-16] catalog.md pg_control.h 512-byte-atomicity | undocumented-invariant/likely | seeded=2026-06-02 | still-present@8f71f64deee6 (:252-257 says "one disk sector, 512" but not hw-defined framing)

## Refill 2026-07-19 (pg-quality-auditor) — catalog register DRAINED + initdb/pg_dump line-cited

catalog register (catalog.md) remaining 32 symbol-cited `open` rows triaged
@`03480907e9ff`: **all 32 still-present, 0 drift, 0 upstream fixes** (format-defining
headers are stable by design). Plus the 1 promised follow-up: pg_control.h
version-bump-obligation **severity downgraded confirmed→nit** (2026-07-16 flagged
the claim as overstated; obligation IS documented at `pg_control.h:33`+`:95`,
re-confirmed @`03480907e9ff`). **catalog register now fully drained** (all 68 rows
triaged across 2026-07-16 [29] + 2026-07-19 [32+1 downgrade]). Side-note: the
`BEGIN_CATALOG_STRUCT`/`END_CATALOG_STRUCT` wrapper macro now spans all catalog
structs — confirmed NOT new this window (present at 07-16 anchor `8f71f64deee6`),
background, no issue-row impact.

Per the recipe register list, then advanced into `initdb` + `pg_dump` line-cited
open rows past the 30-day staleness threshold (dated 2026-06-03). The 2026-06-22
pg_dump.c/pg_dumpall.c/pg_restore.c rows are only 27 days old → NOT yet eligible,
deferred to next cycle.

[done:2026-07-19] catalog.md pg_partitioned_table.h partstrat-onstat + partattrs-pun | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (partstrat :35, partattrs :46)
[done:2026-07-19] catalog.md pg_opclass.h opcdefault-uniqueness | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (opcdefault :74 BKI_DEFAULT(t))
[done:2026-07-19] catalog.md pg_default_acl.h DEFACLOBJ chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (defaclobjtype :39, DEFACLOBJ_* :70+)
[done:2026-07-19] catalog.md pg_init_privs.h InitPrivsType chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (enum :81, INITPRIVS_INITDB='i' :83)
[done:2026-07-19] catalog.md pg_largeobject.h direct-bytea-bypass-TOAST | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (bytea data :39 "direct access; see inv_api.c" :38)
[done:2026-07-19] catalog.md pg_seclabel.h label-opaque/provider | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (provider text :38)
[done:2026-07-19] catalog.md pg_policy.h polcmd-ACL_*_CHR-cross-header | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (polcmd :37 "One of ACL_*_CHR")
[done:2026-07-19] catalog.md pg_publication.h pubgencols-PUBLISH_GENCOLS chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (pubgencols :70, PUBLISH_GENCOLS_* :128+)
[done:2026-07-19] catalog.md pg_statistic_ext.h stxkind chars | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (stxkind[1] :57)
[done:2026-07-19] catalog.md pg_rewrite.h ev_type/ev_enabled cross-header | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (ev_type :39, ev_enabled :40)
[done:2026-07-19] catalog.md pg_event_trigger.h evtenabled-reuses-pg_trigger | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (evtenabled :39)
[done:2026-07-19] catalog.md pg_event_trigger.h evtevent-strings-on-disk | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (evtevent NameData :35)
[done:2026-07-19] catalog.md pg_event_trigger.h ordering-unspecified | question/maybe | seeded=2026-06-02 | still-present@03480907e9ff
[done:2026-07-19] catalog.md pg_auth_members.h grantor-row-identity | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (grantor :44; (roleid,member,grantor) uniq idx :66)
[done:2026-07-19] catalog.md pg_foreign_data_wrapper.h handler/validator-sig-drift | doc-drift/maybe | seeded=2026-06-02 | still-present@03480907e9ff (fdwhandler :36, fdwvalidator :38, prototypes elsewhere)
[done:2026-07-19] catalog.md pg_statistic.h STATISTIC_KIND-cross-project-contract | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (stavalues1..5 :121-125)
[done:2026-07-19] catalog.md pg_statistic_ext_data.h serialized-format-undocumented | doc-drift/maybe | seeded=2026-06-02 | still-present@03480907e9ff (stxdndistinct/stxddependencies/stxdmcv :41-43, formats live in statistics/)
[done:2026-07-19] catalog.md pg_seclabel.h no-Form_pg_seclabel-typedef | question/nit | seeded=2026-06-02 | still-present@03480907e9ff (grep Form_pg_seclabel → absent, anomaly holds)
[done:2026-07-19] catalog.md pg_shseclabel.h PK-omits-objsubid | question/nit | seeded=2026-06-02 | still-present@03480907e9ff (no objsubid in header/PK, divergence from pg_seclabel holds)
[done:2026-07-19] catalog.md pg_policy.h polroles-embedded-0-PUBLIC | question/maybe | seeded=2026-06-02 | still-present@03480907e9ff (polroles[1] BKI_LOOKUP_OPT(pg_authid) :42)
[done:2026-07-19] catalog.md pg_parameter_acl.h paracl-empty-ACL-semantics | question/nit | seeded=2026-06-02 | still-present@03480907e9ff (paracl[1] BKI_DEFAULT(_null_) :41)
[done:2026-07-19] catalog.md pg_propgraph_element.h minimal-header-comment | doc-drift/maybe | seeded=2026-06-02 | still-present@03480907e9ff (boilerplate-only comment, invariants in propgraphcmds.c)
[done:2026-07-19] catalog.md pg_propgraph_element.h eqop-OID-arrays-lack-BKI_LOOKUP | undocumented-invariant/maybe | seeded=2026-06-02 | still-present@03480907e9ff (pgesrceqop[1] :70, pgedesteqop[1] :87, no BKI_LOOKUP)
[done:2026-07-19] catalog.md pg_propgraph_element_label.h empty-header-comment | doc-drift/nit | seeded=2026-06-02 | still-present@03480907e9ff (generic Catalog.pm NOTES only, no substantive doc)
[done:2026-07-19] catalog.md pg_propgraph_element_label.h no-by-oid-syscache | question/nit | seeded=2026-06-02 | still-present@03480907e9ff
[done:2026-07-19] catalog.md pg_propgraph_label.h empty-header-comment | doc-drift/nit | seeded=2026-06-02 | still-present@03480907e9ff (generic NOTES only)
[done:2026-07-19] catalog.md pg_propgraph_label_property.h empty-header-comment | doc-drift/nit | seeded=2026-06-02 | still-present@03480907e9ff
[done:2026-07-19] catalog.md pg_propgraph_label_property.h serialized-expr-forces-catversion | undocumented-invariant/likely | seeded=2026-06-02 | still-present@03480907e9ff (plpexpr pg_node_tree :42, not stated in header)
[done:2026-07-19] catalog.md pg_propgraph_property.h empty-header-comment | doc-drift/nit | seeded=2026-06-02 | still-present@03480907e9ff
[done:2026-07-19] catalog.md pg_type.h CASHOID/LSNOID-ancient-aliases | stale-todo/nit | seeded=2026-06-02 | still-present@03480907e9ff (:343-347 "ancient random spellings")
[done:2026-07-19] catalog.md pg_database.h DATCONNLIMIT_INVALID_DB=-2-overload | stale-todo/nit | seeded=2026-06-02 | still-present@03480907e9ff (:125 "isn't particularly clean", :128 =-2)
[done:2026-07-19] catalog.md pg_authid.h rolsuper-via-superuser-only | question/nit | seeded=2026-06-02 | still-present@03480907e9ff (:37 "read this field via superuser() only!")
[done:2026-07-19] catalog.md pg_control.h version-bump-obligation | invariant/nit(↓from confirmed) | seeded=2026-06-02 | claim-corrected@03480907e9ff (obligation documented :33+:95; severity downgraded, register updated)

## Refill 2026-07-19 (pg-quality-auditor) — initdb register, 4 line-cited open rows

[done:2026-07-19] initdb.md initdb.c:1732 (get_su_pwd) | secret-scrub/likely | seeded=2026-06-03 | still-present@03480907e9ff (assign :1732 exact; file-scope static :156; no free/memset/explicit_bzero anywhere — plaintext-in-memory pattern intact)
[done:2026-07-19] initdb.md initdb.c:1706-1711 | trust-boundary/likely | seeded=2026-06-03 | still-present@03480907e9ff (comment "insist ... not world-readable" :1707, "skip the paranoia" :1709, fopen :1712 — range spot-on)
[done:2026-07-19] initdb.md initdb.c:1706-1711 | stale-todo/maybe | seeded=2026-06-03 | still-present@03480907e9ff (same "paranoia for now" comment unresolved)
[done:2026-07-19] initdb.md findtimezone.c:88 | undocumented-invariant/maybe | seeded=2026-06-03 | still-present@03480907e9ff (:88 cite = the single-timezone contract comment "we only support one loaded timezone at a time" :87-88; pg_load_tz def :91, `static pg_tz tz` :93 — per-file doc already anchors static @:93)

## Refill 2026-07-19 (pg-quality-auditor) — pg_dump register, 1 line-cited open row eligible

[done:2026-07-19] pg_dump.md connectdb.c:154 | correctness/likely | seeded=2026-06-03 | still-present@03480907e9ff (PQconnectdbParams(keywords,values,true) expand_dbname=true HARD-CODED at :154 exact; a dbname-discard guard was ADDED for connection_string [:75-98 discards "dbname" keyword from conn_opts] but the enumerated dbname/override_dbname function args [:138,:144] are still set as keyword "dbname" and remain subject to libpq expansion → hostile-datname redirect concern STILL stands)
