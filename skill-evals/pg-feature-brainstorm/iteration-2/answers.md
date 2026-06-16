# Iteration 2 — answers (with_skill vs baseline)

Same 3 prompts as iter-1, after applying 5 SKILL.md edits (URL fix +
PGXN/out-of-tree-extension prior-art category + composite-scenarios +
distinctness heuristic + worked DECISION examples + Anti-patterns
section). Same 11-assertion rubric per eval.

## Eval 1 — Row-level TTL brainstorm

### with_skill answer

**slug:** `row_ttl`

**1. Problem statement.** The user wants per-row TTL: a row inserted now
auto-disappears after N hours, without the user running their own
DELETE cron / sweeper. Beneficiary: app developer using PG as
session-store / cache / event-log substitute. Not a coarse partition-
drop scheme — they want per-row granularity with TTL set at INSERT.

**2. Why this might matter.** Today PG users either (a) write a
`DELETE WHERE expires_at < now()` cron, (b) shard by time and `DROP
PARTITION`, or (c) leave the work to autovacuum after their own
DELETE. None are "set-and-forget" at row granularity.

**3. Relevant subsystems.**
- `knowledge/subsystems/access-heap.md` — TTL interacts with tuple
  visibility (xmin/xmax/HEAP_HOT_UPDATED) and cleanup
  (heap_page_prune / vacuum).
- `knowledge/subsystems/access-transam.md` — autovacuum is the
  natural sweeper.
- `knowledge/subsystems/parser-and-rewrite.md` — CREATE TABLE syntax
  extension (`WITH (ttl_column = expires_at)`).

**4. Has this been tried?**
- CommitFest: `WebFetch https://commitfest.postgresql.org/?text=TTL`
  — recurring discussion of "row expiration" / "automatic deletion"
  but no landed core proposal [unverified — would actually fetch].
- git log `--grep='TTL\|expire' --since='2y'` — likely nothing in
  core [unverified].
- **Out-of-tree extensions**: `pg_partman` (time-bucket retention,
  mature, in distros) — coarse-grained but works. `pg_cron` + user
  DELETE — the manual path. Timescale's hypertables have per-row
  retention but only for time-series.  **Per-row TTL at the heap
  level: no mature extension I'm aware of** — but worth a PGXN
  check before committing. So the "extension already does this"
  reframe is half-applicable: time-bucket TTL is solved out-of-
  tree; per-row TTL is the actual gap.
- Corpus: `grep -ri 'ttl\|expire' knowledge/` — likely nothing
  beyond autovacuum docs [unverified].
- **Scenarios layer**: composite of `add-new-system-catalog-column`
  (#9, store ttl_column per relation) ∪ `add-new-utility-statement`
  /`add-new-sql-keyword` (#13/#11, IF reloption form is too narrow)
  ∪ `add-new-bgworker` (#23, dedicated ttl-vacuum worker, if not
  reusing autovacuum) ∪ `add-new-guc` (#21, `ttl_check_interval`).
  **Scenarios layer gap:** "per-row policy enforced by a sweeper"
  is a recurring change-class (also: retention policies, soft
  delete, audit-cleanup), but no scenario covers it directly.
  Worth flagging — same shape will recur.

**5. Candidate approaches.**

Distinctness check (per Anti-patterns §): the three below differ
on (a) owning subsystem, (b) invariant footprint, (c) user-visible
surface — genuinely distinct, not flavors-of-the-same.

**A. TTL as a relopt + autovacuum extension.** User declares
`WITH (ttl_column = expires_at, ttl_grace = '1h')`. Autovacuum
runs a TTL-prune pass: for every tuple where `expires_at < now()
- grace`, mark dead. Reuses `heap_page_prune`.
- Pros: smallest footprint; no new bgworker; user already accepts
  autovacuum's "eventually" semantics for visibility; reuses
  heap-am primitives.
- Cons: latency is autovacuum's (minutes-to-hours); needs a new
  pg_class column / reloption for the ttl column; "tuple is dead
  because the user's clock says so" is a new visibility concept
  that doesn't slot into HeapTupleSatisfiesMVCC cleanly.
- Scope: medium (~10 files: heap visibility, autovacuum,
  reloptions, parser for reloption, system view, docs).
- Reuses: autovacuum worker, heap_page_prune, reloptions
  framework.

**B. Dedicated TTL bgworker + DELETE.** Bgworker scans ttl-marked
tables, runs `DELETE ... WHERE expires_at < now()` in bounded
batches. No heap visibility changes.
- Pros: zero changes to access-am or visibility; conceptually
  same as user-space `pg_cron` + DELETE; trivially backportable.
- Cons: it IS cron-in-core; doesn't solve "this row is dead the
  moment the clock crosses N"; competes with user's own jobs.
- Scope: small-medium (~5 files: bgworker, GUC, registration
  catalog, sql syntax, docs).
- Reuses: BackgroundWorker API, SPI for the DELETE.

**C. TTL baked into tuple visibility (xmax-by-clock).** Extend
`HeapTupleSatisfiesMVCC` so a tuple with `ttl_at` is invisible
once `now() > ttl_at`. Pruning is lazy by existing prune paths.
- Pros: rows disappear *instantly* at SQL semantics level (no
  autovacuum lag); cleanest UX for session-store use case.
- Cons: huge invariant footprint — every MVCC predicate, every
  index scan, every logical-decoding path (decoder sees rows
  that may now be "expired"), every vacuum decision; snapshot
  stability gets murky when invisibility is clock-driven not
  xid-driven.
- Scope: large (HeapTupleSatisfies*, snapbuild, logical decoding,
  every index AM, replication; 30+ files, several new invariants).
- Reuses: little — mostly NEW invariants.

**6. Recommended approach.** **A (relopt + autovac extension).**
Smallest delta with acceptable semantics. C only wins if the user
explicitly demands clock-instant invisibility — a stronger guarantee
than PG normally offers. B is sub-A: it's just cron-in-core.

**7. Decisions for the user.**
- DECISION: Is the goal "minimize sweeper-cron pain" (then A) or
  "row must be query-invisible *immediately* at clock crossing"
  (then C)? — semantics tradeoff.
- DECISION: Should TTL fire on the *insert timestamp + interval*
  or on a *user-supplied column*? (i.e. is the TTL itself
  queryable?)
- DECISION: Ship as contrib first (proves relopt + bgworker
  integration before catalog changes are forced on everyone), or
  aim for core in one go?
- DECISION: Should TTL also delete dependent rows via FK, or is
  "let cascade or fail on conflict" acceptable?
- DECISION: Target current master or wait for the next CF window
  (catalog change → CATALOG_VERSION_NO bump → initdb invalidation
  for existing testers)?

**8. What this brainstorm did NOT figure out.**
- Catalog schema (new pg_class column? new pg_ttl_relation table?).
- WAL impact (probably none for A; large for C).
- Test surface — only sketched.
- Interaction with logical replication / row visibility on
  subscriber.
- Concrete scenarios-layer composition with file checklist (Phase 2).

Run `/pg-plan row_ttl` after answering the DECISION: questions.

### baseline answer

Per-row TTL in PG is interesting because PG doesn't really have it
today. You'd want a way to mark rows as "expires at" and have
something delete them. Sketches:

- Easiest: CREATE EXTENSION with a background worker running
  periodic DELETEs. Basically pg_cron with extra steps in core.
- Medium: extend table syntax with a TTL clause; have autovacuum
  notice and clean up.
- Hardest: bake TTL into tuple visibility so rows just "disappear"
  at the right time. Probably too invasive.

Lean toward medium. Harder question: does TTL fire on a user-
supplied column or on insert-time + interval? Also: should expired
rows be removed or just marked invisible? Replication might see
them either way.

Open: scope (MVP vs full), FK interaction, core vs contrib.

I don't know offhand whether anyone proposed this on pgsql-hackers
recently or whether pg_partman / Timescale already cover the user
need.

---

## Eval 2 — "Rewind to LSN X" without restart

### with_skill answer

**slug:** `live_rewind_to_lsn`

**1. Problem statement.** Live "rewind to LSN X" SQL command: a
running server (with active connections) undoes everything after
LSN X and resumes there, without `pg_ctl restart` + recovery.
Beneficiary: SRE doing emergency rollback after a bad batch; also
test infra wanting fast scenario rewind.

**2. Why this might matter.** Today's rollback path is `pg_ctl
stop` → restore from base backup → set `recovery_target_lsn` →
start in recovery → promote: minutes-to-hours of downtime. Live-
rewind would shrink that to seconds, *if* it's safe.

**3. Relevant subsystems.**
- `knowledge/subsystems/access-transam.md` — XLogReadRecord,
  redo, the recovery state machine (`xlog.c` startup loop).
- `knowledge/subsystems/replication.md` — physical replication
  already has "promote a standby at LSN X"; hot standby readers;
  synchronous-commit machinery.
- `knowledge/subsystems/storage-buffer.md` — buffer pool flush
  + reset; dirty pages above LSN X must be discarded.

**4. Has this been tried?**
- CommitFest: `WebFetch https://commitfest.postgresql.org/?text=rewind`
  — pg_rewind is offline; recurring discussion of "online PITR" /
  "branchable databases" / "Aurora-style rewind" but nothing
  landed in core [unverified].
- git log `--grep='rewind\|recovery_target'` — `pg_rewind`
  (`src/bin/pg_rewind/`) exists, offline only. `recovery_target_lsn`
  is set-at-startup, not online.
- **Out-of-tree extensions**: the Neon project has
  `pg_truncate_xlog` experiments and a branchable-DB model; Aurora
  has the rewind product feature. Both are *fork* products, not
  PG extensions. So no PGXN extension to reframe against — but
  there IS commercial prior art (Neon, Aurora) that informs the
  product DECISION:.
- Corpus: `knowledge/subsystems/access-transam.md` covers
  recovery; `replication.md` covers promote-at-LSN.
- **Scenarios layer**: closest compositions —
  `add-new-utility-statement` (#13, new `REWIND TO LSN`) ∪
  `add-new-wal-record` (#19, possibly a "rewind marker" record).
  But the actual change is "modify the live recovery state
  machine", which no scenario covers. **Scenarios layer gap:**
  "modify the recovery state machine in flight" — recurring
  change-class that has no playbook (also would apply to:
  pause/resume recovery, point-in-time fork, online standby
  reset). Worth flagging.

**5. Candidate approaches.**

Distinctness check: all three differ on owning subsystem AND
invariant footprint — distinct.

**A. SQL command that does `pg_ctl restart --recovery-target-lsn=X`
internally (controlled crash + restart).** Backend kills
connections, writes a shutdown checkpoint, postmaster restarts
in recovery to LSN X.
- Pros: zero new invariants — reuses every existing recovery
  path; safe by construction.
- Cons: not really *live* (still a restart gap, even if scripted);
  doesn't meet "without restart" framing literally.
- Scope: small (~3-5 files: utility statement, postmaster
  signal, control-file dance).
- Reuses: existing `recovery_target_lsn` + startup process.

**B. Quiesce + in-process rewind: drain backends, flush buffer
pool, reset shmem state, replay from base backup.** Server stays
up in a "rewinding" state; new connections get a clear error.
- Pros: shorter downtime than full restart (postmaster doesn't
  die, sockets stay open); clean SQL error path.
- Cons: new server state ("rewinding"); every subsystem holding
  cross-LSN state (replication slots, prepared xacts, unlogged
  tables, walsender connections, GIN pending list, visibility
  map) needs to react to rewind — most haven't been designed
  to go backward; huge invariant burden.
- Scope: large (recovery state machine, shmem reinit, every
  LSN-keyed cache; 30+ files).
- Reuses: redo loop, base-backup machinery — in a new context.

**C. Branchable database via COW snapshot (zfs/btrfs/smgr
indirection).** User issues "branch at LSN X"; PG starts a
parallel "snapshot postmaster" pointing at the snapshot.
Original keeps running unchanged.
- Pros: original DB unaffected; user can investigate the snapshot
  side-by-side; Neon / Aurora model that works in practice.
- Cons: requires external filesystem support OR new COW smgr
  layer — basically a re-architecture; doesn't really answer
  "rewind THIS database" — it spawns a sibling.
- Scope: very large (new storage layer + lifecycle).
- Reuses: smgr indirection, base-backup format.

**6. Recommended approach.** **A (scripted offline restart).** B's
invariant burden is enormous — every LSN-keyed cache, every
replication slot, every walsender needs a rewind hook; the
upgrade path is "the entire server now has to be able to go
backward". C is a different product (sibling-branch model, not
in-place rewind). A meets the *outcome* (faster rollback)
without inventing new invariants; the "without restart" framing
may be negotiable once the user sees the cost.

For B to win: a use case where the restart gap (10s-30s) is
itself unacceptable AND user is willing to lose all replication
state. For C to win: user actually wants a branchable DB.

**7. Decisions for the user.**
- DECISION: Is your goal "minimize downtime" (then A is enough)
  or "no downtime / connections stay open" (then B)? — semantics.
- DECISION: How does rewind interact with **active replication
  slots** — invalidate them, rewind them too, or refuse rewind?
- DECISION: How does rewind interact with **logical-replication
  subscribers** that already consumed rewound-away changes?
- DECISION: Do you actually want a *branchable* DB (C) rather
  than in-place rewind? Worth surfacing because B is expensive
  and C is a different product (Neon / Aurora model).
- DECISION: MVP scope — only "rewind to a recent LSN within
  current WAL retention", or restore-from-archive too?

**8. What this brainstorm did NOT figure out.**
- Concrete state-machine for B (which backend states are
  rewind-safe).
- Replication-slot semantics across a rewind.
- pg_rewind's existing offline mechanism in detail (Phase 2).
- WAL impact (none for A; "rewind marker" WAL record for B).
- Backward-compat (none of these can be backported).

Run `/pg-plan live_rewind_to_lsn` after the DECISION: questions.

### baseline answer

PG has `recovery_target_lsn` but only set at startup in recovery
mode. For online rewind, you'd either (a) automate the restart-
in-recovery from SQL, or (b) actually rewind in place — touching
xlog.c, the buffer pool, and replication slots. (b) is much more
work because PG recovery goes forward.

Subsystems: WAL / xlog, recovery / startup process, buffer manager
(dirty pages above LSN X must not be written back), replication
(slots are LSN-keyed). Probably catalog cache / relmapper too.

(a) is the realistic one — drain backends, restart-in-recovery,
come back up. (b) might work for a very recent LSN where nothing
else happened, but in general is a huge invariant problem.

Existing related work: `pg_rewind` (offline), PITR via
`recovery_target_*`. I don't recall any in-flight CF entry for
online rewind.

Open: scope, replication-slot semantics during rewind, in-flight
transactions.

---

## Eval 3 — `plpgsql_check` as core: dead-code at CREATE FUNCTION

### with_skill answer

**slug:** `plpgsql_static_check`

**1. Problem statement.** User wants `CREATE FUNCTION ... LANGUAGE
plpgsql` to do compile-time dead-code analysis (unreachable
RETURNs, unused variables, unreachable post-RAISE branches).
Beneficiary: app developer + DBA who only finds these bugs at
first call.

**2. Why this might matter.** Today plpgsql parses at CREATE
FUNCTION but defers semantic checks to first execution. Heavy
schemas with hundreds of functions surface bugs at the worst
time.

**3. Relevant subsystems.**
- `knowledge/subsystems/parser-and-rewrite.md` — `pl_gram.y` /
  `pl_handler.c` / `pl_comp.c` (plpgsql's parser); SQL-statement
  strings inside plpgsql.
- `knowledge/subsystems/utils-cache.md` — function plan caching.
- `knowledge/subsystems/tcop.md` — DDL / CREATE FUNCTION dispatch.

**4. Has this been tried?** **YES — this is the critical reframe.**
- **Out-of-tree extension hit (per §4 extension-reframe rule):**
  the **`plpgsql_check`** extension by Pavel Stěhule is widely
  used and mature. Provides `plpgsql_check_function`,
  `plpgsql_check_function_tb`, profiler, tracer. Packaged in
  Debian, RHEL, pgdg [unverified — repo:
  github.com/okbob/plpgsql_check].
- Per the **extension-already-exists Anti-pattern**: the
  brainstorm pivots from "what would it take" to "upstream into
  core vs harden the extension vs move to contrib". The first
  DECISION: in §7 surfaces this — see Anti-patterns §.
- CommitFest: `WebFetch
  https://commitfest.postgresql.org/?text=plpgsql_check` —
  recurring discussion of "tighter plpgsql validation at CREATE
  time"; consensus has tended to be "the extension does this; if
  you want it, install it" [unverified].
- git log: the existing `check_function_bodies` GUC +
  `pl_handler.c:plpgsql_validator` hook is the EXISTING surface
  the extension uses. A hook already exists; the question is
  what runs in it.
- Corpus: `parser-and-rewrite.md` covers plpgsql parsing.
- **Scenarios layer**: composition would be `add-new-extension`
  (#30, IF moving to contrib) ∪ `add-new-guc` (#21, switch like
  `plpgsql_extra_checks`). **Scenarios gap**: "promote a
  contrib feature into core" — not really a scenario, more a
  project-process question. Don't flag — one-off, not recurring.

**5. Candidate approaches.**

Distinctness check: A and C share owning subsystem (plpgsql) but
differ on user-visible surface (in-core checks vs ship-extension);
B differs on subsystem (hooks framework) and surface (no checks
in core, just better APIs). Three genuinely distinct directions.

**A. Ship the extension's behavior as opt-in core checks.** GUC
`plpgsql_validation_level = basic | strict | paranoid` (or
extend existing `plpgsql.extra_warnings`); copy a curated subset
of `plpgsql_check`'s analyses into `pl_handler.c:plpgsql_validator`;
CREATE FUNCTION emits warnings (or errors at strict level).
- Pros: in-tree without `CREATE EXTENSION`; benefits long tail
  of users who never install extensions; existing
  `check_function_bodies` + validator hook is the right surface.
- Cons: extension's surface is large and evolves quickly —
  what we copy goes stale; maintenance burden on -hackers; bikeshed
  on "which checks are good defaults".
- Scope: medium (~10-20 files: pl_comp.c, pl_exec.c validator
  path, new GUC, new error categories, docs, big test surface).
- Reuses: existing `plpgsql_validator` hook +
  `check_function_bodies` GUC.

**B. Don't upstream the analyses; ship the extension's missing
primitives as core hooks / exported APIs.** Survey what
`plpgsql_check` has to monkey-patch or re-parse; ship those as
hooks. Extension becomes a thinner adapter.
- Pros: maintains the extension boundary; extension is already
  in distros; durably improves the platform for any future
  plpgsql tool.
- Cons: doesn't help users who don't install extensions; needs
  Pavel-engagement on -hackers; hard to know *which* hooks to add
  without co-design.
- Scope: small-medium (depends on what's missing — could be 2-3
  hook exports + SPI / cache invalidation primitive).
- Reuses: existing hook framework + `_PG_init`.

**C. Ship the extension as a contrib module.** Move
`plpgsql_check` (with Pavel's consent + licensing) into
`contrib/plpgsql_check/`. No core changes.
- Pros: trivially solves "users don't install extensions"
  because contrib ships in `postgresql-contrib` packages; no
  API design needed; Pavel keeps maintaining.
- Cons: contrib has a higher bar than out-of-core; license +
  governance question; the extension is large; this is a
  community-process question more than technical.
- Scope: small technically (file move + Makefile/meson + packaging);
  large socially.
- Reuses: contrib infrastructure (scenario #30).

**6. Recommended approach.** **B (export better hooks).** The
extension exists, is mature, is already packaged. Forcing core
to track its surface (A) is a long-term maintenance trap. Moving
to contrib (C) is politically cleanest but doesn't solve any
technical problem — it's a packaging question, decided by Pavel
+ packagers, not by feature design. B *durably* improves the
platform for all plpgsql-tooling.

For A to win: user / community decides "having to install an
extension" is itself the problem AND a curated core subset is
worth the maintenance burden. For C to win: Pavel agrees AND the
contrib bar question is answered yes.

**7. Decisions for the user.**
- DECISION: **Are you aware that `plpgsql_check` (Pavel Stěhule's
  extension) already covers ~80% of this? Does it not meet your
  need, and if so, why?** *(Surfacing per Anti-patterns
  rule — if §4 found a mature out-of-tree extension, this
  ranks first.)*
- DECISION: Is the goal "ship checks to every PG user" (favors A
  or C) or "give extension authors better tools" (favors B)?
- DECISION: If A — which checks are the MVP core set?
  `plpgsql_check` has dozens; the bar for "default on" is high.
- DECISION: If C — is moving an externally-maintained extension
  into contrib a path you'd want to drive with Pavel + packagers?
  (Process-heavy.)
- DECISION: How errored is the "wrong" code today — warnings,
  errors, or both? Are existing `plpgsql.extra_warnings` /
  `plpgsql.extra_errors` GUCs enough surface already?

**8. What this brainstorm did NOT figure out.**
- Exact extension API surface that B would need.
- The list of checks the extension provides (Phase 2 source
  read).
- Compatibility with PL/Perl, PL/Python (out-of-scope?).
- Whether `check_function_bodies` GUC is the right surface or
  needs a sibling.
- Test surface enumeration.

Run `/pg-plan plpgsql_static_check` after the DECISION: questions
— particularly the first one, because the answer reframes which
approach is even on the table.

### baseline answer

`plpgsql_check` is a thing — Pavel Stěhule maintains it as an
extension. It does thorough static analysis. So before brainstorming
from scratch: do you want to upstream what exists, or build new?

Approaches:
- Add static analysis to `plpgsql_validator` in `pl_handler.c`
  when `check_function_bodies` is on.
- Add it as a separate GUC like `plpgsql_extra_checks`.
- Move plpgsql_check into contrib.

First is most invasive; third is lightest if licensing / governance
work out. Open: which checks in scope, warnings or errors, whether
to also handle PL/Perl etc.

Main thing to flag: this functionality basically exists already —
pick "make extension easier to install" vs "ship subset in core"
before designing.
