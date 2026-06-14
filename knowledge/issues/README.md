# Issues register — corpus-discovered concerns

The append-only register of potential issues surfaced while reading
PostgreSQL source for the per-file documentation pass (Phase A).

This is **not** a bug tracker. It's a corpus-side notebook of things
that looked suspicious, surprising, or worth a second look while
documenting. Some entries become CommitFest patches; some become
non-issues on a closer read; some sit here as known-unknowns for years.

## What lands here

- `[ISSUE-correctness: ...]` — a logic bug, race, or invariant
  violation. Reproducible or strongly suspected.
- `[ISSUE-leak: ...]` — a memory, FD, lock, or information leak.
  Includes side-channel hints (timing, error-message granularity).
- `[ISSUE-doc-drift: ...]` — comment or README diverges from code.
  Common after a refactor.
- `[ISSUE-style: ...]` — code that violates `coding-style` skill rules
  (long lines, BSD-brace breaks, include-order). Low-priority.
- `[ISSUE-stale-todo: ...]` — a `TODO` / `FIXME` / `XXX` comment that
  hasn't been touched in years; flag for triage.
- `[ISSUE-dead-path: ...]` — code that looks unreachable. May be
  defensive, may be genuinely dead.
- `[ISSUE-undocumented-invariant: ...]` — an invariant the code clearly
  relies on but doesn't comment. Adding to corpus is the fix.
- `[ISSUE-question: ...]` — a "why is this here?" question that
  reading didn't answer. Surface for the next session or for a
  domain expert.

## Workflow

1. While writing or refreshing a per-file doc under `knowledge/files/`,
   if you spot one of the above, **tag inline in the per-file doc**:
   ```
   ## Potential issues

   - **[ISSUE-leak: lookup memory not freed on fast-path return]**
     `nbtsearch.c:1284` — `_bt_search` allocates a stack-local
     buffer but the FAST_PATH branch at line 1290 returns without
     hitting the `pfree(stack)` at line 1308. Likely benign (palloc
     in per-query context) but worth a second read.
   ```
2. **Also append a row** to the matching subsystem register
   `knowledge/issues/<subsystem>.md` so cross-corpus triage stays
   cheap. Format:
   ```
   | Date | File:line | Type | Severity | Summary | Status | Linked doc |
   |---|---|---|---|---|---|---|
   | 2026-06-02 | nbtsearch.c:1284 | leak | maybe | Stack buffer not freed on FAST_PATH return | open | knowledge/files/.../nbtsearch.c.md §Potential issues |
   ```
3. **Severity scale**: `nit` < `maybe` < `likely` < `confirmed` <
   `critical`. Be conservative — most things start at `maybe`.
4. **Status scale**: `open` (default) → `triaged` (we looked again,
   here's the read) → `wontfix` (deliberate; documented why) →
   `submitted` (sent upstream as CF entry / patch; link the CF#) →
   `landed` (upstream commit applied).

## How this register is used

- `pg-quality-auditor` cloud routine scans new per-file docs for the
  `[ISSUE-*]` tag and appends to the matching `<subsystem>.md`
  register if it hasn't been mirrored already. (Once that integration
  lands; see follow-up in `.claude/cloud/pg-quality-auditor.md`.)
- `pg-patch-review` skill's critic A (architecture + INV) checks the
  relevant `knowledge/issues/<subsystem>.md` to see if the patch
  addresses or contradicts any open issue.
- `pg-feature-brainstorm` skill triages this register during its
  "Has this been tried?" pass — open issues are candidate starting
  points for features.
- Periodic triage: `pg-state-keeper`'s daily briefing surfaces issues
  whose status hasn't moved in 30 days.

## Per-subsystem registers

One file per subsystem doc under `knowledge/subsystems/`. Created on
first issue. Index here:

| Subsystem | Register file | Open / Triaged / Wontfix / Submitted / Landed |
|---|---|---|
| storage-buffer | knowledge/issues/storage-buffer.md | (no issues yet) |
| access-nbtree | knowledge/issues/access-nbtree.md | (no issues yet) |
| utils-adt | knowledge/issues/utils-adt.md | 12 open (all nit/maybe; scalar-type cluster, 2026-06-03) |
| fe_utils | knowledge/issues/fe_utils.md | 23 open (all nit/maybe; A11 .c sweep 2026-06-04 + include/fe_utils headers 2026-06-05 — secret-scrub + backup-stream-trust + decompression-bomb + identifier-quoting clusters; +3 header-level undocumented-invariants) |
| port | knowledge/issues/port.md | 3 open (nit/maybe; src/port shim sweep 2026-06-06 — path-traversal canonicalization precondition, /dev/urandom O_CLOEXEC, quotes.c int-len truncation; hosts the in-tree secret/crypto primitives) |
| timezone | knowledge/issues/timezone.md | 4 open (all nit; src/timezone sweep 2026-06-07 — vendored IANA tzcode; static result buffer, malloc-not-palloc, %Z untrusted-input path, TZif producer/consumer trust split) |
| access-rmgrdesc | knowledge/issues/access-rmgrdesc.md | 4 open (all nit; rmgrdesc per-AM desc cloud sweep 2026-06-09 — empty gist PAGE_UPDATE desc, hash SPLIT_PAGE/CLEANUP no-desc case, committs/replorigin identify-on-unmasked-info, logicalmsg user-prefix raw %s into waldump) |
| libpq-oauth | knowledge/issues/libpq-oauth.md | 5 open (nit/maybe; libpq-oauth device-flow cloud sweep 2026-06-11 — sscanf %lf LC_NUMERIC, client_secret not bzero'd vs scrubbed token, client id/secret ASCII-assumed-unenforced, test F_SETFD/F_GETFL slip, uri_regress stable-order XXX) |
| ecpg | knowledge/issues/ecpg.md | 51 open (mostly nit; ecpg runtime-library cloud sweep 2026-06-12 + preproc compiler sweep 2026-06-13 — ecpglib+pgtypeslib+compatlib. Two systemic themes: pgtypeslib forks of backend datetime/numeric drift; Informix/pgtypes *_to_asc formatters write unbounded caller buffers. Maybe-flags: execute.c:761 bool[] heap overflow, execute.c:1649 PGresult leak, numeric.c:181 exponent alloc-sizing, dt_common.c:20 token-table sortedness, informix.c:660 NULL-deref asymmetry, prepare.c auto-prepare lifetime/threadsafety) |
| ... | ... | ... |

(Will populate as Phase A issues land.)

## Boundaries

- **Not for confirmed crashes / RCE / security vulnerabilities** — those
  go straight to `pgsql-security@lists.postgresql.org` per the
  upstream disclosure policy. The register is for the squishy middle:
  "this looks odd, let's track it".
- **Not for feature ideas** — those go in `planning/<slug>/brainstorm.md`
  via `/pg-brainstorm`.
- **Not for in-flight CF patches** — those live in CommitFest.

## See also

- `.claude/skills/pg-corpus-maintainer/SKILL.md` (cloud routine that
  writes corpus updates — owns issue-tag mirroring).
- `.claude/skills/pg-patch-review/SKILL.md` (critic A consults this
  register).
- `progress/coverage-gaps.md` (Phase A work queue — issue surface
  scales with coverage).
