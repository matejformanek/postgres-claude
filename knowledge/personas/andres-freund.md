# Persona: Andres Freund

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (read-only clone). Cross-cut against
  `knowledge/personas/committer-map.md`, `contributor-map.md`,
  `domain-ownership.md`. No external network calls.

## Role + email(s)

- **Primary identity:** `Andres Freund <andres@anarazel.de>` (committer + author).
- **Affiliation hint:** historical work for Citus / Microsoft (not asserted from
  log; visible in older trailers — `[inferred]`, do not state in reviews).
- **Lifetime commits as committer:** 1548 (`git rev-list --count --committer='Andres Freund'`).
- **Lifetime commits as author (%an):** 3 only — Andres is overwhelmingly a
  *committer* of his own and others' work, with author credit recorded in
  `Author:` / `Co-authored-by:` trailers in the body, not in the `%an` field.

## Activity profile (last 24mo)

Window: 2024-06-11 .. 2026-06-11.

| Metric | Value | Source |
|---|---:|---|
| Commits as committer (24mo) | 227 | `rev-list --count --since='24 months ago' --committer=...` |
| Commits as committer (12mo) | 107 | same, 12mo window |
| `Reviewed-by:` trailers crediting him (24mo, tree-wide) | 237 | `grep -ci '^reviewed-by:.*andres'` over all 24mo commits |
| `Reported-by:` trailers (24mo) | 50 | same approach |
| `Tested-by:` trailers (24mo) | 3 | same |
| `Author:` / `Co-authored-by:` trailers (24mo) | 30 | same |
| Commits with `Discussion:` URL (24mo, his) | 259 occurrences across 227 commits | every commit has at least one, many have several earlier-version threads |
| Commits referencing back-branch / backpatch (24mo, his) | 31 (~14%) | `grep -ci 'backpatch-through\|back-branch\|back-patch'` |
| Avg body length (lines) | 16.2 | longest 92 lines (the AIO infrastructure commit) |

Reads as: he commits less than the broad maintainers (Michael Paquier,
Peter Eisentraut, Tom Lane all >600 in 24mo) but reviews very heavily (237
review credits = roughly 1 review per active calendar day). Body length is
~2-3× the tree median because most commits carry multi-paragraph rationale.

## Domain ownership

Path footprint, 24mo (depth-3 buckets, top by file-touches):

```
195 src/backend/storage      ← dominant. buffer manager, AIO, smgr.
 75 src/include/storage      ← matched header churn.
 49 src/test/modules         ← test_aio, test_bufmgr, etc.
 43 src/backend/utils        ← instrumentation (TSC), GUC, memdebug.
 40 src/backend/access       ← heapam, hash kill_prior_tuples.
 27 doc/src/sgml             ← docs only when adding GUCs / behavior.
 26 src/backend/postmaster   ← postmaster startup, latches.
 22 src/backend/executor     ← instrumentation hooks for EXPLAIN.
 19 src/tools/pgindent       ← typedef list maintenance.
 10 src/tools/ci             ← CI infrastructure (Cirrus → GH Actions).
```

[verified-by-code] He owns three things on master right now:

- **Asynchronous I/O (AIO) subsystem.** The core infrastructure landed
  `da72269` "aio: Add core asynchronous I/O infrastructure" (2025-03-17, body 92
  lines — the longest in the 24mo window). All `aio:` prefixed commits (33 in
  24mo) are his. `src/backend/storage/aio/*` is essentially his module.
- **Buffer manager evolution.** `bufmgr:` prefix appears 34 times in 24mo,
  including `fcb9c977aa5` "bufmgr: Implement buffer content locks independently
  of lwlocks" (1036 lines, 2026-01-15) and `dac328c8a68` "bufmgr: Change
  BufferDesc.state to be a 64-bit atomic". This is structural rework feeding
  AIO, not incremental fixes.
- **CI infrastructure.** All `ci:` prefix commits (19 in 24mo) are his.
  `9c126063b19` "ci: Add GitHub Actions based CI" (1272 LOC added) is the most
  recent landmark — Cirrus CI shut down 2026-06-01 and he led the migration.
- **EXPLAIN instrumentation low-level path.** `instrumentation:` prefix (10
  commits in 24mo) — moving query-level instrumentation to use x86 TSC instead
  of `clock_gettime()`. `294520c4448` is the umbrella commit (~626 lines).

## Style + patterns

Inferred from his own commits (see Landmark commits §) and the bodies sampled
above:

- **Lowercase `area:` prefix on subjects.** Distinctive on master.
  `bufmgr:`, `aio:`, `ci:`, `meson:`, `postmaster:`, `instrumentation:`,
  `localbuf:`, `read_stream:`, `lwlock:`, `heapam:`. Even when other committers
  send patches in this area, his commits keep the lowercase prefix.
  `[verified-by-code]` — see subject prefix histogram in this file's mining
  notes; 121 of his 227 commits in 24mo use this form.
- **Multi-paragraph rationale, often numbered.** Long commits open with `1) 2)
  3) 4)` enumerated motivations. `fcb9c977aa5` opens with four numbered points
  explaining *why* content locks need to leave lwlock infrastructure. `da72269`
  opens with `a) b)` enumerated motivations for AIO. `[verified-by-code]`.
- **`Discussion:` URL on essentially every commit.** 259 occurrences across 227
  commits — sometimes two URLs (current thread + an "in an earlier version"
  reference). Skipping `Discussion:` is unusual enough to look at twice.
  `[verified-by-code]`.
- **Self-review credit.** He frequently lists himself as both `Author:` *and*
  `Reviewed-by:` on the same commit (`294520c4448`, `999dec9ec6a` both do
  this). This is the multi-author "co-developed and cross-reviewed" pattern,
  not vanity. `[verified-by-code]`.
- **"in an earlier version" trailer suffix.** Distinctive: when a reviewer
  signed off on v1-v8 of a series but did not re-review the final, he records
  it as `Reviewed-by: <name> (in an earlier version)`. Visible in
  `294520c4448`. `[verified-by-code]`.
- **Followup commits flagged in subject.** `6c7bce28c83` "Fixups for
  a4f774cf1c7" — when a small fix follows up a recent push he names the
  predecessor SHA in the subject line. `[verified-by-code]`.
- **Body explains the "why we cannot just do X" failure mode.** `c0af4eb4e71`
  "bufmgr: Fix ordering of checks in PinBuffer()" reads as "the check was added
  in 819dc118c0f6 at the start of the loop; in theory CAS allows that; however
  there's a `WaitBufHdrUnlocked(buf)` immediately after which introduces a race"
  — narrating exactly why the obvious version is wrong. `[verified-by-code]`.

## Common reviewer / collaborator partners

Reviewers of his commits (24mo, his commits only):

```
 42 Noah Misch              — durability + correctness backstop
 34 Melanie Plageman        — read stream + vacuum work
 25 Andres Freund           — self (during multi-author commits)
 23 Nazir Bilal Yavuz       — CI + AIO contributor pair
 23 Heikki Linnakangas      — storage + shmem + WAL reviewer
 14 Tom Lane                — design / code quality reviewer
  9 Bertrand Drouvot        — pgstat + lwlock work
  7 Matthias van de Meent   — buffer mgr + index work
  5 Thomas Munro            — read stream + AIO worker mode
  4 Robert Haas             — design reviewer
```

Co-authors on his commits (24mo):

```
 19 Andres Freund           — self (multi-author conventions)
 17 Nazir Bilal Yavuz       — CI co-driver + AIO contributor
 14 Lukas Fittl             — TSC / instrumentation work
  8 Thomas Munro            — read stream + AIO worker mode
  8 Melanie Plageman        — read stream + vacuum
  4 David Geier             — instrumentation (TSC)
  3 Noah Misch
  2 Jelte Fennema-Nio       — CI
```

The pairings cluster into three working groups:

1. **AIO / read-stream loop:** Thomas Munro, Melanie Plageman, Nazir Bilal Yavuz
   recur as both co-authors and reviewers.
2. **CI migration:** Nazir Bilal Yavuz + Jelte Fennema-Nio co-drove the GH
   Actions cutover.
3. **Storage correctness reviewer pair:** Noah Misch + Heikki Linnakangas — the
   two voices that catch race-window bugs in his buffer-mgr rework.

## What to expect on a patch he would review

- **He will not accept lack of motivation.** If your commit message is one line
  and the diff is non-trivial, expect a request to explain the *why* in the
  body, ideally numbered. His own commits set the bar.
- **Race-window reasoning, with citations to lines.** He reads atomic / lock
  paths very carefully and will quote the specific `WaitBufHdrUnlocked()` /
  `CAS` ordering that breaks. Pre-empt this by spelling out, in the body, why
  the obvious cheaper variant has a race.
  Example: `c0af4eb4e71` (PinBuffer ordering fix).
- **Will push back on patches that walk into AIO/bufmgr without reading
  recent BufferDesc / `state` rework.** `dac328c8a68` widened BufferDesc.state
  to a 64-bit atomic; `fcb9c977aa5` then moved content locks into bufmgr. If a
  patch still treats those as a small `state` + LWLock pair, expect a rebase
  request.
- **Will surface BSD / Windows / DIO portability if your patch added a syscall
  or a memory-mapping path.** AIO infrastructure is portability-sensitive; he
  has io_uring (Linux), worker (cross-platform), and sync paths to keep aligned.
- **Will ask for a `Discussion:` URL.** Tree-wide his own commits hit ~100% on
  this trailer. Expect the same on a patch he ushers in.

## Landmark commits (last 12mo)

1. **`9c126063b19` ci: Add GitHub Actions based CI** (2026-06, 1272 LOC added).
   Migration off Cirrus CI after Cirrus shutdown 2026-06-01. Three named
   `Author:` co-authors (Yavuz, Freund, Fennema-Nio) plus four reviewers. Body
   enumerates which OS/build matrix tasks are covered and what is intentionally
   left for later (BSD). Shows the "explain what is intentionally NOT done"
   discipline.
2. **`fcb9c977aa5` bufmgr: Implement buffer content locks independently of
   lwlocks** (2026-01, ~1036 LOC). Decoupling content locks from lwlocks to
   unblock AIO writes. Body opens with four numbered motivations including
   "btrfs internal checksums" as a concrete failure case.
3. **`da72269` aio: Add core asynchronous I/O infrastructure** (2025-03,
   ~92-line body — longest in window). Lays down the AIO target/callback
   abstraction with explicit "no AIO targets in this commit, smgr target in a
   later one" — illustrates his preferred slicing of a large feature into
   reviewable units.
4. **`82467f627bd` Require share-exclusive lock to set hint bits and to flush**
   (12mo, 712 LOC). Precondition for the content-lock decoupling above —
   reordering hint-bit semantics so concurrent flush does not need a page copy.
5. **`294520c4448` instrumentation: Use Time-Stamp Counter on x86-64 to lower
   overhead** (12mo, ~626 LOC). Adds `timing_clock_source` GUC with `auto` /
   `system` / `tsc`. Body cites concrete benchmark numbers ("2x as slow → 1.2x
   as slow", "~20% gains on TPCH") — quantitative justification is part of
   his commit-body style.

## Notes / hedges

- **Heads-up on the committer-map number:** the 24mo count there (227) is
  the *committer* count, not author count. Andres almost never appears as
  `%an` (3 lifetime commits) because PG records author credit in trailers.
  This is the canonical "committer-vs-author" gotcha called out in
  committer-map.md §"Important caveat" — Andres is the cleanest example of it.
- **AIO ownership is not absolute.** Thomas Munro is the closest collaborator
  (read stream API) and Melanie Plageman drove the heap-AM and vacuum
  integrations. On AIO-touching patches, a CC to all three is appropriate.
  `[verified-by-code]` — co-author counts above.
- **Backpatch frequency (~14%) is below the bulk-maintainers' rate.** His work
  is mostly master-only restructuring. Don't assume a fix from him will be
  backpatched; he tags `Backpatch-through:` explicitly when it is.
  `[verified-by-code]`.
- **The "Andres reviews more than he commits" pattern.** 237 `Reviewed-by:`
  credits vs 227 own commits in 24mo. Treat any AIO/bufmgr/storage patch as
  likely to land through his review even if it is committed by someone else.
  `[verified-by-code]`.
