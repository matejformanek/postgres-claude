# Persona: Heikki Linnakangas

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (commit bodies parsed for trailers, subjects scanned for prefix patterns, paths bucketed by subsystem) + cross-cut against `committer-map.md`, `contributor-map.md`, `domain-ownership.md`. No mailing-list archives.

## Role + email(s)

- Role: committer (active 24mo), core team member.
- Primary email: `heikki.linnakangas@iki.fi` — single identity.
- Lifetime committer rank: **#8** (1,890 lifetime commits — see `committer-map.md`).
- Identity rollups: none.

## Activity profile (last 24mo: 2024-06-11 .. 2026-06-11)

| Trailer | Count |
|---|---:|
| Commits authored (`%an` as committer) | 292 |
| Commits w/ `Discussion:` URL | 267 (91%) |
| Commits w/ `Backpatch-through:` | 50 (17%) |
| Reviewed-by trailer appearances (any commit) | 113 |
| Reported-by | 10 |
| Author trailer appearances | 7 |
| Co-authored-by | 5 |
| Other (Suggested + Tested + Diagnosed) | 5 |
| **Total trailer appearances** | **135** |

Self-authorship on his pushed commits: only **1 explicit `Author: Heikki Linnakangas`**, 219 with no Author trailer, 72 with someone else as Author. **Almost never self-tags** — strongest "no self-Author trailer" convention of any committer in this set.

Cross-verified against `contributor-map.md` row "Heikki Linnakangas | 7 | 113 | 10 | 5 | 135".

12mo / 24mo split: 154/292 ≈ 53% — steady cadence (slightly accelerating in 12mo).

## Domain ownership

From `domain-ownership.md` per-subsystem leadership (24mo):

- `src/backend/postmaster/` — **top committer** (38 commits, ahead of Nathan Bossart 24).
- `src/backend/tcop/` — **top committer** (20 commits, ahead of Michael Paquier 14 and Peter Eisentraut 12).
- `src/backend/storage/` — second top (82 commits, behind Andres Freund 109). The new shmem-allocation API rework is his.
- `src/backend/access/` — top-5 (51 commits, behind Michael Paquier 101, Peter Geoghegan 87, Melanie Plageman 83).
- `src/backend/utils/` — top-5 (55 commits).
- `src/include/` — top-4 (97 commits).
- `src/include/storage/` — heavy contribution (80 file-touches).

**Read:** Heikki's profile is the **deep-internals one** in this set. His path histogram is dominated by `src/backend/storage/` (148), `src/backend/access/` (81), `src/include/storage/` (80), `src/backend/utils/` (73), and `src/backend/postmaster/` (70). Compared with Tom (everywhere) or Michael (everywhere), Heikki is concentrated in the **bottom-of-the-stack** — buffer manager, shmem, WAL, latches, the things that run before/below SQL parsing.

Featured 12mo work: the **new shmem allocation API** (`9b5acad3f40`, `2e0943a8597`, `283e823f9dc`, `c6d55714ba4`, `6ef9bee2931` — five commits in one week in April 2026) is one of the most substantial refactors of the cycle. Also the **MultiXactOffset widening to 64 bits** (`bd8d9c9bdfa`, Dec 2025) — a large correctness-driven change.

## Style + patterns

### Commit message style

Subject prefix histogram (top 10):

| Prefix | Count |
|---|---:|
| `Fix ...` | 70 |
| `Add ...` | 24 |
| `Use ...` | 21 |
| `Remove ...` | 19 |
| `Make ...` | 11 |
| `Refactor ...` | 10 |
| `Move ...` | 10 |
| `Don't ...` | 8 |
| `Replace ...` | 7 |
| `Convert ...` | 7 |

- **`Refactor ...` and `Convert ...` prefixes** are unusual — Heikki uses them more than other committers (Tom has neither in his top 20). Reflects his focus on internal-API rework.
- Subject length: 51.9 chars (close to Tom's 56).
- Mostly bare imperative, less tool-prefix tagging than Michael or Nathan (no `psql:`, no `pg_upgrade:`).

### Body conventions

`%B` mean ≈ 13.3 lines / commit, **median = 11 lines**. Middle of the pack. Bodies typically:

1. Brief context (what's wrong / what's missing).
2. The mechanism (how the change works).
3. Trailer block.

Spot-read of the shmem rework commit (`283e823f9dc` "Introduce a new mechanism for registering shared memory areas"): body explains the *why* (existing API limitations), the *what* (new RegisterNamedDSA / RegisterNamedDSH primitives), and references the follow-up commits that convert callers. This is the "design-rationale" body — somewhere between Tom's narrative style and Peter's terse style.

### Discussion: URL discipline

**91% of his commits cite a `Discussion:` URL** (267/292). Strong norm adherence.

### Backpatch behavior

**17% backpatch rate** (50/292) — slightly below the project-wide ~18%. Backpatch examples in 24mo include "Fix integer overflow in array_agg(), when the array grows too large", "Don't try to record dependency on a dropped column's datatype", "Avoid orphaned objects dependencies" — these are durability/correctness fixes that must propagate.

### Author-trailer pattern (self-tagging avoidance)

Only **1 commit** in 24mo carries `Author: Heikki Linnakangas` — the strongest "I don't self-tag" pattern in PG. He follows the convention "if I'm committer and the patch was substantially mine, no Author trailer is needed."

72 commits credit someone else as Author = 25% — he is closer to Tom's authorship ratio (he's mostly committing his own work) than to Michael's (mostly others' work).

### Self-review avoidance

Per `contributor-map.md`'s pairing analysis: "**Heikki Linnakangas does NOT self-review** (his self-line is absent from his top-5). He's the cleanest 'I commit only others' patches with their reviewers' pattern." Verified here — his top 10 reviewers do not include himself.

### Refactor-heavy work pattern

Top-churn 12mo commits are dominated by **refactors and API conversions**:
- `9b5acad3f40` Convert all remaining subsystems to use the new shmem allocation API (2,135 lines).
- `bd8d9c9bdfa` Widen MultiXactOffset to 64 bits (2,131 lines).
- `2e0943a8597` Convert SLRUs to use the new shmem allocation functions (1,362 lines).
- `283e823f9dc` Introduce a new mechanism for registering shared memory areas (1,343 lines).
- `d6eba30a245` Refactor how user-defined LWLock tranches are stored in shmem.
- `17f51ea8187` Separate RecoveryConflictReasons from procsignals.

Six of his top 10 12mo commits are explicit refactors. This is **noticeably more refactor-leaning than Michael (mostly Add/Fix) or Tom (Fix-leaning)**.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md) | `src/include`, `src/backend/utils` |
| [`add-new-bgworker`](../scenarios/add-new-bgworker.md) | `src/include`, `src/backend/postmaster` (+1) |
| [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md) | `src/include`, `src/backend/utils` (+3) |
| [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md) | `src/include`, `src/backend/utils` |
| [`add-new-cast`](../scenarios/add-new-cast.md) | `src/include` |
| [`add-new-cost-model-knob`](../scenarios/add-new-cost-model-knob.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-data-type`](../scenarios/add-new-data-type.md) | `src/include`, `src/backend/utils` |
| [`add-new-error-code`](../scenarios/add-new-error-code.md) | `src/include`, `src/backend/utils` |
| [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md) | `src/include`, `src/backend/utils` |
| [`add-new-extension`](../scenarios/add-new-extension.md) | `src/include` |
| [`add-new-guc`](../scenarios/add-new-guc.md) | `src/include`, `src/backend/utils` |
| [`add-new-hook`](../scenarios/add-new-hook.md) | `src/include`, `src/backend/tcop` |
| [`add-new-index-am`](../scenarios/add-new-index-am.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-lwlock-tranche`](../scenarios/add-new-lwlock-tranche.md) | `src/include`, `src/backend/utils` (+3) |
| [`add-new-node-type`](../scenarios/add-new-node-type.md) | `src/include`, `src/backend/utils` |
| [`add-new-operator`](../scenarios/add-new-operator.md) | `src/include`, `src/backend/utils` |
| [`add-new-operator-class`](../scenarios/add-new-operator-class.md) | `src/include`, `src/backend/access` |
| [`add-new-pg-stat-view`](../scenarios/add-new-pg-stat-view.md) | `src/include`, `src/backend/utils` |
| [`add-new-plan-node`](../scenarios/add-new-plan-node.md) | `src/include`, `src/backend/utils` |
| [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md) | `src/include`, `src/backend/access` (+1) |
| [`add-new-replication-message`](../scenarios/add-new-replication-message.md) | `src/include` |
| [`add-new-shared-memory-region`](../scenarios/add-new-shared-memory-region.md) | `src/include`, `src/backend/utils` (+2) |
| [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md) | `src/include`, `src/backend/utils` |
| [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md) | `src/include`, `src/backend/utils` (+1) |
| [`add-new-system-view`](../scenarios/add-new-system-view.md) | `src/include`, `src/backend/utils` |
| [`add-new-table-am`](../scenarios/add-new-table-am.md) | `src/include`, `src/backend/access` |
| [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md) | `src/include`, `src/backend/tcop` |
| [`add-new-wal-record`](../scenarios/add-new-wal-record.md) | `src/include`, `src/backend/access` |
| [`add-startup-hook`](../scenarios/add-startup-hook.md) | `src/include`, `src/backend/postmaster` (+2) |
| [`bump-catversion`](../scenarios/bump-catversion.md) | `src/include`, `src/backend/access` |
| [`remove-from-catalog`](../scenarios/remove-from-catalog.md) | `src/include` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`access-heap`](../subsystems/access-heap.md)
- [`access-nbtree`](../subsystems/access-nbtree.md)
- [`access-transam`](../subsystems/access-transam.md)
- [`executor`](../subsystems/executor.md)
- [`foreign`](../subsystems/foreign.md)
- [`jit`](../subsystems/jit.md)
- [`libpq-backend`](../subsystems/libpq-backend.md)
- [`optimizer`](../subsystems/optimizer.md)
- [`parser-and-rewrite`](../subsystems/parser-and-rewrite.md)
- [`partitioning`](../subsystems/partitioning.md)
- [`port`](../subsystems/port.md)
- [`replication`](../subsystems/replication.md)
- [`storage-buffer`](../subsystems/storage-buffer.md)
- [`storage-ipc`](../subsystems/storage-ipc.md)
- [`storage-lmgr`](../subsystems/storage-lmgr.md)
- [`tcop`](../subsystems/tcop.md)
- [`utils-cache`](../subsystems/utils-cache.md)
- [`utils-mmgr`](../subsystems/utils-mmgr.md)

<!-- /persona-subsystems:auto -->

## Common reviewer/collaborator partners

Top reviewers credited on commits Heikki pushed (24mo):

| Reviewer | Count |
|---|---:|
| Ashutosh Bapat | 22 |
| Andres Freund | 20 |
| Chao Li | 19 |
| Matthias van de Meent | 17 |
| Daniel Gustafsson | 15 |
| Nathan Bossart | 11 |
| Tomas Vondra | 9 |
| Robert Haas | 8 |
| Peter Eisentraut | 7 |
| Sami Imseih | 6 |

**Notable:** None of the heavy-volume reviewers (Tom Lane, Michael Paquier) crack his top 10. His reviewer pool is **specialist-shifted**: Ashutosh Bapat (22), Matthias van de Meent (17), Andres Freund (20), Tomas Vondra (9) — these are storage/access/buffer-manager specialists. Reflects that his work is in the deep internals where general-purpose reviewers are less useful.

**Andres Freund (20)** — strongest pair, both work on storage + AIO + shmem. Per `contributor-map.md` Andres also has Heikki as a top-5 reviewer on Andres's commits (23 R-by). Symmetric review relationship.

**Matthias van de Meent (17)** — pure reviewer in the storage area; deep on buffer/access internals.

**Ashutosh Bapat (22)** is the #1 — heavy on storage + partitioning + regress review.

## What to expect on a patch he would review

1. **He will probe shared-memory + locking invariants.** Confidence: very high — five of his top 10 12mo commits are shmem/lwlock/SLRU rework. Patches that allocate shared memory, take LWLocks, or interact with the postmaster/shmem startup sequence will get deep review on lock-order and shmem-size-estimation.

2. **He will demand API-conversion follow-through.** Confidence: high. The shmem-API series shows he does multi-commit "introduce new API + convert all callers" patterns. Patches that introduce a new internal API but leave old callers behind will be flagged.

3. **He will check correctness on integer overflow + wraparound.** Confidence: high. The MultiXactOffset 64-bit widening, "Fix integer overflow in array_agg()", "Use palloc_array() in a few more places to avoid overflow" — recurring themes. Patches handling unbounded counters or array growth without overflow checks will be flagged.

4. **He will not push back hard on commit-message style.** Confidence: medium. Subject length 51.9 chars, bodies median 11 lines. He doesn't appear to systematically rewrite landing subjects in the way Tom does.

5. **He expects you to know the bottom-of-stack code.** Confidence: high. Patches into `storage/`, `tcop/`, `postmaster/`, `access/` arrive at him; expect questions about how the change interacts with checkpointer, the postmaster start sequence, recovery, etc. A patch with hand-wavy "this should work" justification will not pass.

6. **He will not self-tag as Author.** Implication: if your patch lands with no Author trailer and Heikki as committer, the patch was substantively his work — don't read the missing trailer as ambiguity.

## Landmark commits (last 12mo)

- `9b5acad3f40` (Apr 2026): Convert all remaining subsystems to use the new shmem allocation API. — Final step of the shmem refactor (2,135 lines).
- `283e823f9dc` (Apr 2026): Introduce a new mechanism for registering shared memory areas. — The new RegisterNamedDSA/DSH primitive (1,343 lines).
- `2e0943a8597` (Apr 2026): Convert SLRUs to use the new shmem allocation functions. — Storage-side conversion (1,362 lines).
- `bd8d9c9bdfa` (Dec 2025): Widen MultiXactOffset to 64 bits. — Correctness-driven widening (2,131 lines), eliminates a long-standing wraparound concern.
- `c6d55714ba4` (Apr 2026): Use the new shmem allocation functions in a few core subsystems. — Mid-series conversion (725 lines).
- `17f51ea8187` (Feb 2026): Separate RecoveryConflictReasons from procsignals. — Cleanup of recovery/signals interaction (444 lines).
- `d6eba30a245` (Mar 2026): Refactor how user-defined LWLock tranches are stored in shmem. — LWLock infrastructure (348 lines).
- `393e0d2` (committer-map landmark): Split WaitEventSet to separate file.

## Notes / hedges

- **The shmem-allocation-API series (April 2026)** is the single largest design landmark in his 12mo window. Five commits within ~10 days that introduce a new primitive (`RegisterNamedDSA`), convert SLRUs, convert "core subsystems", and finally "convert all remaining subsystems." This is the textbook PG multi-commit refactor pattern — introduce, convert by subsystem, sweep. Phase D submitters proposing similar storage-API work should expect this style of staging.
- **Specialist reviewer pool** (Matthias, Ashutosh, Tomas, Andres) is the cleanest case in the top-5 committers of "subsystem-specific review pairings" rather than the cross-cutting pools of Tom/Michael/Peter. Phase D patches into storage should anticipate this reviewer set.
- **No self-Author, no self-Reviewed-by.** Heikki is the cleanest example of "the project's no-self-tagging convention taken seriously." If you mine commits with him as committer and look for Author trailers to attribute work, you will misattribute his own large refactors.
- **Cross-references:**
  - `peter-eisentraut.md` — 26 R-by on Peter's commits (high pair); they share storage + access territory.
  - `michael-paquier.md` — does NOT crack Heikki's top 10 reviewers despite Michael being top committer overall. Different territories.
  - Andres Freund (not yet a deep persona but cited heavily) — the strongest storage/AIO co-traveler.
