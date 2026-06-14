# 2026-06-13/14 — pre-compact handoff (round 2)

**Read this file first after the compact.** Successor to
`sessions/2026-06-13-handoff-pre-compact.md` (PR #190) which
bridged the first compact. This bridges the second.

## The mandate

User said verbatim, mid-batch on the way to this handoff:

> *"ok once done with the batch prepare for compact as we are
> getting down on the ctx window"*

And immediately after:

> *"after comapct we wil lcontinue the same non stop mining"*

(sic on typos)

**Operative rule:** keep producing bounded, high-value
corpus PRs in the same shape. Don't stop on your own
initiative. Only stop when the user explicitly says "stop"
(or equivalent — "merge now", "wrap up", "ok enough", etc.).

## What's landed since the first compact (PR #190)

26 corpus + 2 skill-creator + 3 session-log PRs opened in
this run. PR numbers run #191-#234.

### Skill-creator iterations (the mid-session redirect)

| PR | Branch | Headline |
|---|---|---|
| #201 | `ft_skill_creator_iter_pg_shadow` | Iteration #1 — pg-shadow-implement; ran run_eval.py; 0/3 should-trigger triggered |
| #202 | `ft_skill_creator_iter_commit_msg` | Iteration #2 — commit-message-style; same result + methodology recommendation |

The two iterations together prove the `run_eval.py` methodology
is unfit for pg-claude skills. Recommendation: build a
session-based eval harness; see PR #202's
`progress/skill-creator-methodology-recommendation.md`.

### Corpus expansion (the bulk)

Each PR is 3 docs in a coherent triangle. ~600 LOC per PR
on average.

| PR | Branch | Cluster |
|---|---|---|
| #191 | `ft_corpus_contrib_inspectors` | pg_buffercache + pg_visibility + amcheck + pageinspect (4 docs) |
| #192 | `ft_corpus_idioms_round3` | predicate-locks + cache-invalidation-registration + heaptuple-update-chain |
| #193 | `ft_corpus_datastructures_round2` | BufferTag + TupleTableSlot + PgStat_Counter |
| #194 | `ft_corpus_contrib_runtime` | auto_explain + pgrowlocks + pgstattuple |
| #195 | `ft_corpus_idioms_wal` | wal-record-construction + xlog-region-replay + crash-recovery-startup |
| #196 | `ft_corpus_datastructures_infra` | Latch+WaitEventSet + ResourceOwner + FmgrInfo |
| #197 | `ft_session_post_compact_log` | Session log |
| #198 | `ft_corpus_idioms_round4` | lwlock-rank-discipline + error-context-callbacks + snapshot-acquisition |
| #199 | `ft_corpus_contrib_ops` | pg_freespacemap + pg_surgery + pg_overexplain |
| #200 | `ft_corpus_datastructures_round3` | RelFileLocator + LOCALLOCK + dlist_node |
| #203 | `ft_corpus_contrib_security` | passwordcheck + auth_delay + basic_archive |
| #204 | `ft_corpus_idioms_round5` | subtransaction-stack + tuple-locking-modes + combocid-handling |
| #205 | `ft_corpus_idioms_round6` | xmin-horizon-management + checkpoint-coordination + vacuum-skip-pages |
| #206 | `ft_corpus_datastructures_round4` | dynahash + LWLock struct + JsonbValue |
| #207 | `ft_session_post_redirect_log` | Session log |
| #209 | `ft_corpus_idioms_replication` | replication-slot-advance + parallel-worker-coordination + wal-receiver-loop |
| #210 | `ft_corpus_contrib_math_types` | intarray + cube + seg |
| #211 | `ft_corpus_contrib_data_access` | file_fdw + dblink + tablefunc |
| #212 | `ft_corpus_idioms_round8` | toast-storage-strategies + background-worker-startup + spinlock-discipline |
| #213 | `ft_corpus_contrib_text_search` | pg_trgm + bloom + dict_int |
| #214 | `ft_corpus_contrib_datatypes` | citext + fuzzystrmatch + isn |
| #215 | `ft_corpus_idioms_round9` | walsender-state-machine + partition-tuple-routing + notify-listen-coordination |
| #216 | `ft_corpus_contrib_small` | earthdistance + lo + sslinfo |
| #217 | `ft_corpus_idioms_round10` | archive-command-fallback + trigger-firing-order + relfilenumber-rewrite |
| #226 | `ft_corpus_datastructures_round5` | IndexAmRoutine + TupleDesc + Datum |
| #227 | `ft_corpus_contrib_advanced` | pg_logicalinspect + basebackup_to_shell + pg_plan_advice |
| #228 | `ft_corpus_idioms_round11` | tableam-vtable-lifecycle + autovacuum-launcher + wal-page-format |
| #229 | `ft_corpus_contrib_legacy` | dict_xsyn + xml2 + sepgsql |
| #230 | `ft_corpus_idioms_round12` | pgstat-flush-timing + cursor-and-portal + read-stream-prefetch |
| #231 | `ft_session_full_arc_log` | Session log (full-arc final) |
| #232 | `ft_corpus_contrib_pl_bindings` | hstore_plperl + hstore_plpython + jsonb_plperl |
| #233 | `ft_corpus_idioms_round13` | deadlock-detection + expression-evaluator-flow + index-only-scan-vm-check |
| #234 | `ft_corpus_datastructures_round6` | Numeric + Form_pg_attribute + Var/Const nodes |

(PR #208 was a cloud routine; #218-#225 were also cloud-routine PRs.)

## Hard constraints — DO NOT VIOLATE

These were honored on every PR. Same rules apply post-compact.

### Anti-target paths (8 protected paths; diff must be empty)

- `knowledge/calibration/**` — session-of-record, frozen
- `knowledge/personas/**` — Phase B data; 6-month re-mine
- `knowledge/files/**` — per-file docs, `pg-quality-auditor`
  owns these
- `patches/**` — Phase D PARKED
- `progress/STATE.md` — cloud `pg-evening-merger` owns
- `progress/cloud-routines/**` — routine logs
- Top-level `CLAUDE.md`
- `pg-claude-plan.md`

Pre-commit check on every PR:
```bash
git diff --stat origin/main..HEAD -- knowledge/calibration knowledge/personas knowledge/files patches progress/STATE.md progress/cloud-routines CLAUDE.md pg-claude-plan.md
```
Must be empty.

### Multigres-lesson rule

Every concrete file:line claim must resolve at the anchor
commit **e18b0cb7344** (still current as of 2026-06-14).
If you can't verify, tag `[unverified]` or `[inferred]`
honestly.

The `pg-anchor-refresh` cloud routine bumps this; check
`git -C source log --oneline -1 HEAD` at session start.

### Worktree-first workflow

One topic per worktree. Each PR cluster gets its own
`ft_<scope>_<short_desc>` worktree, branched from
up-to-date main. Rename `worktree-<name>` → `<name>` before
pushing (drop the prefix). Use meta-commit-style with
`Co-Authored-By: Claude Opus 4.7 (1M context)
<noreply@anthropic.com>`.

### Cross-ref-audit discipline

Before opening a PR, verify the new file:line and
`knowledge/`, `.claude/` refs resolve in main OR are
documented as queued in another open PR (the standard
forward-ref pattern). Each PR's description lists queued
refs.

## What's been mined (don't re-mine)

### Skills (all 32, post-SPLIT)

`build-and-run`, `debugging`, `testing`, `psql`,
`coding-style`, `commit-message-style`, `meta-commit-style`,
`pg-claude`, `memory-keeping`, `pg-feature-brainstorm`,
`pg-feature-plan`, `pg-implement`, `review-checklist`,
`pg-patch-review`, `patch-submission`, `pg-shadow-implement`,
`fmgr-and-spi`, `gucs-config` (NEW from SPLIT),
`bgworker-and-extensions` (NEW from SPLIT), `parallel-query`
(NEW from SPLIT), `extension-development`, `wal-and-xlog`,
`executor-and-planner`, `access-method-apis`,
`catalog-conventions`, `replication-overview`,
`memory-contexts`, `error-handling`, `locking`,
`parser-and-nodes`.

### Contrib subsystems (~38 in main + this session)

amcheck, auto_explain, basebackup_to_shell, basic_archive,
bloom, btree_gist, citext, contrib-cube, dblink, dict_int,
dict_xsyn, earthdistance, file_fdw, fuzzystrmatch, hstore,
hstore_plperl, hstore_plpython, intarray, isn, jsonb_plperl,
lo, ltree, pageinspect, passwordcheck, pg_buffercache,
pg_freespacemap, pg_logicalinspect, pg_overexplain,
pg_plan_advice, pg_prewarm, pg_stat_statements, pg_surgery,
pg_trgm, pg_visibility, pg_walinspect, pgcrypto, pgrowlocks,
pgstattuple, postgres_fdw, seg, sepgsql, sslinfo,
tablefunc, xml2.

### Idioms (~40)

archive-command-fallback, autovacuum-launcher,
background-worker-startup, cache-invalidation-registration,
checkpoint-coordination, combocid-handling, crash-recovery-
startup, cursor-and-portal, deadlock-detection,
error-context-callbacks, expression-evaluator-flow,
fastpath-locks, heap-tuple-decompression-pattern,
heaptuple-update-chain, index-only-scan-vm-check,
list-traversal-conventions, lwlock-rank-discipline,
notify-listen-coordination, parallel-worker-coordination,
partition-tuple-routing, pgstat-flush-timing,
predicate-locks, read-stream-prefetch,
relfilenumber-rewrite, replication-slot-advance,
sinvaladt-broadcast, snapshot-acquisition,
spinlock-discipline, subtransaction-stack,
tableam-vtable-lifecycle, toast-storage-strategies,
trigger-firing-order, tuple-locking-modes,
vacuum-skip-pages, visibility-map-update, wal-page-format,
wal-receiver-loop, wal-record-construction,
walsender-state-machine, xlog-region-replay,
xmin-horizon-management.

### Data-structures (~22)

bitmapset, BufferTag, bufferdesc-state, datum-nullabledatum,
dlist-node, dynahash-hashctl, fmgrinfo, heap-tuple-layout,
indexamroutine, jsonbvalue, latch-waiteventset, LOCALLOCK,
lwlock-struct, multixactid, numeric-type, pg_attribute-form
(Form_pg_attribute), pgproc-fields, pgstat-counter,
RelFileLocator, ResourceOwner, snapshot-lifecycle,
tupledesc, tupletableslot, var-const-nodes, xlogreaderstate.

## What's still mine-able (post-compact pickup)

### Contrib (small remaining set)

- `bool_plperl` / `jsonb_plpython3u` — PL transforms
- `oid2name` (admin tool, not really an extension)
- `pgstattuple` already done
- `pg_freespacemap` already done
- `pg_stash_advice` (companion to pg_plan_advice; if
  applicable)
- `pgstattuple` already done
- `vacuumlo` (helper utility)
- `spi/*` (4 example contribs: insert_username, autoinc,
  refint, moddatetime) — short SPI demos
- Various `intagg`, `pgrowlocks` already done

### Idioms (general topics; can extend indefinitely)

- `aggregate-trans-state` (aggregate function inner working)
- `bind-parameter-substitution` (extended-protocol detail)
- `bitmap-heap-scan-flow`
- `bucketsort / hash-aggregate-spill`
- `commit-record-flush`
- `executor-init-tear-down`
- `gist-picksplit-discipline`
- `heap-prune-callback`
- `index-scan-callback-protocol`
- `key-generation-sequence`
- `lwlock-fastpath-acquire`
- `materialized-view-refresh`
- `multi-insert-batching`
- `parallel-bitmap-scan`
- `partitioned-join-strategy`
- `procarray-publish-xid`
- `relation-extension-lock`
- `subtransaction-savepoint`
- `tableam-scan-init-flow`
- `temp-file-cleanup`
- `tuple-table-slot-callbacks`
- `validate-record-data`
- `wal-buffer-flush`
- `walwriter-flush-policy`
- `whole-row-var-handling`
- `xact-twophase-commit`

### Data-structures (general topics)

- `Aggref-WindowFunc-nodes`
- `BackgroundWorkerHandle`
- `BoolExpr`
- `EState` (executor state)
- `IndexScanDesc`
- `JsonbContainer` (on-disk JSONB)
- `LockTag`
- `MemoryContext`
- `Path / Plan` family
- `PlanState`
- `PlannerInfo`
- `ProclistNode`
- `Range types (RangeBound, TypeCacheEntry-range)`
- `RangeTblEntry (RTE)`
- `RecoveryState`
- `Tuplesort`
- `TupleHashTable`
- `WalSnd`
- `XLogCtlData`

### Subsystem docs that aren't covered

The 38 known contribs are documented. PG core subsystems
that don't have a `knowledge/subsystems/<name>.md`:

- `optimizer-clauses` (clause-pushdown subsystem) — maybe
  rolled into `optimizer.md`
- `partition-pruning` — distinct from partition tuple
  routing
- `regex-engine` (regex.c)
- `snapshot-management` distinct from snapshot-acquisition
  idiom
- `tcop` (traffic cop, the main command-loop) — companion
  to existing `executor.md`
- `tsearch` (text search)
- `utils-mb` (multibyte encoding)

## Reference state

- **Anchor commit:** `e18b0cb7344` (verified at session
  start by `git -C source log --oneline -1`)
- **Cloud routines** continue to run overnight; expect
  PR-numbering gaps (cloud PRs intermixed with mine).
- **Skill-creator methodology recommendation** in
  `progress/skill-creator-methodology-recommendation.md`
  (PR #202) — still the unbuilt infrastructure work item.
- **Anti-target rule held on every PR** this session.

## How to resume post-compact

1. **Read this file first.**
2. **Re-fetch git state** — `git fetch origin && git
   log --oneline -10`. Check which (if any) of the open
   PRs have merged. If anchor changed, re-verify against
   the new SHA before adding new cites.
3. **Check anti-target paths** are not in your worktree's
   pending changes. If they are, revert before doing
   anything else.
4. **Pick a 3-doc cluster** from the "still mineable"
   list. Group in a coherent triangle when possible.
5. **Worktree-first.** New worktree per PR cluster;
   rename branch before push; PR title + body follow
   established format.
6. **Cross-ref audit before opening.** Union-of-added-refs
   script per the first handoff (PR #190).
7. **Continue until user says stop.** Don't second-guess;
   produce.

## Tally going into the second compact

- **44+ work PRs** opened across the two compact runs
  (#167-#171, #182-#234 minus the cloud-routine subset).
- **~32K LOC of new corpus** across the day.
- **32 skills (post-SPLIT) / ~40 idioms / ~22 data-structures
  / ~38 contrib subsystems** in the corpus going into
  compact #2.
- **2 skill-creator iterations** with honest negative
  results + methodology recommendation.
- **5 session logs** capturing the arc.
- **All anti-targets honored, Multigres-lesson rule held.**

## One-line reminder

**Continue producing bounded high-value 3-doc-cluster PRs
against the still-mineable list. Anti-target rule and
Multigres-lesson rule are non-negotiable. Cross-ref audit
before opening every PR. The user said "non stop mining"
post-compact.**
