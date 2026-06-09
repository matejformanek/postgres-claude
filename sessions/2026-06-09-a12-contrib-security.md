# Session — A12 contrib security-themed sweep (foreground)

**Date:** 2026-06-09 (continuing the contrib/ campaign after A11
top-4 and several overnight cloud cycles)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a12_contrib_security`

## Scope

The **security-themed contrib bundle** — 7 modules whose entire
purpose is a Phase-D-relevant security surface. 30 source files
totalling **~19 200 LOC**:

| Module | Files | LOC | Docs | Security theme |
|---|---:|---:|---:|---|
| amcheck | 5 | 6 782 | 4 | catalog/index/heap verification |
| pageinspect | 9 | 3 693 | 8 | raw-page introspection (RLS-bypass) |
| pgstattuple | 3 | 1 784 | 3 | table/index stats (`pg_stat_scan_tables`) |
| sepgsql | 10 | 5 049 | 10 | SELinux MAC layer |
| file_fdw | 1 | 1 340 | 1 | path-traversal class |
| auth_delay | 1 | 75 | 1 | brute-force mitigation |
| sslinfo | 1 | 476 | 1 | TLS connection introspection |
| **Total** | **30** | **~19 200** | **28** | |

## Method

Standard A-sweep parallel-agent pattern. **4 general-purpose
subagents fired in parallel**, each with an explicit slice:

- **A12-1** amcheck (5 files; integrity verification)
- **A12-2** pageinspect + pgstattuple (12 files; raw-page +
  table-stats introspection)
- **A12-3** sepgsql (10 files; SELinux MAC integration)
- **A12-4** file_fdw + auth_delay + sslinfo (3 small standalone
  files)

Wall time ~14 min. **Zero misdirection.** **12th A-sweep in a row.**

## Output

**Per-file docs** (28 docs, 30 source files):
- `knowledge/files/contrib/amcheck/*` (4 docs)
- `knowledge/files/contrib/pageinspect/*` (8 docs)
- `knowledge/files/contrib/pgstattuple/*` (3 docs)
- `knowledge/files/contrib/sepgsql/*` (10 docs)
- `knowledge/files/contrib/{file_fdw,auth_delay,sslinfo}/*.c.md` (3 docs)

**Subsystem issue registers** (7 files, ~153 entries):
- `knowledge/issues/amcheck.md` — ~30 entries
- `knowledge/issues/pageinspect.md` — ~30 entries
- `knowledge/issues/pgstattuple.md` — ~13 entries
- `knowledge/issues/sepgsql.md` — ~53 entries (the largest; most
  security-explicit module in contrib)
- `knowledge/issues/file_fdw.md` — 15 entries
- `knowledge/issues/auth_delay.md` — 6 entries
- `knowledge/issues/sslinfo.md` — 12 entries

**Progress ledgers updated:**
- `progress/files-examined.md` — +30 rows
- `progress/coverage.md` — 1 541→1 569 docs (60.1%→**61.2%**);
  contrib row 15.7%→29.0%; gap ~995
- `progress/coverage-gaps.md` — contrib section refreshed with A12
  completions
- `progress/STATE.md` — last-activity narrative + work-queue refresh

## Confidence rollup

Aggregate ~80% `[verified-by-code]`, ~13% `[from-comment]`, ~5%
`[inferred]`, **0% `[unverified]`**. Discipline holds across all
12 sweeps.

## Headlines

### sepgsql — 3 confirmed security-class findings worth surfacing

1. **Permissive-mode AVC cache widening permanently mutates
   `cache->allowed`** (`uavc.c:384`). If an admin flips
   PERMISSIVE→DEFAULT without a policy reload, existing backends
   carry the widened entries until cache reclaim or policy reload.

2. **Parallel workers + bgworkers run unmonitored.** They use the
   SERVER's SELinux label as `client_label_peer` and stay in
   `SEPGSQL_MODE_INTERNAL` — silently non-enforcing AND
   non-auditing. Combined with the foreign-table DML gap (next
   point), MAC has real holes in modern PG workloads.

3. **`proc.c:279` typo** — ALTER FUNCTION ... SET SCHEMA does NOT
   check `add_name` on the destination namespace (re-adds to OLD
   namespace).

Plus: **DML on `RELKIND_FOREIGN_TABLE` gets no sepgsql check**;
**`db_tuple` per-row MAC unimplemented**; **TCP connections FATAL
out at ClientAuthentication** — sepgsql is effectively Unix-socket-
only.

### amcheck — zero permission checks, rich errdetail leaks

`verify_common.c:155-159` is explicit: "intentionally not checking
permissions". Combined with rich `errdetail` across all three
verifiers (page LSN + heap-TID + downlink block + xmin/xmax XID), a
misconfigured GRANT or SECDEF wrapper exposes a side channel of
per-page write timing + XID disclosure + physical layout.
**`verify_heapam(check_toast=true)` is documented as "can crash the
backend"** if the toast index is corrupted — only contrib function
in the tree with that level of honest crash disclosure.

### pageinspect — RLS bypass + cross-table TOAST read

`get_raw_page` is the central RLS-bypass primitive (returns full
8 KB block bytea). **`tuple_data_split(do_detoast=true)` follows
attacker-controlled TOAST pointers without cross-checking
`va_toastrelid` matches the `relid` argument's TOAST relation** —
cross-table read primitive if SECDEF-delegated; only the superuser
gate prevents arbitrary use. Pageinspect has **zero
`pg_stat_scan_tables` GRANT discipline** unlike pgstattuple. Bounds-
checking is uneven (`rawpage.c` + `heapfuncs.c` check `lp_off+lp_len
≤ BLCKSZ`; per-AM decoders trust `PageGetItem` invariants on
fabricated bytea).

### pgstattuple — VM-trust fail-open

`pgstatapprox` silently trusts VM bits → corrupt VM = wrong stats,
no diagnostic. **Direct echo of A11 pg_amcheck critique.** Module
disagrees with itself on what "live" means (SnapshotDirty
[pgstattuple] vs HeapTupleSatisfiesVacuum [pgstatapprox]) and on
corruption policy (ERROR [pgstatindex hash] vs silent-swallow
[pgstattuple hash]).

### file_fdw — single-layer trust, inherits A6 gap

Single role-gate (`pg_read_server_files` /
`pg_execute_server_program`). **Diverges from A11's postgres_fdw
two-layered `password_required` gold standard.** NO path-traversal
sanitization, no `O_NOFOLLOW`, no `S_ISREG` check, no in-data-dir
restriction. **Inherits A6 pg_rewind's symlink-TOCTOU surface** —
PG's file-open path lacks `O_NOFOLLOW` system-wide.

### auth_delay — failure-only delay = deliberate timing oracle

`pg_usleep(1000L * auth_delay.milliseconds)` fires only when
`status != STATUS_OK`. A network observer measuring round-trip time
can distinguish wrong-password from right-password. The upstream
design accepts the oracle for the brute-force-mitigation benefit.
No per-IP rate-limit, no jitter, 35-min upper bound (DoS
amplifier).

### sslinfo — zero role gates, asymmetric verification

No `superuser()` / role check on any function. Default PUBLIC
EXECUTE. **`ssl_issuer_field` checks `!MyProcPort->peer` instead of
`!ssl_in_use || !peer_cert_valid`** — can return issuer-DN data
from an UNVERIFIED cert while sibling `ssl_client_dn_field`
requires verification. **`cstring_to_text` strlen-based** —
embedded NUL in DN truncates silently = potential CN-comparison
bypass.

## New corpus-wide pattern from A12

**"Monitoring access = sensitive data extraction"** — amcheck
errdetail (page LSN/heap-TID/XID) + pageinspect RLS bypass
(raw-page bytes) + pgstattuple RLS row-count leak + pg_stat_statements
password capture (A11) + genfile.c bypass (A7) form a **5-sweep
cluster** where role-granted monitoring/integrity tools become PII
channels. Propose `knowledge/idioms/monitoring-is-data-leak.md`.

## Cross-corpus reinforcement

- **A11 pg_amcheck fail-open pattern** now has 2nd echo
  (pgstatapprox VM-trust).
- **A6 `O_NOFOLLOW` gap** has 4th site (file_fdw).
- **A11 postgres_fdw two-layered trust** confirmed as gold standard
  via contrast (file_fdw, dblink, amcheck all single-layer).
- **A11 pgcrypto "wrapped legacy more disciplined than SQL surface"
  pattern** mirrors here — sepgsql's well-designed AVC cache is
  undermined by the permissive-mode widening bug.
- **NAME-vs-OID Phase D pattern** — sepgsql per-table-name canonical
  hash + sepgsql foreign-table DML gap are 2 new sites; cluster now
  spans 8 sweeps (A3+A6+A7+A8+A9+A10+A11+A12).

## What this sweep did NOT do

- No commits to `dev/`.
- No new idiom docs written — the new "monitoring-is-data-leak"
  cluster is seeded as proposal.
- No upstream patches drafted — sepgsql's 3 confirmed findings are
  worth a hackers thread but that's Phase D territory.
- Did NOT sweep remaining contrib (~149 files left) — A13 candidate.

## Position

**61.2% coverage; gap ~995 files.** src/pl + src/fe_utils +
src/timezone + contrib top-4 + contrib security-themed all
complete. **Cumulative since 2026-06-02:** 12 A-sweeps shipped,
+652 docs, +~1 850 issues. The next foreground sweep candidates are
the contrib datatypes (hstore/ltree/intarray/citext), contrib
index AMs (btree_gin/btree_gist), or the remaining `src/include`
backlog (~390 files).
