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

[pending] utils-adt.md bool.c:44-92 | undocumented-invariant/nit | seeded=2026-07-13
[pending] utils-adt.md name.c:338-342 | undocumented-invariant/nit | seeded=2026-07-13
[pending] utils-adt.md enum.c:135-141 | undocumented-invariant/nit | seeded=2026-07-13
[pending] utils-adt.md cash.c:191,407 | undocumented-invariant/nit | seeded=2026-07-13
[pending] utils-adt.md cash.c:226,240-241 | stale-todo/nit | seeded=2026-07-13
[pending] utils-adt.md pg_lsn.c:272 | undocumented-invariant/maybe | seeded=2026-07-13
[pending] utils-adt.md uuid.c:550 | question/nit | seeded=2026-07-13
[pending] utils-adt.md encode.c:644-658 | question/nit | seeded=2026-07-13
[pending] utils-adt.md encode.c:174,412,834 | undocumented-invariant/maybe | seeded=2026-07-13
[pending] utils-adt.md ascii.c:92 | undocumented-invariant/maybe | seeded=2026-07-13
[pending] utils-adt.md ascii.c:187 | question/nit | seeded=2026-07-13
[pending] utils-adt.md pg_locale_builtin.c:293-295 | info-disclosure/nit | seeded=2026-07-13
[pending] utils-adt.md pg_locale_builtin.c:285-290 | correctness/nit | seeded=2026-07-13
[pending] utils-adt.md ri_triggers.c:2185 | injection/nit | seeded=2026-07-13
[pending] utils-adt.md ri_triggers.c:1004 | undocumented-invariant/nit | seeded=2026-07-13
[pending] utils-adt.md ri_triggers.c:295,4010 | correctness/maybe | seeded=2026-07-13
[pending] utils-adt.md xml.c:2042 | stale-todo/nit | seeded=2026-07-13
[pending] utils-adt.md xml.c:4449-4451 | correctness/nit | seeded=2026-07-13
