# Session — A13 contrib datatypes + index-AM sweep (foreground)

**Date:** 2026-06-09 (continuing the contrib/ campaign immediately
after A12 security-themed bundle)
**Phase:** A — corpus completeness + issue surfacing
**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Branch:** `ft_corpus_a13_contrib_datatypes`

## Scope

The **contrib datatypes + index-AM opclasses** bundle — 7 modules
covering the type-system extensions PG ships in contrib/. 56 source
files / ~22 K LOC:

| Module | Files | LOC | Docs |
|---|---:|---:|---:|
| hstore | 7 | 4 521 | 7 |
| ltree | 11 | 4 620 | 12 (inline ltree_gist.h documented separately) |
| btree_gist | 27 | 6 725 | 24 (3 framework .c+.h pairs combined + 21 per-type) |
| intarray | 8 | 3 506 | 7 (_int.h + _int_tool.c combined) |
| tablefunc | 1 | 1 575 | 1 |
| citext | 1 | 412 | 1 |
| btree_gin | 1 | 978 | 1 |
| **Total** | **56** | **~22 337** | **53** |

## Method

Standard A-sweep pattern. **4 parallel agents:**
- **A13-1** hstore (7 files; KV type + GiST + GIN)
- **A13-2** ltree (11 files; hierarchical labels + lquery + ltxtquery + GiST)
- **A13-3** btree_gist (27 files; GiST opclass framework for 21 PG types)
- **A13-4** intarray + tablefunc + citext + btree_gin (11 files;
  mixed datatype + SRF + collation-aware text + GIN opclass framework)

Wall time ~15 min. **Zero misdirection.** **13th A-sweep in a row.**

## Output

**Per-file docs** (53 docs, 56 source files):
- `knowledge/files/contrib/hstore/*` (7)
- `knowledge/files/contrib/ltree/*` (12)
- `knowledge/files/contrib/btree_gist/*` (24)
- `knowledge/files/contrib/intarray/*` (7)
- `knowledge/files/contrib/tablefunc/tablefunc.md`
- `knowledge/files/contrib/citext/citext.md`
- `knowledge/files/contrib/btree_gin/btree_gin.md`

**Subsystem issue registers** (7 files, ~155 entries):
- `knowledge/issues/hstore.md` — ~42 entries
- `knowledge/issues/ltree.md` — ~52 entries
- `knowledge/issues/btree_gist.md` — ~25 entries
- `knowledge/issues/intarray.md` — ~20 entries
- `knowledge/issues/tablefunc.md` — 10 entries
- `knowledge/issues/citext.md` — 5 entries
- `knowledge/issues/btree_gin.md` — 6 entries

**Progress ledgers updated:**
- `progress/files-examined.md` — +56 rows
- `progress/coverage.md` — 1 569→1 622 docs (61.2%→**63.3%**);
  contrib row 29.0%→54.3%; gap ~942
- `progress/coverage-gaps.md` — contrib section refreshed with A13
  completions
- `progress/STATE.md` — last-activity narrative

## Confidence rollup

Aggregate ~83% `[verified-by-code]`, ~13% `[from-comment]`, ~4%
`[inferred]`, **0% `[unverified]`**. Discipline holds across all
13 sweeps.

## Headlines

### 🚨 `tablefunc.connectby_text` SQL injection

`tablefunc.c:1227-1247` builds SQL via `appendStringInfo("SELECT
%s, %s FROM %s WHERE %s = %s ...", key_fld, parent_key_fld,
relname, parent_key_fld, quote_literal_cstr(start_with), ...)`.
**5 of 6 identifier args interpolated RAW; only `start_with` is
`quote_literal_cstr`'d.** Apps exposing relname/key_fld/
parent_key_fld to user input = straight-line SQL injection gated
only by SPI `read_only=true` (still permits `pg_authid` reads,
`pg_read_server_files()`).

`build_tuplestore_recursively` has NO `check_stack_depth()` —
only fragile `strstr`-based cycle check + user-supplied `max_depth`
(0=unlimited) guard the recursion.

### ltree — the lquery parser DoS surface

- **`parse_lquery` ~400000× memory amplification** —
  `ltree_io.c:322,329` allocates `nodeitem[numOR+1]` PER LEVEL
  where numOR is the GLOBAL `|` count. A ~256 KB query with
  ~65000 levels × ~65000 `|`s = ~100 GB scratch.
- **`checkCond` is a regex-class catastrophic backtracker**
  (`lquery_op.c:228-244`). 6 nested `*{0,9}` against 18-level
  ltree → ~10^6 explorations.
- **`crc32.c` locale-change silently breaks GiST signatures** —
  OS upgrade / pg_upgrade across platforms / ICU upgrade / lc_ctype
  change produces false-negative searches with no code-side
  detection.
- **`_ltree_gist::_ltree_compress` lacks `CHECK_FOR_INTERRUPTS`** —
  bounded only by MaxAllocSize (~85M elements); per-INSERT CPU DoS.

### hstore — the forgery channel

**Forged `HS_FLAG_NEWVERSION` bypasses ALL validation in
`hstoreUpgrade`** (`hstore_compat.c:242-243`). Fast path trusts
version bit on structurally-old hstore — downstream macros
(`HSE_ISFIRST`, `HSE_ENDPOS`) read garbage; `HSTORE_KEY`/`HSTORE_VAL`
memcpy off attacker-controlled offsets = **controllable OOB-read**.
The dump/restore channel is the realistic forgery vector. **Closest
hstore equivalent to A7 binary-decoder confusion + A3 pg_dump
trust-the-source.**

`hstore_compat.c` in-place re-encode has unchecked `pos+keylen`
arithmetic; `HENTRY_POSMASK` truncates overflow silently.

### btree_gist — collation-vs-NaN cluster

- **`btree_utils_var.c` latent collation footgun** — byte-prefix
  truncation is collation-invariant; ONLY `tinfo.trnc=false` in
  `btree_text.c:85,155` keeps text/bpchar correct. A future "shrink
  index size" change flipping this on would silently break range
  queries under ICU.
- **float4/float8 NaN divergence vs nbtree** — `EXCLUDE USING gist
  (val WITH =)` permits duplicate NaN rows where nbtree rejects.
- **`btree_inet.c` lossy double scalar** — only fixed-width opclass
  needing `*recheck=true`.
- **`btree_enum.c` stores raw enum OIDs** — fragile to `pg_upgrade
  --link` without REINDEX.
- **`btree_uuid.c` assumes `WORDS_BIGENDIAN` configured correctly.**

### intarray — signature-tree mod-hash collisions

`HASHVAL(val, siglen) = val % (siglen*8)`; default modulo 2016
(`_intbig_gist`). Attacker insertion can build false-positive
amplification OR plant 2016-distinct-value array creating an
ALLISTRUE leaf that defeats all pruning. `_int_bool.c::bqarr_in`
can palloc ~3 GB for max-size query (134M ITEM).

### citext — collation asymmetry

`citext_eq` uses DEFAULT-collation lowercase + bitwise compare;
`citext_lt`/`citext_cmp` use DEFAULT-collation lowercase +
INPUT-collation `varstr_cmp`. **Under Turkish/ICU-tailored
collations, `a=b` does NOT imply `not (a<b) and not (a>b)`.**

## New corpus-wide clusters from A13

1. **GiST-collision attacks on attacker-controlled data** —
   hstore CRC32 + ltree CRC32 + intarray mod-hash + A11 pgcrypto
   weak password defaults = 4-module signature-design vulnerability
   cluster.

2. **text-to-SPI injection sinks** — A9 plpgsql
   `exec_stmt_dynexecute` + A10 plperl `spi_exec_query` + A10
   plpython `plpy.execute(text)` + A10 pltcl `spi_exec` + **A13
   tablefunc `connectby_text`** (worst identifier-hygiene posture
   in tree) = **5-sweep cluster.** Combined Phase D pitch:
   identifier-quoting validator for `appendStringInfo`-style SQL
   builders.

## Cross-corpus reinforcement

- **A5 jsonapi recursive-parser finding** gets 3 new echo sites:
  ltree `checkCond` (lquery), ltxtquery `makepol`, intarray
  `bqarr_in`/`makepol`.
- **A7 `pg_locale_icu` ICU finding** gets 3 new echo sites:
  ltree `ISLABEL` locale-awareness, ltree `crc32` locale-cached
  `pg_locale_t`, citext collation-asymmetry.
- **A3 pg_dump trust-the-source** gets 1 strong echo: `hstore_compat`
  forgery channel.

## What this sweep did NOT do

- No commits to `dev/`.
- No new idiom docs written — the 2 new clusters are seeded as
  proposals.
- Did NOT sweep remaining ~96 contrib files (pg_visibility,
  pg_buffercache, pg_freespacemap, pg_prewarm, pgrowlocks,
  pg_walinspect, basebackup_to_shell, basic_archive,
  pg_overexplain, pg_surgery, bloom, seg, cube, isn, lo, unaccent,
  dict_xsyn, dict_int, earthdistance, fuzzystrmatch, pg_trgm,
  tsm_system_*) — A14 candidates.

## Position

**63.3% coverage; gap ~942 files.** Cumulative since 2026-06-02:
13 A-sweeps shipped, +705 docs, +~2 005 issues. **13 sweeps in a
row with zero misdirection.**

Next foreground candidates: **contrib leftovers cleanup** (~96
files across ~22 modules), `src/interfaces/ecpg` (~127 files, low
Phase D priority), or finishing `src/include` (still has gaps in
non-replication subdirs).
