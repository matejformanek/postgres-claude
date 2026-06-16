# Iteration 1 — answers (with_skill vs baseline)

## Eval 1 — Row-level TTL brainstorm

### with_skill answer

**slug:** `row_ttl`

**1. Problem statement.** The user wants per-row TTL: a row inserted now
auto-disappears after N hours, without the user running their own DELETE
cron / sweeper. Beneficiary: app developer using PG as a session-store /
cache / event-log substitute. Not asking for a partition-drop scheme
(coarse-grained, time-bucketed) — they want per-row granularity with a
TTL set at INSERT time.

**2. Why this might matter.** Today PG users either (a) write a
`DELETE WHERE expires_at < now()` cron, (b) shard by time and `DROP
PARTITION`, or (c) leave the work to autovacuum after their own DELETE.
None of these are "set-and-forget" at the row level. The closest existing
mechanism is partitioning + detach, which is awkward at fine granularity.

**3. Relevant subsystems.**
- `knowledge/subsystems/access-heap.md` — TTL must interact with
  tuple visibility (xmin/xmax/HEAP_HOT_UPDATED) and tuple cleanup
  (heap_page_prune / vacuum).
- `knowledge/subsystems/access-transam.md` — autovacuum is the
  natural sweeper; a new "ttl-aware" autovacuum mode would live here.
- `knowledge/subsystems/parser-and-rewrite.md` — CREATE TABLE syntax
  extension (`WITH (ttl_column = expires_at)` or similar).

**4. Has this been tried?**
- CommitFest: search "TTL" / "row expiration" — pg_partman covers
  time-bucket TTL out-of-core; the CF history has had recurring
  discussion of "expiring tuples" but no landed core proposal
  [unverified — would `WebFetch` CF].
- git log `--grep='TTL\|expire'` — I'd expect to find nothing in core
  for per-row TTL [unverified].
- Extensions: `pg_partman` (time partitions), `pg_cron` + DELETE
  (the manual sweeper). The Citus / Timescale ecosystem has built
  per-row retention into hypertables. None of these are core.
- Scenarios layer: no direct hit, but the implementation would
  COMPOSE: `add-new-system-catalog-column` (#9, store ttl_column
  per relation in `pg_class` or a new aux table) ∪
  `add-new-sql-keyword`/`add-new-utility-statement` (#11/#13,
  `WITH (ttl = ...)` is a reloption — might fit without new
  grammar) ∪ `add-new-bgworker` (#23, dedicated ttl-vacuum
  worker) ∪ `add-new-guc` (#21, `ttl_check_interval`).
  **Scenarios layer gap:** "per-row policy enforced by a sweeper"
  is a recurring change-class (also: retention policies, soft
  delete, audit-cleanup). Worth a new scenario if this lands.

**5. Candidate approaches.**

**A. TTL as a relopt + autovacuum extension.** User declares
`WITH (ttl_column = expires_at, ttl_grace = '1h')` on the table.
Autovacuum, when it touches the relation, also runs a "ttl prune"
pass: for every tuple where `expires_at < now() - grace` and the
tuple is dead-by-ttl, mark dead. Reuses `heap_page_prune` machinery.
- Pros: smallest footprint; no new bgworker; user already accepts
  autovacuum's "eventually" semantics for visibility; reuses heap-am
  primitives.
- Cons: latency is autovacuum's latency (minutes-to-hours by
  default); requires a new pg_class column or a reloption for
  the ttl column name; "tuple is dead because the user's clock says
  so" is a new visibility concept that doesn't slot cleanly into
  HeapTupleSatisfiesMVCC.
- Scope: medium (~10 files: heap visibility, autovacuum, reloptions,
  parser for reloption, system view to inspect TTL state, docs).
- Reuses: autovacuum worker, heap_page_prune, reloptions framework.

**B. Dedicated TTL bgworker + DELETE.** Background worker scans
ttl-marked tables, runs `DELETE ... WHERE expires_at < now()`
in bounded batches. No changes to heap visibility — just a
better-integrated cron.
- Pros: zero changes to access-am or visibility; conceptually
  the same as user-space pg_cron + DELETE, just shipped in core;
  trivially backportable.
- Cons: it IS just a cron-in-core; doesn't solve the real "this
  row is dead the moment the clock crosses N" problem; competes
  with the user's own jobs.
- Scope: small-medium (~5 files: bgworker, GUC for interval, a
  catalog table listing ttl-tracked relations, sql syntax to
  register, docs).
- Reuses: BackgroundWorker API, SPI for the DELETE.

**C. TTL baked into tuple visibility (xmax-by-clock).** Extend
`HeapTupleSatisfiesMVCC` so a tuple with a non-null `ttl_at` is
invisible once `now() > ttl_at`. Pruning happens lazily by the
existing prune paths. Effectively "expired" becomes a third
visibility-state alongside live/dead.
- Pros: rows disappear *instantly* at the SQL semantics level
  (no autovacuum lag for queries); cleanest UX for the
  session-store use case.
- Cons: huge invariant footprint — every MVCC predicate, every
  index scan that returns a heap tuple, every replication path
  (logical decoding sees rows that may now be "expired"!), every
  vacuum decision. Snapshot stability gets murky if "expired"
  is clock-driven, not xid-driven. Pile of corner cases.
- Scope: large (touches HeapTupleSatisfies*, snapbuild, logical
  decoding, every index AM that hands rows back, replication;
  probably 30+ files and several invariants).
- Reuses: very little — mostly NEW invariants.

**6. Recommended approach.** **A (relopt + autovac extension)** —
smallest delta that delivers the feature with acceptable semantics.
The "expired tuple is dead like a normal dead tuple after autovac
notices it" semantics are weak but match user mental model of
autovacuum already. C would win only if a user explicitly demands
"the moment the clock crosses N seconds, the row MUST be invisible
to a concurrent query" — that's a stronger guarantee than PG
normally offers and probably out-of-scope.

**7. Decisions for the user.**
- DECISION: Does TTL need to be query-visible *instantly* at expiry
  (approach C), or is autovacuum-eventual OK (approach A/B)?
- DECISION: Should TTL fire on the *insert timestamp + interval* or
  on a *user-supplied column*? (i.e. is the TTL itself queryable?)
- DECISION: MVP scope — only `ttl_column = <existing column>` (user
  supplies the timestamp), or also automatic `inserted_at + interval`?
- DECISION: Should TTL also delete dependent rows via FK, or is
  "let cascade or fail on conflict" acceptable?
- DECISION: Target core, or ship as a contrib extension first
  (proves the relopt + bgworker integration before catalog
  changes are forced on everyone)?

**8. What this brainstorm did NOT figure out.**
- Catalog schema (new pg_class column? new pg_ttl_relation table?).
- WAL impact (probably none if A; large if C).
- Test surface — only sketched, not enumerated.
- Interaction with logical replication / row visibility on a
  subscriber.
- Concrete scenarios-layer composition with file checklist (that's
  Phase 2's job).

Run `/pg-plan row_ttl` once the DECISION: questions are answered.

### baseline answer

Per-row TTL in PG is interesting because PG doesn't really have it
today. You'd basically want a way to mark rows as "expires at" and
have something delete them. A few sketches:

- Easiest: a CREATE EXTENSION with a background worker that runs
  DELETE statements periodically. The user adds a column and
  registers the table. This is basically pg_cron with extra steps,
  but in core.
- Medium: extend table syntax with a TTL clause and have autovacuum
  notice and clean up. This is closer to what people probably want.
- Hardest: bake TTL into tuple visibility so rows just "disappear"
  at the right time. Probably too invasive.

I'd lean toward the medium approach. The harder question is whether
TTL fires on a user-supplied column or on insert-time + interval.
Also: should expired rows actually be removed or just marked
invisible? Replication might see them either way.

Open questions: scope (MVP vs full), how TTL interacts with
foreign keys, and whether to ship as core or contrib first.

I don't know offhand whether anyone has proposed this on
pgsql-hackers recently or whether pg_partman / Timescale already
cover the user need.

---

## Eval 2 — "Rewind to LSN X" without restart

### with_skill answer

**slug:** `live_rewind_to_lsn`

**1. Problem statement.** The user wants an online "rewind to LSN X"
SQL command: a running server (with active connections) is told
"undo everything after LSN X and resume there", without `pg_ctl
restart` + recovery. Beneficiary: SRE doing emergency rollback
after a bad batch (DELETE FROM big_table NO WHERE); also test
infra that wants fast rewind between scenarios.

**2. Why this might matter.** Today the rollback path is:
`pg_ctl stop` → restore from base backup → set `recovery_target_lsn`
→ start server in recovery → promote. Minutes to hours of downtime.
A live-rewind would shrink that to seconds *if* it's safe — which is
the entire question.

**3. Relevant subsystems.**
- `knowledge/subsystems/access-transam.md` — XLogReadRecord, redo,
  the recovery state machine; `xlog.c` startup-process loop.
- `knowledge/subsystems/replication.md` — physical replication
  already has the "promote a standby at LSN X" code path; hot
  standby readers; the synchronous-commit machinery.
- `knowledge/subsystems/storage-buffer.md` — buffer pool would
  need a flush + reset; dirty pages above LSN X would need to be
  discarded, not written back.

**4. Has this been tried?**
- CommitFest: there are recurring discussions of "online PITR" /
  "branchable databases" / "Aurora-style rewind" — I'd expect
  CF entries on related concepts (e.g. neon's `pg_truncate_xlog`
  experiments) but nothing landed in core [unverified — would
  `WebFetch` CF].
- git log `--grep='rewind\|recovery_target'` — pg_rewind exists
  (`src/bin/pg_rewind/`) but that's offline. `recovery_target_lsn`
  is set-at-startup, not online.
- Existing offline machinery: PITR via `recovery_target_lsn` +
  archive-shipping, `pg_rewind` to align a divergent primary with
  a new primary. Both require server stop.
- The closest existing "online" concept is **promotion** (a hot
  standby promoting at a configured LSN) — already implemented in
  `startup.c` / `walreceiver.c`. But promotion's direction is
  *forward to consistency*, not *backward from current state*.
- Scenarios layer: no direct hit. Closest compositions would
  involve `add-new-utility-statement` (#13, new `REWIND TO LSN`
  command) ∪ `add-new-wal-record` (#19, possibly a "rewind
  marker" record) ∪ a deep custom recovery-state-machine
  patch that has no scenario equivalent. **Scenarios layer gap:**
  "modify the live recovery state machine" — recurring class of
  feature with no playbook yet.

**5. Candidate approaches.**

**A. SQL command that does `pg_ctl restart --recovery-target-lsn=X`
internally (a "controlled crash + restart").** No live rewind;
just automate the existing offline path. Backend kills connections,
writes a shutdown checkpoint, postmaster restarts in recovery to
LSN X, comes back up.
- Pros: zero new invariants — reuses every existing recovery code
  path; safe by construction.
- Cons: not really *live* (still has the restart gap, even if
  scripted); doesn't meet the user's "without restart" framing.
- Scope: small (~3-5 files: utility statement, postmaster signal,
  control-file dance).
- Reuses: existing `recovery_target_lsn` + startup process.

**B. Quiesce + in-process rewind: drain backends, flush buffer
pool, run the startup process's redo loop *backward* (or rather,
reset to LSN X and replay from base backup).** Server stays up
in a "rewinding" state where new connections get a clear error.
- Pros: shorter downtime than a full restart (postmaster doesn't
  die, network sockets stay open); can return a clean SQL error
  to the issuer.
- Cons: needs a new server state ("rewinding"); every subsystem
  that holds cross-LSN state (replication slots, prepared xacts,
  unlogged tables, walsender connections, GIN pending list,
  visibility map) needs to react to the rewind — most of these
  haven't been designed to go backward; huge invariant burden.
- Scope: large (recovery state machine, shmem reinit, every
  subsystem that caches LSN-keyed state; 30+ files).
- Reuses: redo loop, base-backup machinery — but in a new context.

**C. Branchable database via copy-on-write filesystem (zfs/btrfs
snapshot, or COW at the smgr layer).** User issues "branch at
LSN X", PG starts a parallel "snapshot postmaster" pointing at the
snapshot. Original keeps running unchanged.
- Pros: original DB unaffected; user can investigate the snapshot
  side-by-side; this is the Neon / Aurora model and it works.
- Cons: requires either external filesystem support (zfs) or a
  new smgr layer in PG that knows how to COW pages — basically a
  re-architecture. Doesn't really answer "rewind THIS database"; it
  spawns a sibling.
- Scope: very large (essentially a new storage layer + lifecycle).
- Reuses: smgr indirection, base-backup format.

**6. Recommended approach.** **A (scripted offline restart).**
B is interesting but the invariant-burden is enormous — every LSN-
keyed cache, every replication slot, every walsender would need
a rewind hook, and the upgrade path is "the entire server now has
to be able to go backward". C is a different product. A meets the
user's *outcome* (faster rollback) without inventing new invariants;
the user's "without restart" framing may be negotiable once they
see the cost.

What would have to be true for B to win: a use case where the
restart-gap (10s-30s) is itself unacceptable AND the user is
willing to lose all logical/physical replication state at rewind.
For C to win: the user actually wants a sibling-branch model,
not in-place rewind.

**7. Decisions for the user.**
- DECISION: Is the goal "minimize downtime" (then A is enough) or
  "no downtime / connections stay open" (then B or C)?
- DECISION: How does rewind interact with **active replication
  slots** — invalidate them, rewind them too, or refuse rewind?
- DECISION: How does rewind interact with **logical replication
  subscribers** that already consumed rewound-away changes?
  Same question different angle.
- DECISION: MVP scope — only "rewind to a recent LSN within the
  current WAL retention", or restore-from-archive too?
- DECISION: Does the user actually want a *branchable* DB (C)
  rather than in-place rewind? (Worth surfacing because B is
  expensive and C is a different product.)

**8. What this brainstorm did NOT figure out.**
- Concrete state-machine for B (which backend states are
  rewind-safe).
- Replication slot semantics across a rewind.
- pg_rewind's existing offline mechanism in detail (Phase 2
  would deep-read `src/bin/pg_rewind/`).
- WAL impact (probably none for A; "rewind marker" WAL record
  for B).
- Backward-compatibility (none of these can be backported).

Run `/pg-plan live_rewind_to_lsn` after the DECISION: questions.

### baseline answer

PG already has `recovery_target_lsn` but it's only set at startup
in recovery mode. To do an online rewind, you'd basically need
to either (a) automate the restart-in-recovery dance from SQL,
or (b) actually rewind in place, which would touch the WAL
machinery (xlog.c), the buffer pool, and replication slots.
Option (b) is a lot more work because PG's recovery is designed
to go forward.

Subsystems involved: WAL / xlog, recovery / startup process,
buffer manager (dirty pages above LSN X must not be written
back), replication (slots are LSN-keyed). Probably also the
catalog cache / relmapper.

I'd guess approach (a) is the realistic one — drain backends,
restart-in-recovery, come back up. Approach (b) might work for
a very recent LSN where nothing else has happened, but in
general it's a huge invariant problem.

Existing related work: `pg_rewind` (offline tool), PITR via
recovery_target_*. I don't recall any in-flight CommitFest entry
for online rewind.

Open questions: scope, replication-slot semantics during rewind,
what happens to in-flight transactions.

---

## Eval 3 — `plpgsql_check` as core: dead-code analysis at CREATE FUNCTION time

### with_skill answer

**slug:** `plpgsql_static_check`

**1. Problem statement.** User wants `CREATE FUNCTION ... LANGUAGE
plpgsql` to do compile-time dead-code analysis (e.g. unreachable
RETURNs, unused variables, unreachable branches after RAISE
EXCEPTION). Beneficiary: app developer + DBA who only finds these
bugs at first call.

**2. Why this might matter.** Today plpgsql parses at CREATE FUNCTION
but defers semantic checks (column references, type mismatches,
dead code) to first execution. Heavy schemas with hundreds of
functions surface bugs at the worst time. The community's
`plpgsql_check` extension already does this — the question is
whether the *core* path should do it too.

**3. Relevant subsystems.**
- `knowledge/subsystems/parser-and-rewrite.md` — `pl_gram.y` /
  `pl_handler.c` / `pl_comp.c` (plpgsql's own parser); the place
  where SQL-statement strings inside plpgsql get parsed.
- `knowledge/subsystems/utils-cache.md` — function plan caching;
  whether validation results stick around.
- `knowledge/subsystems/tcop.md` — DDL / CREATE FUNCTION dispatch.

**4. Has this been tried?** **YES — this is the critical reframe.**
- The extension **`plpgsql_check`** by Pavel Stěhule is widely used
  and very mature: it provides `plpgsql_check_function`,
  `plpgsql_check_function_tb`, profiler, tracer, and roughly the
  feature set the user is describing. It exists in OS packages
  (Debian, RHEL, pgdg). [Pavel's repo:
  github.com/okbob/plpgsql_check — unverified link, well-known
  in the community.]
- This means the brainstorm is NOT "what would it take" but
  "should we **upstream** the extension, or **ship the missing
  bits** to make the extension easier to use"?
- CommitFest: there have been recurring discussions of
  "tighter plpgsql validation at CREATE time" but the consensus
  has tended to be "the extension does this; if you want it,
  install it" [unverified, but matches the community pattern].
- git log: `plpgsql_check_function` is the existing function
  named `check_function_bodies` (the GUC and `pl_handler.c`
  validator) — this is the EXISTING hook the extension uses.
  `pl_handler.c:plpgsql_validator` is invoked at CREATE FUNCTION
  *only when* `check_function_bodies = on`. So a hook already
  exists; the question is what runs in it.
- Scenarios layer: no direct hit. The relevant compositions
  would be `add-new-extension` (#30, if we just want a better
  extension story) ∪ maybe `add-new-guc` (#21, a switch like
  `plpgsql_extra_checks` already exists). **The scenario gap
  here is "promote a contrib feature into core" — not really
  a scenario, more a project-process question.**

**5. Candidate approaches.**

**A. Ship the extension's behavior as opt-in core checks.**
Add a GUC like `plpgsql_validation_level = basic | strict |
paranoid` (or extend the existing `plpgsql.extra_warnings`),
copy a curated subset of `plpgsql_check`'s analyses into
`pl_handler.c:plpgsql_validator`, and have CREATE FUNCTION
emit warnings (or errors at the strict level).
- Pros: in-tree without `CREATE EXTENSION`; benefits the
  long tail of users who never install extensions; existing
  `check_function_bodies` GUC + validator hook is the right
  surface.
- Cons: the upstream extension's surface is large and
  evolves quickly — what we copy goes stale; it's a maintenance
  burden on -hackers to keep up; bikeshed risk on "which
  checks are good defaults".
- Scope: medium (~10-20 files: pl_comp.c, pl_exec.c
  validator path, new GUC, new error categories, docs, big
  test surface).
- Reuses: existing `plpgsql_validator` hook +
  `check_function_bodies` GUC.

**B. Don't upstream the analyses; instead make the extension's
job easier.** Survey what `plpgsql_check` has to monkey-patch
or re-parse, and ship those primitives as core hooks /
exported APIs. The extension becomes a thinner adapter on
better core hooks.
- Pros: maintains the extension boundary; the extension is
  already in distros; this gives Pavel + future plugin
  authors a sturdier foundation.
- Cons: doesn't help users who don't install extensions;
  requires Pavel-engagement on -hackers; harder to know
  *which* hooks to add without a co-design.
- Scope: small-medium (depends on what's missing — could be
  just 2-3 hook exports + an SPI / cache invalidation
  primitive).
- Reuses: existing hook framework + `_PG_init` registration.

**C. Ship the extension as a contrib module.** Move
`plpgsql_check` (with Pavel's consent + licensing) into
`contrib/plpgsql_check/`. No core changes; the extension is
shipped + tested with the server.
- Pros: trivially solves "users don't install extensions"
  because contrib is part of `postgresql-contrib` packages
  in most distros; no API/spec design needed; minimal
  maintenance — Pavel keeps committing.
- Cons: contrib has a higher bar than out-of-core; license
  + governance question; the extension is large and would
  bloat contrib's footprint; this is really a community-
  process question more than a technical one.
- Scope: small technically (file move + Makefile/meson +
  RPM/deb packaging coordination); large socially.
- Reuses: contrib infrastructure (`add-new-extension`
  scenario #30).

**6. Recommended approach.** **B (export better hooks).**
The extension exists, is mature, and is already packaged in
distros. Forcing core to track its surface (A) is a long-term
maintenance trap. Moving it to contrib (C) is the politically
cleanest but doesn't really solve any technical problem; it's
mostly a packaging question and should be decided by Pavel +
the packagers, not by a feature design. Meanwhile B —
surveying what the extension has to work around and shipping
those primitives — *durably* improves the platform for all
plpgsql-tooling, not just one extension.

What would have to be true for A: the user (or community)
decides that "having to install an extension" is itself the
problem and a curated core subset is worth the maintenance
burden. For C: Pavel agrees, and the contrib bar question is
answered yes.

**7. Decisions for the user.**
- DECISION: Are you aware that `plpgsql_check` (Pavel Stěhule's
  extension) already provides this? Does it not fit your need,
  and if so, why?
- DECISION: Is the goal "ship checks to every PG user" (favors A
  or C) or "give extension authors better tools" (favors B)?
- DECISION: If A — which checks are the MVP core set?
  (`plpgsql_check` has dozens; the bar for "default on" is
  high.)
- DECISION: If C — is moving an externally-maintained extension
  into contrib a path you'd want to drive with Pavel + the
  packagers? (Process-heavy.)
- DECISION: How errored is the "wrong" code today — warnings,
  errors, or both? Are existing `plpgsql.extra_warnings` /
  `plpgsql.extra_errors` GUCs enough surface?

**8. What this brainstorm did NOT figure out.**
- The exact extension API surface that B would need.
- The list of checks the extension provides (Phase 2 would
  read its source).
- Compatibility with PL/Perl, PL/Python (out-of-scope?).
- Whether `check_function_bodies` GUC is the right surface or
  needs a sibling.
- Test surface enumeration.

Run `/pg-plan plpgsql_static_check` after answering the
DECISION: questions — particularly the "are you aware the
extension exists" question, because the answer reframes
which approach is even on the table.

### baseline answer

`plpgsql_check` is a thing — Pavel Stěhule maintains it as an
extension. It does pretty thorough static analysis of plpgsql
function bodies. So before brainstorming from scratch, the
real question is: do you want to upstream what already exists,
or build something new?

Approaches:
- Add static analysis to `plpgsql_validator` in `pl_handler.c`
  when `check_function_bodies` is on. This is where CREATE
  FUNCTION already validates plpgsql today.
- Add it as a separate GUC like `plpgsql_extra_checks`.
- Move plpgsql_check into contrib.

The first is the most invasive; the third is the lightest if
licensing / governance work out. Open questions: which checks
are in scope, whether warnings or errors, and whether to also
handle PL/Perl etc.

I think the main thing to flag is: this functionality basically
exists already — you should pick "make the extension easier to
install" vs "ship a subset in core" before designing.
