# 2026-06-03 — A2 libpq stack sweep (foreground sweep #2)

**Type:** interactive (worktree `ft_corpus_a2_libpq_stack`).
**Outcome:** 69 new per-file docs covering the entire libpq stack
(`src/include/libpq/` + `src/backend/libpq/` + `src/interfaces/libpq/`);
**227 [ISSUE-*] tags surfaced** into `knowledge/issues/libpq.md` —
the densest Phase D data-leak surface in the codebase so far.

## Why this sweep

Phase A foreground sweep #2 per `progress/coverage-gaps.md`. The user
chose libpq as the natural follow-up to A1 catalog headers because:

- It's a data-leak project prerequisite (Phase D target).
- It's the most-attacked surface in PG (every client connection goes through it).
- It concentrates the auth / crypto / wire-protocol surface other subsystems delegate to it.

## What landed

### New files (72 total)

| Path | Count | Role |
|---|---|---|
| `knowledge/files/src/include/libpq/*.md` | 20 | All backend libpq headers (auth.h, libpq-be.h, libpq.h, protocol.h, sasl.h, scram.h, pqcomm.h, …) |
| `knowledge/files/src/backend/libpq/*.md` | 17 | All backend libpq .c (auth.c, auth-scram.c, be-secure-openssl.c, hba.c, pqcomm.c, …) |
| `knowledge/files/src/interfaces/libpq/*.md` | 32 | Frontend libpq (fe-connect.c, fe-exec.c, fe-auth.c, fe-secure-openssl.c, libpq-fe.h, libpq-int.h, …) — both client implementation and public/private API headers |
| `knowledge/issues/libpq.md` | 1 | Consolidated 227-entry issue register, grouped by Phase D priority + P1/P2/P3 |
| `sessions/2026-06-03-a2-libpq-stack.md` | 1 | This log |

### Modified files

| Path | Change |
|---|---|
| `progress/files-examined.md` | +69 rows |
| `progress/coverage.md` | Doc count 989→1 058; src/interfaces 0%→19.3%; src/include 42.8%→45.1%; total 38.6%→41.3% |
| `progress/coverage-gaps.md` | A2 marked done; attack order renumbered (sweep #3 = pg_dump+psql+pg_basebackup now priority) |
| `progress/STATE.md` | Last-activity updated; Phase A work queue renumbered |

## How it was done — 6 parallel agents

Same pattern as A1 catalog headers, scaled for libpq's larger files:

| Batch | Theme | Files | Issues | Wall time |
|---|---|---:|---:|---:|
| B1 | Backend headers (.h) | 20 | 35 | ~7 min |
| B2 | Backend auth + security (.c) — `auth.c`, `auth-scram.c`, `be-secure-openssl.c`, … | 9 | 41 | ~12 min |
| B3 | Backend protocol + HBA (.c) — `hba.c`, `pqcomm.c`, … | 8 | 32 | ~9 min |
| B4 | Frontend core (.c) — `fe-connect.c`, `fe-exec.c`, `fe-protocol3.c`, … | 8 | 50 | ~13 min |
| B5 | Frontend auth + security (.c/.h) — `fe-auth.c`, `fe-secure-openssl.c`, … | 13 | 47 | ~13 min |
| B6 | Frontend aux + headers + win32 — `libpq-fe.h` (the public API!), `libpq-int.h`, `pqexpbuffer.c`, `win32.c`, … | 11 | 22 | ~8 min |
| **Total** | | **69** | **227** | ~13 min wall (parallel max) |

Each agent read `dependency.h.md` or another existing doc for tone
calibration, then read each file and wrote a structured per-file doc.
Doc depth scaled with file size: tiny shim headers got 25-40 lines;
large state-machine .c files (`fe-connect.c`, `auth.c`,
`be-secure-openssl.c`) got 100-200 lines.

Agents returned structured summaries (files-examined rows + issue list
+ observations); orchestrator (this session) appended ledger rows,
refreshed coverage docs, and consolidated the 227 issues into
`knowledge/issues/libpq.md` grouped by Phase D priority.

## One process gotcha — B4 wrote to wrong path

B4's agent wrote its 8 docs into the **main repo's working tree**
(`/Users/matej/Work/postgres/postgres-claude/knowledge/files/...`)
instead of the worktree (`/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_corpus_a2_libpq_stack/knowledge/files/...`).
The agent prompt correctly specified the worktree path, but the
implementation apparently used absolute paths against the meta-repo
root. Caught at the verification step (the worktree had 61/69 docs,
not 69).

**Fix**: `mv` the 8 docs from main → worktree; clean up the empty
directories left in main. Took ~30 seconds, but worth flagging as a
prompt-hardening item for the next sweep: explicitly forbid absolute
paths in agent Write calls, or have agents return the doc bodies
and have the orchestrator write them. The latter avoids the issue
entirely but adds I/O cost.

## What the sweep surfaced

### The big picture: 227 issues in 69 files

Far denser than the catalog-headers sweep (68 issues / 72 files = 0.94
per doc) — libpq is at 3.3 issues per doc, because it concentrates
auth, crypto, and wire-protocol surface that the rest of PG delegates
here.

### Top Phase D candidates (full triage in `knowledge/issues/libpq.md`)

1. **Secret-scrubbing discipline is wildly uneven.** `explicit_bzero`
   is called in exactly TWO places across 60+ files reading credentials:
   `auth-oauth.c:341` (backend) and OAuth-token cleanup (frontend).
   Everywhere else, secrets are `pfree`'d without zeroing, left in
   `PGconn`/`Port` structs for the full connection lifetime, or copied
   into static buffers. **Single coordinated `explicit_bzero` sweep
   patch** + a `SecretBuf` wrapper would close the dominant Phase D
   surface.
2. **`require_auth=scram,none` partial-exchange weakness** — documented
   in code comment at `fe-auth.c:941`; auth silently accepts a partial
   SCRAM exchange.
3. **PBKDF2 iteration count uncapped on client side** — hostile server
   can DoS the client by setting a huge iteration count.
4. **`sslmode=prefer` (the default!) silently degrades to plaintext**
   on SSL handshake failure with no application signal beyond post-hoc
   `PQparameterStatus("ssl_in_use")`.
5. **`PGconn` credential lifetime is the structural problem** — carries
   `pgpass`, `sslpassword`, scram client/server keys, `oauth_token`,
   `oauth_client_secret`, per-host passwords array for the full
   connection lifetime. No clearance discipline in `freePGconn`.
6. **`'p'` byte is overloaded across four FE auth-response messages**
   (GSSResponse / PasswordMessage / SASLInitialResponse / SASLResponse),
   disambiguated only by what `AUTH_REQ_*` the server just sent —
   state-machine-confusion attack surface.
7. **`PQregisterEventProc` plugins run in-process with full PGconn access**;
   no unregister API; live until PQfinish; plugin registration is
   unauthenticated.
8. **`PQescapeString` (no-Conn variant)** uses process-global encoding
   state set by most recent connection — multi-connection apps have
   stale-globals injection vector. Always use `PQescapeStringConn`.
9. **`PQtrace` dumps DataRow values + Parse/Bind parameters verbatim**,
   including secrets. Intentional for debug but an exposure surface if
   enabled in production.
10. **15+ deprecated PQ* symbols still exported** for ABI compat
    (`PQrequestCancel`, `PQescapeString`/`PQescapeBytea`,
    `PQgetline`/`PQputline` family, `PQfn`, etc.). Pruning needs SONAME
    bump.

### Wire-protocol "do not change" pattern (echo of A1)

Same as the catalog sweep: ~20 libpq header constants (wire bytes,
mechanism strings, ALPN names) are on-wire-load-bearing but only
`dependency.h`'s `DependencyType` enum carries the "don't change this"
comment. **A single coordinated doc-only patch could close both the
catalog and the libpq clusters** — clean calibration target for the
planner suite.

### Pattern observations

- `COMMERROR` (don't try to write to client) is a corpus-wide PG idiom
  used in any I/O failure path; both `pqcomm.c` and `be-gssapi-common.c`
  call it out. Worth a `knowledge/idioms/commerror.md`.
- The `logdetail` / `error_detail` "server-log-only" convention is
  consistent but unenforced (`crypt.h`, `sasl.h`, `oauth.h`). A
  type-level wrapper would prevent regressions.
- HBA case-handling is consistent (SNI hostname `pg_strncasecmp` per
  RFC 952/921; GSSAPI realm `pg_strcasecmp` when `pg_krb_caseins_users`).
  No mismatch.
- OpenSSL 3.x API drift is well-managed in backend (#ifdefs for
  SSL_CTX_set_client_hello_cb, etc.) but the **frontend ENGINE path is
  still active** — `USE_SSL_ENGINE` builds against 3.x will degrade.

## What this commit explicitly does NOT do

- **No subsystem doc.** A `knowledge/subsystems/libpq.md` synthesis
  covering the whole stack (above the per-file layer) would be the
  next natural step; queued.
- **No upstream patches for any of the 227 issues.** The corpus side
  is done; turning any into a CF patch is separate Phase D work.
- **No changes to `dev/` or other knowledge/ trees.**
- **ecpg deferred** — 127 files under `src/interfaces/ecpg/`; embedded
  SQL preprocessor; low Phase D priority.

## Followup candidates surfaced

- **Foreground sweep #3** — `src/bin/pg_dump/` + `src/bin/psql/` + `src/bin/pg_basebackup/` (~46 files). Promoted to next active item in `progress/coverage-gaps.md`.
- **`knowledge/subsystems/libpq.md` spine synthesis** — combine A2's per-file docs into a single navigable spine doc with INV-* tags. Would feed the Phase D brainstorm directly.
- **Doc-only patch series #1**: "this is on-wire/on-disk; do not change" comment sweep — combines the 26 catalog + ~20 libpq sites. Single CF entry; near-zero risk; high clarity.
- **`SecretBuf` wrapper + `explicit_bzero` sweep** — the dominant Phase D surface in this register. Touches ~12 files; each change is local.
- **`knowledge/idioms/commerror.md`** — the I/O-error path discipline used in `pqcomm.c`, `be-gssapi-common.c`, etc.
- **`pg-quality-auditor` ISSUE mode is going to triage 227 new entries** under the new throughput budgets — keep an eye on its overnight runs to ensure it's keeping up.
- **B4 agent prompt-hardening** — explicitly forbid absolute paths in `Write` calls; or restructure so agents return doc bodies for orchestrator to write.

## Repository state after this commit

- 69 new files in `knowledge/files/src/{include,backend,interfaces}/libpq/`.
- 1 new file in `knowledge/issues/libpq.md` (227 rows organized by P0/P1/P2/P3 and pattern).
- 1 session log.
- 3 progress files updated (coverage.md, coverage-gaps.md, files-examined.md, STATE.md).

Total: 75 files changed, ~5 500 lines added.

## Commit message for this work

```
ft(corpus): document 69 libpq stack files (A2 sweep) + 227 issues

Second foreground sweep of Phase A: cover every previously-undocumented
.c/.h under src/include/libpq/ (20), src/backend/libpq/ (17), and
src/interfaces/libpq/ (32) via 6 parallel general-purpose agents.
Wall time ~13 min; 69 per-file docs landed; 227 [ISSUE-*] tags surfaced
and consolidated into knowledge/issues/libpq.md grouped by Phase D
priority (secret-scrubbing gaps, downgrade/protocol-confusion, DoS
uncapped inputs, TLS/cert validation, wire-protocol invariants, trust
boundaries, info disclosure) + P1/P2/P3.

Coverage bumps: 989 -> 1 058 docs (38.6% -> 41.3%); src/include
42.8% -> 45.1%; src/interfaces 0% -> 19.3%; the libpq dir moves to
"Done" in coverage-gaps.md; foreground sweep #3 (pg_dump + psql +
pg_basebackup) promoted to priority.

The headline finding: explicit_bzero is called in exactly TWO places
across 60+ files reading credentials. Everywhere else, secrets are
pfree'd without zeroing or left in PGconn/Port structs for the full
connection lifetime. A SecretBuf wrapper + a coordinated sweep patch
would close the dominant Phase D surface.

Other Phase D candidates: require_auth=scram,none partial-exchange
weakness (in-code comment at fe-auth.c:941); PBKDF2 iteration count
uncapped on client (CPU DoS); sslmode=prefer silently degrading to
plaintext; PGconn credential lifetime is structural; 'p' byte
overloaded across four FE auth-response messages; libpq plugin trust
boundary; PQescapeString process-global encoding state; PQtrace
dumps secrets.

One process gotcha: B4 agent wrote to the main repo working tree
instead of the worktree; manually relocated. Flagged in the session
log as a prompt-hardening item.

Session: sessions/2026-06-03-a2-libpq-stack.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
