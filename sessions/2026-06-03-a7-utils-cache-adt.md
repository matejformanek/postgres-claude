# 2026-06-03 — A7 utils/cache + utils/adt sweep (foreground sweep #7)

**Type:** interactive (worktree `ft_corpus_a7_utils_cache_adt`).
**Outcome:** 104 new per-file docs across `src/backend/utils/cache/`
(3 — completing the dir) + `src/backend/utils/adt/` (101); **310 issues
consolidated into `knowledge/issues/utils.md`** — the largest single
register in the corpus to date.

**Headlines:** (1) **genfile.c is the server-side dependency of A6
pg_rewind** — `pg_read_server_files` membership = total bypass + no
`O_NOFOLLOW`; (2) **xml.c uses unconventional XXE defense** — custom
entity-loader instead of `XML_PARSE_NONET`; (3) **pg_upgrade_support
is catalog-corruption battery** gated by single `IsBinaryUpgrade`
bool; (4) **acl.c PUBLIC-friendly defaults**; (5) **to_char has no
input-length cap**; (6) **binary recv DoS surface** (tsvector
16M lexemes, multirange 100 MB pre-alloc, record_recv no
check_stack_depth); (7) **extended-stats `Assert`-only validation**.

## Why this sweep

Phase A foreground sweep #7 per `progress/coverage-gaps.md`. `utils/`
was at 42.1% — the biggest absolute backend gap. `utils/cache` was
near-done (12/15); `utils/adt` was the giant unaddressed area (21/120).
This sweep closes both: every primitive type input function, every
SQL-exposed admin function, every text-search parser. Phase D angles
abound because adt is **where every user value enters the backend**.

## What landed

### New files (108 total)

| Path | Count | Role |
|---|---|---|
| `knowledge/files/src/backend/utils/cache/*.md` | 3 | funccache, relfilenumbermap, relmapper (completes the dir) |
| `knowledge/files/src/backend/utils/adt/*.md` | 101 | All previously-missing adt files (primitives, format/locale, text-search, arrays/ranges, JSON/XML/etc) |
| `knowledge/issues/utils.md` | 1 | 310-entry register — largest single register in the corpus |
| `sessions/2026-06-03-a7-utils-cache-adt.md` | 1 | This log |

### Modified files

| Path | Change |
|---|---|
| `progress/files-examined.md` | +104 rows (source slug `utils-a7`) |
| `progress/coverage.md` | 1 281 → 1 385 docs; src/backend 71.1% → 82.6%; utils dir 42.1% → 86.7%; total 50.0% → **54.0%** |
| `progress/coverage-gaps.md` | A7 marked done; utils remaining = error/, fmgr/, hash/, init/, mb/, misc/, mmgr/, resowner/, sort/, time/, activity/ subdirs |
| `progress/STATE.md` | Last-activity bumped; Phase A work queue 1-7 done, 8-11 queued |

## How it was done — 6 parallel agents

Same pattern as A1-A6; scaled for 104-file size with 6 batches by
semantic grouping:

| Batch | Theme | Files | Issues | Wall time |
|---|---|---:|---:|---:|
| B1 | cache (3) + admin/auth/system functions (acl, dbsize, genfile, hbafuncs, lockfuncs, mcxtfuncs, misc, pgstatfuncs, pg_upgrade_support, partitionfuncs, version, …) | 18 | 64 | ~16 min |
| B2 | numeric/datetime/oid primitive types (bool, char, cash, datetime, datum, expandeddatum, expandedrecord, mac, mac8, name, numutils, oid8, pg_lsn, regproc, tid, varbit, quote) | 17 | 46 | ~10 min |
| B3 | format/locale/text encoding (ascii, bytea, encode, format_type, formatting, levenshtein, like_*, oracle_compat, pg_locale*, ruleutils, pseudotypes, skipsupport) | 16 | 48 | ~13 min |
| B4 | text-search + regexp + windowing (regexp, trigfuncs, tsginidx, tsgistidx, tsquery*, tsrank, tsvector*, orderedsetaggs, windowfuncs, pseudorandomfuncs) | 17 | 32 | ~7 min |
| B5 | arrays/ranges/rowtypes + ext-stats (amutils, array*, arraysubs, arrayutils, multirange*, rangetypes*, rowtypes, pg_dependencies, pg_ndistinct) | 15 | 31 | ~8 min |
| B6 | JSON/XML/crypto/geo/network/uuid/enum/RI/xid (json, jsonb*, jsonfuncs, xml, cryptohashfuncs, geo_*, network_*, inet_*, uuid, enum, ri_triggers, xid, xid8funcs) | 21 | 64 | ~10 min |
| **Total** | | **104** | **285 reported / 310 grep** | ~17 min wall (parallel max) |

**Zero misdirection.** Seven consecutive sweeps with the explicit
"RELATIVE paths" instruction = zero relocation incidents.

The 285→310 discrepancy is the same clustered-tag undercount pattern
from prior sweeps; grep-authoritative.

## What the sweep surfaced

### Headline 1: genfile.c — the server-side dependency of A6 pg_rewind

The single most impactful corpus finding from A7 because it **explains
exactly which server-side function pg_rewind (A6) extracts** and where
the trust posture lives.

`genfile.c:53-92` `convert_and_check_filename`:
- `pg_read_server_files` role membership = **total bypass** (any file
  the postgres uid can read).
- Non-members: `canonicalize_path` collapses `..`, then accept iff
  absolute path is under `DataDir` OR `Log_directory` (which can be
  configured **outside pgdata**).
- **No `O_NOFOLLOW`, no `realpath`** — symlinks at any level transit
  through.

**Closure:** add `O_NOFOLLOW` to genfile's open calls; require
`realpath` resolution; refuse `Log_directory` escape.

Combined finding with A6: a malicious pg_rewind source with
`pg_read_server_files` membership can **list AND read AND
(via null-bytea response when genfile errors) silently delete** target
files. Worth a coordinated patch.

### Headline 2: xml.c — unconventional XXE defense

`xml.c:2046,1319` installs a custom `xmlSetExternalEntityLoader`
callback (`xmlPgEntityLoader`) that **returns empty string for every
external entity URL/ID** — INSTEAD of the standard `XML_PARSE_NONET`
flag. Meanwhile `XML_PARSE_NOENT` IS set, so internal entities expand
normally.

**Works today but architecturally fragile** — future libxml2 changes
to the entity-loader dispatch could regress this silently.

**Closure:** ADD `XML_PARSE_NONET` (defense-in-depth); document the
custom entity-loader contract; add explicit billion-laughs cap.

### Headline 3: pg_upgrade_support.c — catalog-corruption-primitive battery

Every `binary_upgrade_*` SQL function (`set_next_*_oid`,
`create_empty_extension`, `set_missing_value`, `add_sub_rel_state`,
`replorigin_advance`) skips normal validation. Gated only by a single
`IsBinaryUpgrade` bool flipped via postmaster `-b`. **No second-layer
defense.**

If `-b` is ever accidentally enabled in production (config drift,
debugging session), every `binary_upgrade_*` function becomes a remote
OID-spoofing / catalog-faking primitive callable by any role with
EXECUTE on the function.

**Closure:** require a stronger gate (shared-memory token from
pg_upgrade) or per-call privilege check beyond `IsBinaryUpgrade`.

### Headline 4: acl.c PUBLIC-friendly defaults

`acldefault` (`acl.c:827-940`) bakes PUBLIC-friendly defaults into 4
object types:
- DATABASE → `CONNECT|CREATE_TEMP` to PUBLIC
- FUNCTION → `EXECUTE` to PUBLIC
- LANGUAGE → `USAGE` to PUBLIC
- TYPE/DOMAIN → `USAGE` to PUBLIC

Every new DB is connectable, every new function is callable by PUBLIC
unless explicitly revoked. Comment self-identifies "for backwards
compatibility". Combined with SECURITY DEFINER = canonical
privilege-escalation surface.

### Headline 5: formatting.c::to_char has no input-length cap

A 50 MB `to_char(ts, big_string)` call forces `palloc(12 * fmt_len) ≈
600 MB`; only `MaxAllocSize` (1 GB) actually caps. NUM variant
silently returns `''` when `fmt_len >= INT_MAX/8` (~256 MB) —
surprising rather than helpful.

### Headline 6: Binary recv DoS cluster

The wire-protocol BinarySend/BinaryRecv paths have weaker discipline
than the text I/O paths:

- `tsvector.c:461` — `tsvectorrecv` accepts up to **16M lexemes** per
  tsvector; silently sorts misordered lexemes → multi-GB `qsort_arg`
  work from a single binary request.
- `tsquery.c:1240` — `tsqueryrecv` admits ~64M QueryItems.
- `multirangetypes.c:352` — `multirange_recv` allocates
  `RangeType*[range_count]` from a 4-byte wire-supplied count BEFORE
  consuming any range bytes. A tiny 6-byte message can trigger >100 MB
  transient palloc.
- `rowtypes.c` — **`record_recv` lacks explicit `check_stack_depth()`**.
  Only `record_in`/`record_out` have it. Deeply-nested record-of-record
  values from binary protocol rely on indirect stack-guard via
  per-column fmgr dispatch.

### Headline 7: Extended-stats trust gap

`statext_dependencies_deserialize` / `statext_ndistinct_deserialize`
validate per-item `nattributes` only with `Assert`. Production builds
rely on palloc's `MaxAllocSize` as last-line defense. A forged
`pg_statistic_ext_data` bytea with oversized `nattributes` could read
past buffer end via `memcpy` before any cap fires.

**Closure:** runtime check `nattributes <= STATS_MAX_DIMENSIONS`.

### What's working well (recorded as P0 negatives)

The corpus has often surfaced gaps; this sweep also surfaced solid
defenses worth documenting:

- **`gen_random_uuid()`** uses `pg_strong_random` (uuid.c:528 v4,
  :625 v7) — RFC 9562 §6.9 compliant.
- **`ri_triggers.c`** is fully safe — `quoteOneName` for identifiers +
  SPI-parameterized values; no SQL-injection surface.
- **`quote_literal`/`quote_ident`** are 100% safe across all server
  encodings — defense works byte-by-byte because PG's
  server-encoding allowlist (`src/common/encnames.c`) excludes SJIS,
  BIG5, GB18030 (encodings where `0x27`/`0x5C` could appear in
  multibyte trailing bytes).
- **`datetime.c`** parser-DoS defenses intact post-CVE-2007-3278 /
  CVE-2010-1170.
- **JSON backend recursion** fully gated by `check_stack_depth()` —
  backend pairing of A5 `jsonapi.c` no-op-in-libpq finding.
- **`range_*`** all stack-guarded.
- **`tsquery` text parsing** well-guarded by 11+ `check_stack_depth`
  calls.

### Notable corpus findings of interest

- **`pg_get_viewdef` omits security-relevant clauses** (`WITH CHECK
  OPTION`, `security_barrier`, `security_invoker`, view ACL). User
  calling `pg_get_viewdef('secure_view')` could wrongly conclude "no
  security barrier". Documentation/UX hazard.
- **`hbafuncs.c::pg_hba_file_rules.options[]`** exposes RADIUS/LDAP
  secrets in plaintext to anyone granted EXECUTE.
- **`pg_locale_icu.c`** passes user-supplied locale strings nearly
  verbatim to ICU's `ucol_open`/`ucol_openRules` — past ICU CVEs in
  BCP-47 parser would expose the backend.
- **`encode.c hex_decode_safe_scalar`** has no `CHECK_FOR_INTERRUPTS`
  → ~1 GB hex string uncancellable.

### Cross-corpus pattern reinforcement

- **A6 pg_rewind ↔ A7 genfile.c**: pg_rewind extracts via
  pg_read_binary_file; genfile.c is where that function lives and
  where the privilege check happens. Combined attack path documented.
- **Three confirmed-safe identifier/pattern helpers** now in the
  corpus: `processSQLNamePattern` (A4 — psql/pg_dump LIKE),
  `patternToSQLRegex` (A6 — pg_amcheck regex), `quoteOneName`/
  `ri_triggers.c` (A7 — FK enforcement). Single `knowledge/idioms/
  safe-sql-identifiers.md` would document the pattern.
- **Library-wrapper trust theme**: A5 found `pg_lzcompress` lacks
  decompression-ratio bound; A7 found `xml.c` uses custom XXE defense
  instead of `XML_PARSE_NONET`. Both inherit safety from upstream
  library behavior. Single Phase D pitch could harden library-wrapper
  boundary discipline corpus-wide.
- **SecretBuf cluster** reaches seven sweeps (no new sites here —
  utils consumers would inherit A5's `secretbuf.h` fix).

## What this commit explicitly does NOT do

- **No subsystem doc.** `knowledge/subsystems/utils-adt.md` synthesizing
  the per-file docs queued as follow-up.
- **No upstream patches for any of the 310 issues.** Corpus side done;
  Phase D work.
- **No changes to `dev/` or other knowledge/ trees.**
- **Remaining utils/ subdirs** (error, fmgr, hash, init, mb, misc,
  mmgr, resowner, sort, time, activity) are NOT in scope — most are
  already well-documented.

## Followup candidates surfaced

- **Phase D — `genfile.c` hardening** (single-function patch; closes
  A6 pg_rewind server-side dependency).
- **Phase D — `xml.c` defense-in-depth** (add `XML_PARSE_NONET` +
  billion-laughs cap).
- **Phase D — `pg_upgrade_support.c` gating** (second-layer check).
- **Phase D — `to_char` input-length cap**.
- **Phase D — `record_recv` explicit `check_stack_depth()`**.
- **Phase D — extended-stats runtime `nattributes` validation**.
- **Phase D — `hbafuncs.c` secret masking**.
- **`knowledge/idioms/safe-sql-identifiers.md`** — single doc for the
  three confirmed-safe pattern/identifier helpers.
- **`knowledge/subsystems/utils-adt.md`** synthesis.
- **Single-file audits** of `src/backend/storage/ipc/signalfuncs.c` and
  `src/backend/statistics/{dependencies,mvdistinct}.c` (where the
  actual logic lives that A7's adt wrappers expose).
- **Foreground sweep #8** — `src/include/replication/` (22, 4.5%) —
  closes the gap exposed by the replication spine doc.

## Repository state after this commit

- 104 new files across `knowledge/files/src/backend/utils/{cache,adt}/`.
- 1 new file `knowledge/issues/utils.md` (310 entries).
- 1 session log.
- 4 progress files updated.

Total: ~110 files changed, ~10 000 lines added.

## Commit message for this work

```
ft(corpus): document 104 utils/cache+adt files (A7 sweep) + 310 issues

Seventh foreground sweep of Phase A: cover the remaining .c/.h under
src/backend/utils/cache/ (3 missing) and src/backend/utils/adt/ (101)
via 6 parallel general-purpose agents. Wall time ~17 min; 104 per-file
docs landed; 310 [ISSUE-*] tags surfaced and consolidated into
knowledge/issues/utils.md — the LARGEST single register in the corpus
(vs libpq A2's 227, common A5's 124).

Coverage bumps: 1 281 -> 1 385 docs (50.0% -> 54.0%); src/backend
71.1% -> 82.6%; utils dir 42.1% -> 86.7%.

THE PHASE D HEADLINES:

1. genfile.c is the server-side dependency of A6 pg_rewind:
   pg_read_server_files membership = TOTAL bypass; non-members can
   still read paths under Log_directory (configurable outside pgdata);
   no O_NOFOLLOW, no realpath. Closure: harden
   convert_and_check_filename. Combined with A6 pg_rewind's null-bytea
   = unlink primitive, a malicious source with pg_read_server_files
   has list + read + silent-delete on target files.

2. xml.c unconventional XXE defense: custom xmlSetExternalEntityLoader
   returning empty string for every external entity, INSTEAD of
   XML_PARSE_NONET. XML_PARSE_NOENT IS set so internal entities
   expand. Works today but architecturally fragile (future libxml2
   changes could regress). Closure: add XML_PARSE_NONET + explicit
   billion-laughs cap.

3. pg_upgrade_support.c is catalog-corruption-primitive battery:
   every binary_upgrade_* function skips normal validation; gated
   only by single IsBinaryUpgrade bool flipped via postmaster -b.
   Accidental -b in production = remote OID-spoofing primitive.

4. acl.c PUBLIC-friendly defaults: DATABASE -> CONNECT|CREATE_TEMP,
   FUNCTION -> EXECUTE, LANGUAGE -> USAGE, TYPE/DOMAIN -> USAGE.
   Comment self-identifies "for backwards compatibility". Combined
   with SECURITY DEFINER = canonical privilege-escalation surface.

5. formatting.c::to_char has NO input-length cap: 50 MB format
   string -> palloc(12 * fmt_len) ~ 600 MB; only MaxAllocSize (1 GB)
   actually caps.

6. Binary recv DoS surface: tsvectorrecv (16M lexemes, silent sort
   -> multi-GB qsort), tsqueryrecv (64M items), multirange_recv
   (~100 MB transient palloc from 4-byte wire count), record_recv
   LACKS explicit check_stack_depth() (only record_in/_out have it).

7. Extended-stats deserializers (pg_dependencies, pg_ndistinct) only
   Assert-validate per-item nattributes -> forged stats bytea could
   read past buffer end via memcpy.

What's working: gen_random_uuid uses pg_strong_random (uuid.c:528 v4,
:625 v7) RFC 9562 compliant; ri_triggers.c fully safe (quoteOneName +
SPI params); quote_literal/quote_ident 100% safe across all server
encodings (SJIS/BIG5/GB18030 excluded by encnames.c allowlist);
datetime.c parser-DoS defenses intact post-CVE; JSON backend recursion
fully gated by check_stack_depth (pairs with A5 jsonapi finding); all
range_* I/O stack-guarded; tsquery text parsing well-guarded by 11+
check_stack_depth calls.

Cross-corpus: A6 pg_rewind null-bytea + A7 genfile.c bypass = combined
attack path. Three confirmed-safe identifier/pattern helpers in corpus
now: processSQLNamePattern (A4) + patternToSQLRegex (A6) + quoteOneName
(A7). XML XXE adds to library-wrapper trust theme (joins A5
pg_lzcompress).

Corpus gaps surfaced: src/backend/storage/ipc/signalfuncs.c (where
pg_terminate_backend actually lives, not misc.c); src/backend/
statistics/{dependencies,mvdistinct}.c (where extended-stats
deserialization actually lives).

All 6 agents wrote to correct worktree paths (zero misdirection;
7 successive sweeps with explicit RELATIVE-paths guidance = 0
relocation incidents).

Session: sessions/2026-06-03-a7-utils-cache-adt.md
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
