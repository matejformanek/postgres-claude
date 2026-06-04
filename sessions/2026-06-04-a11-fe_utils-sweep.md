# 2026-06-04 — A11 src/fe_utils sweep (cloud/pg-file-backfiller)

## What I did
- Ran the nightly `pg-file-backfiller` cloud routine. Queue head's 8
  `[pending]` `utils/adt/` entries were all stale (docs already on disk);
  marked `[done:covered-prior]` and refilled from `coverage-gaps.md`
  attack-order item 10: **`src/fe_utils/` (0/18 docs)**.
- 4 parallel general-purpose agents fetched each .c by raw URL at anchor
  `4b0bf0788b0` and wrote 18 per-file docs to `knowledge/files/src/fe_utils/`.
  Buckets: identifier-quoting/helpers, connection/recovery, astreamer chain,
  print/parallel.
- Consolidated **20 `[ISSUE-*]`** into the new `knowledge/issues/fe_utils.md`.
  Updated ledgers (files-examined +18, coverage 55.9%→56.6%, coverage-gaps
  src/fe_utils→100%, issues README index). Seeded next-run queue with the 16
  `src/include/fe_utils/` headers. Spot-checked 3 citations vs source — accurate.

## What I learned
- **`string_utils.c` is the identifier-quoting chokepoint** A4 flagged as a gap:
  `fmtId` (`:44`) returns a shared `static` buffer (silent aliasing footgun),
  `appendShellString` (`:600`) shell-safety rests entirely on a `strspn`
  allowlist, plus `processSQLNamePattern`/`patternToSQLRegex`. Now closed.
- **`astreamer_tar.c` IS the A4 "trust-the-stream" boundary** — server-supplied
  tar name/size/mode/uid/gid drive local `mkdir`/`fopen`/`chmod`. Mitigated by
  `path_is_safe_for_extraction` + non-empty-name reject + a hard `pg_fatal` on
  PAX extended headers (closes the classic PAX-long-name traversal). Residual is
  an invariant (server = trust root for base backups), not a bug.
- **`recovery_gen.c:57` is the canonical secret-to-disk site** — the conninfo
  skip-list omits `password`, so a base-backup password is written cleartext into
  `primary_conninfo` in `postgresql.auto.conf`. Joins the secret-scrub cluster
  (libpq A2 + psql/initdb A4 + common A5 + pg_upgrade A6 + walreceiver A8); +
  `connect_utils.c:44` frees prompted password without zeroing.
- **Decompression-bomb nuance:** gzip/lz4/zstd astreamers stream through a fixed
  output buffer (~256 KB / `ZSTD_DStreamOutSize()`) → NO RAM bomb, unlike
  `pg_lzcompress` (A5). The unbounded dimension is cumulative output/disk only.
- `version.c:64` `memcpy(*version_str, buf, st.st_size)` copies file-length bytes
  from a `%63s`-filled buffer → uninitialized trailing bytes + no NUL guarantee
  (bounded, harmless on well-formed `PG_VERSION`; flagged `correctness/maybe`).
- All 18 files confirm the frontend-conventions theme: `pg_malloc`/`pg_log_error`,
  never palloc/ereport.

## What I'm unsure about
- The agents repeatedly reported some target docs as "pre-existing"; on disk the
  directory was empty at run start, so they were almost certainly self-written in
  an earlier step and misattributed. Docs verified present + cite-accurate; no
  duplication. Worth noting the pattern if it recurs.
- `astreamer_file.c:248` absolute-symlink-target path-check bypass (for tablespace
  mappings) is the one fe_utils item that might be more than defense-in-depth —
  left at `question/maybe` for a domain expert.

## Pointers left for next time
1. Next-run queue is seeded with the 16 `src/include/fe_utils/` headers
   (companions; `print.h`/`astreamer.h` carry the load-bearing structs).
2. Candidate idiom doc: `knowledge/idioms/safe-sql-identifiers.md` joining
   `processSQLNamePattern` (A4) + `patternToSQLRegex` (A6) + `quoteOneName`/
   `ri_triggers.c` (A7) + `string_utils.c` (A11).
3. Remaining mechanical cloud-grind dirs: `src/port` (64, 0%), `src/timezone`
   (7, 0%), then contrib/ top modules.
