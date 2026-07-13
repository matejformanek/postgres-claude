# Issues — `utils` (src/backend/utils/{cache,adt}/)

Per-subsystem issue register for the catalog cache (3 new files) and
the type-implementation directory adt/ (101 new files). The latter is
**THE entry point for every user-supplied value into the backend** —
every input function takes a Datum/text and produces a typed Datum.

**Parent docs:** `knowledge/files/src/backend/utils/cache/*` (15 docs)
+ `knowledge/files/src/backend/utils/adt/*` (122 docs).

**Source:** **310 entries** surfaced 2026-06-03 by the A7 foreground
sweep (6 batches B1-B6). Each is mirrored in the per-file doc's
`## Potential issues` block.

This is the **largest single register** in the corpus to date (vs
libpq A2's 227, common A5's 124). Reflects adt's status as the broadest
attack surface — every type's I/O, every SQL function exposed via
fmgr.

The headlines:
1. **`genfile.c` is the server-side trust target pg_rewind extracts** — `pg_read_server_files` role membership = total bypass; non-members can still read paths under `Log_directory` (which can be outside pgdata); no `O_NOFOLLOW`, no `realpath`.
2. **`xml.c` XXE defense is unconventional** — uses a custom `xmlSetExternalEntityLoader` returning empty string instead of `XML_PARSE_NONET`; works today but future libxml2 changes could regress.
3. **`pg_upgrade_support.c` is a catalog-corruption-primitive battery** gated by a single `IsBinaryUpgrade` bool flipped by postmaster `-b`.
4. **`acl.c` PUBLIC-friendly defaults** — DATABASE→`CONNECT|CREATE_TEMP`, FUNCTION→`EXECUTE`, LANGUAGE→`USAGE`, TYPE/DOMAIN→`USAGE` for PUBLIC. The "secure by default" gap.
5. **`formatting.c::to_char` has NO input-length cap** — 50 MB format string → ~600 MB palloc.
6. **Binary recv DoS surface** — `tsvectorrecv` (16M lexemes), `tsqueryrecv` (64M items), `multirange_recv` (~100 MB transient palloc from 4-byte count), `record_recv` lacks explicit `check_stack_depth`.
7. **Extended-stats deserializers** (`pg_dependencies`, `pg_ndistinct`) only `Assert`-validate per-item `nattributes` → forged bytea could read past buffer end.

**What's working well (recorded as P0 negatives):**
- **`gen_random_uuid()` uses `pg_strong_random`** (uuid.c:528 v4, :625 v7) — RFC 9562 compliant.
- **`ri_triggers.c` is fully safe** — `quoteOneName` for identifiers + SPI-parameterized values; no SQL-injection surface.
- **`quote_literal`/`quote_ident` are 100% safe** across all server encodings (SJIS/BIG5/GB18030 excluded from allowlist by `encnames.c`).
- **`datetime.c` parser-DoS defenses intact** post-CVE-2007-3278 / CVE-2010-1170.
- **JSON backend recursion fully gated** by `check_stack_depth()` — backend pairing of A5 `jsonapi.c` no-op-in-libpq finding.
- **`range_in`/`range_out`/`range_recv`/`range_send`** all call `check_stack_depth`.
- **`tsquery` text parsing** well-guarded by 11+ `check_stack_depth` calls.

---

## P0 — Phase D candidates

### `genfile.c` — the read-arbitrary-file gate (the pg_rewind dependency)

The function family pg_rewind (A6) extracts via libpq_source — the trust posture matters not just to pg_rewind but to any malicious admin with `pg_read_server_files` membership.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | genfile.c:53-92 | trust-boundary | likely | `pg_read_server_files` role = **total bypass** — any file the postgres uid can read is returned. No `O_NOFOLLOW`/no `realpath` | open | knowledge/files/src/backend/utils/adt/genfile.c.md |
| 2026-06-03 | genfile.c:65 | path-traversal | likely | Non-members can still read paths under `DataDir` OR `Log_directory` — `Log_directory` can be configured outside pgdata so non-`pg_read_server_files` callers granted EXECUTE can read server logs by path | open | knowledge/files/src/backend/utils/adt/genfile.c.md |
| 2026-06-03 | genfile.c | path-traversal | maybe | `canonicalize_path` collapses `..` before validation but symlinks at any level still transit through | open | knowledge/files/src/backend/utils/adt/genfile.c.md |
| 2026-06-03 | genfile.c | trust-boundary | maybe | `pg_stat_file`, `pg_ls_dir` use the same gate as `pg_read_file` | open | knowledge/files/src/backend/utils/adt/genfile.c.md |

**Phase D pitch:** add `O_NOFOLLOW` to genfile's open calls; require `realpath` resolution to validate the canonical destination is under `DataDir` (refuse `Log_directory` escape).

### `xml.c` — unconventional XXE defense

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | xml.c:2046,1319 | xxe | likely | `XML_PARSE_NONET` is NOT set; defense is via custom `xmlPgEntityLoader` that returns empty string for every external entity. `XML_PARSE_NOENT` IS set so internal entities expand. Architecturally fragile — future libxml2 changes could regress this | open | knowledge/files/src/backend/utils/adt/xml.c.md |
| 2026-06-03 | xml.c:2042 | stale-todo | nit | Comment "allow loading entities that exist in the system's global XML catalog" — stable TODO | open | knowledge/files/src/backend/utils/adt/xml.c.md |
| 2026-06-03 | xml.c | dos | maybe | Billion-laughs defense relies on libxml2's internal amplification limit — not verified at PG layer | open | knowledge/files/src/backend/utils/adt/xml.c.md |

**Phase D pitch:** ADD `XML_PARSE_NONET` (defense-in-depth); document the custom entity-loader contract in code comment; add explicit billion-laughs cap.

### `pg_upgrade_support.c` — catalog-corruption-primitive battery

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_upgrade_support.c | trust-boundary | likely | Every `binary_upgrade_*` function (`set_next_*_oid`, `create_empty_extension`, `set_missing_value`, `add_sub_rel_state`, `replorigin_advance`) skips normal validation; gated only by single `IsBinaryUpgrade` bool flipped via postmaster `-b`. Accidental `-b` in production = remote OID-spoofing/catalog-faking primitive | open | knowledge/files/src/backend/utils/adt/pg_upgrade_support.c.md |
| 2026-06-03 | pg_upgrade_support.c | trust-boundary | maybe | No second-layer defense (e.g., calling backend must be pg_upgrade-spawned) | open | knowledge/files/src/backend/utils/adt/pg_upgrade_support.c.md |

**Phase D pitch:** require a stronger gate (e.g., shared-memory token issued by pg_upgrade) or per-call privilege check beyond `IsBinaryUpgrade`.

### `acl.c` — PUBLIC-friendly defaults

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | acl.c:827-940 | trust-boundary | likely | `acldefault` bakes PUBLIC-friendly defaults: DATABASE→`CONNECT\|CREATE_TEMP`, FUNCTION→`EXECUTE`, LANGUAGE→`USAGE`, TYPE/DOMAIN→`USAGE`. Comment self-identifies "for backwards compatibility". Combined with SECURITY DEFINER = canonical privilege-escalation surface | open | knowledge/files/src/backend/utils/adt/acl.c.md |
| 2026-06-03 | acl.c | undocumented-invariant | maybe | ACL parser has many edge cases (PUBLIC vs role names; "group" prefix legacy) — every parser path is potential ACL bypass | open | knowledge/files/src/backend/utils/adt/acl.c.md |

### Backend DoS: parser & decoder caps

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | formatting.c:3907 | dos | likely | `to_char` has NO input-length cap on format strings — 50 MB format → palloc(12 * fmt_len) ≈ 600 MB; only `MaxAllocSize` (1 GB) actually caps | open | knowledge/files/src/backend/utils/adt/formatting.c.md |
| 2026-06-03 | formatting.c:6236 | correctness | maybe | NUM variant silently returns `''` when `fmt_len >= INT_MAX/8` (~256 MB) — surprising | open | knowledge/files/src/backend/utils/adt/formatting.c.md |
| 2026-06-03 | encode.c:282-306 | dos | likely | `hex_decode_safe_scalar` has no visible `CHECK_FOR_INTERRUPTS` in scalar loop — ~1 GB hex string spins CPU uncancellable | open | knowledge/files/src/backend/utils/adt/encode.c.md |
| 2026-06-03 | tsvector.c:461 | dos | maybe | `tsvectorrecv` accepts up to 16M lexemes per tsvector — silently sorts misordered lexemes → multi-GB `qsort_arg` work from binary protocol | open | knowledge/files/src/backend/utils/adt/tsvector.c.md |
| 2026-06-03 | tsquery.c:1240 | dos | maybe | `tsqueryrecv` admits ~64M QueryItems per tsquery | open | knowledge/files/src/backend/utils/adt/tsquery.c.md |
| 2026-06-03 | multirangetypes.c:352 | dos | maybe | `multirange_recv` allocates `RangeType*[range_count]` from 4-byte wire-supplied count BEFORE consuming bytes — tiny 6-byte message could trigger >100 MB transient palloc | open | knowledge/files/src/backend/utils/adt/multirangetypes.c.md |
| 2026-06-03 | rowtypes.c | dos | maybe | `record_recv` lacks explicit `check_stack_depth()` (only `record_in`/`record_out` have it at line 92/344). Deeply-nested record-of-record values from binary protocol rely on indirect stack-guard via per-column fmgr dispatch | open | knowledge/files/src/backend/utils/adt/rowtypes.c.md |
| 2026-06-03 | pg_locale_icu.c | trust-boundary | maybe | User-supplied locale strings pass nearly verbatim to ICU's `ucol_open`/`ucol_openRules` parsers. CREATE COLLATION requires privilege but past ICU CVEs in BCP-47 parser would expose the backend | open | knowledge/files/src/backend/utils/adt/pg_locale_icu.c.md |

### Extended-stats trust gap

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_dependencies.c (+ statext/mvdistinct.c:310, dependencies.c:557) | trust-boundary | maybe | `statext_dependencies_deserialize`/`statext_ndistinct_deserialize` validate per-item `nattributes` only with `Assert` — production builds rely on palloc's `MaxAllocSize` as last-line defense; forged `pg_statistic_ext_data` bytea with oversized `nattributes` could read past buffer end via `memcpy` before any cap fires (pre-check uses *minimum* per-item size, not trusted-from-bytea value) | open | knowledge/files/src/backend/utils/adt/pg_dependencies.c.md |
| 2026-06-03 | pg_ndistinct.c | trust-boundary | maybe | Same per-item `nattributes` `Assert`-only validation | open | knowledge/files/src/backend/utils/adt/pg_ndistinct.c.md |

**Phase D pitch:** runtime check `nattributes <= STATS_MAX_DIMENSIONS` (not just `Assert`).

### Info-disclosure: sensitive fields exposed in views

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | hbafuncs.c | info-disclosure | likely | `pg_hba_file_rules.options[]` exposes RADIUS / LDAP secrets in plaintext to anyone granted EXECUTE — no masking in `get_hba_options`; default ACL is owner-only but `GRANT TO monitor` leaks secrets | open | knowledge/files/src/backend/utils/adt/hbafuncs.c.md |
| 2026-06-03 | pgstatfuncs.c | info-disclosure | maybe | `pg_stat_get_activity` uses literal `'<insufficient privilege>'` for masked query column (not NULL) — common cause of false-negative filter queries | open | knowledge/files/src/backend/utils/adt/pgstatfuncs.c.md |
| 2026-06-03 | misc.c, version.c | info-disclosure | nit | `current_setting('server_version')` and `version()` always expose full compile-time banner to PUBLIC | open | knowledge/files/src/backend/utils/adt/version.c.md |
| 2026-06-03 | ruleutils.c:5900-5965 | info-disclosure | maybe | **`pg_get_viewdef` omits `WITH CHECK OPTION` / `security_barrier` / `security_invoker` / view ACL** — user calling `pg_get_viewdef('secure_view')` could wrongly conclude "no security barrier". Documentation/UX hazard | open | knowledge/files/src/backend/utils/adt/ruleutils.c.md |
| 2026-06-03 | lockfuncs.c | trust-boundary | maybe | `pg_advisory_lock` shares a single per-DB keyspace across all roles — multi-tenant footgun | open | knowledge/files/src/backend/utils/adt/lockfuncs.c.md |

---

## P1 — Type-I/O parser & correctness invariants

### Asymmetries between text and binary protocols

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | name.c:57 vs :90 | wire-protocol | maybe | `namein` truncates silently at NAMEDATALEN-1; `namerecv` errors with `ERRCODE_NAME_TOO_LONG`. Asymmetry undocumented in user-facing material | open | knowledge/files/src/backend/utils/adt/name.c.md |
| 2026-06-03 | numutils.c:947 vs :983 | wire-protocol | maybe | `uint32in_subr` accepts `-1` and wraps to MAXUINT32 for legacy oid compat; `uint64in_subr` does not. Lack of parity surprises ORM/driver authors | open | knowledge/files/src/backend/utils/adt/numutils.c.md |

### Expanded-Datum memory discipline

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | expandeddatum.c:88-145 | undocumented-invariant | maybe | R/W vs R/O pointer discipline is load-bearing for memory safety — `MakeExpandedObjectReadOnly`, `TransferExpandedObject`, `DeleteExpandedObject` rely on caller correctly identifying pointer type. Bugs surface as use-after-free or double-free in long-running PL/pgSQL composite-variable code | open | knowledge/files/src/backend/utils/adt/expandeddatum.c.md |

### Correctness in numeric/window/range

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | windowfuncs.c:559 | correctness | maybe | `leadlag_common` signed-integer overflow on `INT32_MIN` — `forward ? offset : -offset` with no guard. `lag(col, -2147483648)` triggers signed-integer UB; likely benign in practice (downstream treats as out-of-frame) but UB by C99 | open | knowledge/files/src/backend/utils/adt/windowfuncs.c.md |
| 2026-06-03 | tsvector_op.c:376,380 | correctness | maybe | `tsvector_concat` (def :899) silently clamps positions at `MAXENTRYPOS-1` instead of erroring — the actual clamp is in helper `add_pos()`: stop-when-full at `:376` (`WEP_GETPOS(dpos[*clen-1]) != MAXENTRYPOS-1`) + `LIMITPOS` at `:380`, called from concat at :995/:1025/:1029/:1077. Document-length tsvectors yield degenerate result with far positions collapsing | open · triaged 2026-07-13 | knowledge/files/src/backend/utils/adt/tsvector_op.c.md |
| 2026-06-03 | ri_triggers.c:4010 (decl :295) | correctness | maybe | `ri_CompareWithCast` trusts a cast operator for cross-type FK comparison — a buggy user-type cast could silently mis-compare. Def at `:4010` (`FunctionCall3(&entry->cast_func_finfo,...)`); forward-decl `:295`. (Was cited `:288`, which is now `ri_NullCheck` — re-anchored; per-file doc already read `decl 295, def 4010`.) | open · triaged 2026-07-13 | knowledge/files/src/backend/utils/adt/ri_triggers.c.md |

### Cache invariants

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | funccache.c | undocumented-invariant | nit | Function-call result caching; correctness on volatile functions implicit | open | knowledge/files/src/backend/utils/cache/funccache.c.md |
| 2026-06-03 | relfilenumbermap.c | undocumented-invariant | nit | Reverse map relfilenumber → relation OID; lookup table trust assumptions | open | knowledge/files/src/backend/utils/cache/relfilenumbermap.c.md |
| 2026-06-03 | relmapper.c | state-transition | nit | Shared-catalog file map; failure mode on map corruption | open | knowledge/files/src/backend/utils/cache/relmapper.c.md |

---

## P2 — High-volume per-file tag rollup

Due to register size, the remaining ~250 entries are mirrored inline in
their per-file docs and summarized in the table below. Each per-file
doc has its own `## Potential issues` block with full text.

### Per-file issue counts (only entries with ≥3 tags shown)

| File | Tag count | Headline |
|---|---:|---|
| `acl.c.md` | 8 | ACL parsing edge cases; PUBLIC defaults |
| `genfile.c.md` | 6 | Path validation gaps; `pg_read_server_files` bypass |
| `hbafuncs.c.md` | 4 | RADIUS/LDAP secret exposure |
| `pgstatfuncs.c.md` | 6 | `pg_stat_*` masking strings |
| `misc.c.md` | 4 | `current_setting`/`set_config` semantics |
| `dbsize.c.md` | 3 | `stat()`-based size; symlink/permission silent errors |
| `lockfuncs.c.md` | 3 | Cross-tenant advisory-lock keyspace |
| `xml.c.md` | 7 | XXE custom defense; billion-laughs reliance |
| `json.c.md` | 4 | Backend json input parser depth |
| `jsonfuncs.c.md` | 5 | json/jsonb manipulation operators |
| `formatting.c.md` | 5 | `to_char` uncapped format strings |
| `encode.c.md` | 4 | hex/base64 decode CPU uncancellable |
| `pg_locale_icu.c.md` | 4 | ICU collation rule parser exposure |
| `ruleutils.c.md` | 6 | Deparse omits security clauses |
| `rowtypes.c.md` | 4 | `record_recv` no explicit stack check |
| `rangetypes.c.md` | 3 | Range bound canonicalization invariants |
| `multirangetypes.c.md` | 3 | `multirange_recv` pre-allocate from wire count |
| `tsvector.c.md` | 4 | Binary recv lexeme cap (16M); silent sort |
| `tsquery.c.md` | 4 | Binary recv item cap (64M); text parser stack-guarded |
| `tsvector_parser.c.md` | 3 | Caller must enforce caps (defense-in-depth gap) |
| `regexp.c.md` | 3 | SQL regex wrapper; flag-string parsing |
| `network.c.md` | 4 | inet/cidr parser edge cases |
| `inet_net_pton.c.md` | 3 | Historic buffer-write-past-end class |
| `uuid.c.md` | 3 | UUIDv4/v7 uses `pg_strong_random` (good) |
| `ri_triggers.c.md` | 3 | Safe identifier quoting + SPI params |
| `arrayutils.c.md` | 3 | Element-count overflow guard |
| `cryptohashfuncs.c.md` | 2 | Deterministic; minimal scrub surface |
| `geo_ops.c.md` | 5 | Quadratic polygon algorithms |
| `formatting.c.md` | 5 | (listed above) |
| `name.c.md` | 3 | Truncate vs error asymmetry |
| `quote.c.md` | 4 | 100% safe due to encoding allowlist |
| `numutils.c.md` | 4 | Legacy uint32 vs uint64 negative parsing |
| `datetime.c.md` | 4 | Post-CVE hardening intact |
| `expandeddatum.c.md` | 3 | R/W vs R/O pointer discipline |
| `expandedrecord.c.md` | 3 | Composite-variable lifecycle |
| `pseudorandomfuncs.c.md` | 3 | Weak PRNG; fallback seed quality |
| `windowfuncs.c.md` | 3 | INT32_MIN overflow in leadlag |
| `pg_dependencies.c.md` | 3 | Assert-only `nattributes` validation |
| `pg_ndistinct.c.md` | 3 | Same |
| `pg_locale.c.md` | 3 | Locale dispatch correctness |
| `pg_locale_libc.c.md` | 3 | libc setlocale interaction |
| `partitionfuncs.c.md` | 2 | Info-disclosure for non-owner |
| `mcxtfuncs.c.md` | 2 | Memory-layout exposure |
| `domains.c.md` | 2 | CHECK constraint eval |
| `version.c.md` | 2 | Banner exposure |
| `oracle_compat.c.md` | 4 | Many string builders; length-bound discipline |
| `like_match.c.md` | 3 | LIKE matching quadratic worst-case |
| `like_support.c.md` | 2 | Index-path support |
| `levenshtein.c.md` | 3 | Quadratic time + space |
| `bytea.c.md` | 3 | Hex vs escape format; NUL handling |
| `ascii.c.md` | 2 | `chr(0)` NUL handling |
| `format_type.c.md` | 2 | Typename pretty-printer |
| `cash.c.md` | 3 | Locale-dependent currency parse |
| `mac.c.md` | 2 | MAC canonicalization |
| `mac8.c.md` | 2 | MAC8 (EUI-64) parse |
| `pg_lsn.c.md` | 2 | LSN `X/Y` format; overflow |
| `regproc.c.md` | 3 | `regclass('SELECT...')` ScanState bound |
| `tid.c.md` | 2 | TID `(block, offset)` bounds |
| `varbit.c.md` | 3 | Bit-length tracking off-by-one |
| `enum.c.md` | 3 | Enum-label lookup; OID ordering |
| `xid.c.md` | 2 | 32-bit XID overflow |
| `xid8funcs.c.md` | 2 | 64-bit FullTransactionId I/O |
| `network_gist.c.md` | 2 | inet GiST opclass |
| `network_selfuncs.c.md` | 2 | inet selectivity |
| `network_spgist.c.md` | 2 | inet SP-GiST opclass |
| `inet_cidr_ntop.c.md` | 2 | inet→string conversion |
| `geo_selfuncs.c.md` | 2 | Geometry selectivity |
| `geo_spgist.c.md` | 2 | Box/point SP-GiST |
| `jsonb_gin.c.md` | 3 | jsonb GIN opclass |
| `jsonbsubs.c.md` | 2 | jsonb subscripting |
| `jsonpath_internal.h.md` | 0 | (header) |
| `array_expanded.c.md` | 2 | Expanded-array discipline |
| `array_selfuncs.c.md` | 2 | Array selectivity |
| `arraysubs.c.md` | 2 | Array subscripting |
| `amutils.c.md` | 2 | AM generic helpers |
| `rangetypes_gist.c.md` | 2 | Range GiST opclass |
| `rangetypes_selfuncs.c.md` | 2 | Range selectivity |
| `rangetypes_spgist.c.md` | 2 | Range SP-GiST opclass |
| `rangetypes_typanalyze.c.md` | 2 | Range ANALYZE |
| `multirangetypes_selfuncs.c.md` | 2 | Multirange selectivity |
| `orderedsetaggs.c.md` | 3 | Per-row allocation; OOM on huge input |
| `tsginidx.c.md` | 3 | GIN opclass for tsvector |
| `tsgistidx.c.md` | 3 | GiST opclass for tsvector |
| `tsquery_cleanup.c.md` | 2 | Normalization stack-guarded |
| `tsquery_gist.c.md` | 2 | GiST opclass for tsquery |
| `tsquery_op.c.md` | 2 | tsquery operators |
| `tsquery_rewrite.c.md` | 2 | `ts_rewrite` cycle handling |
| `tsquery_util.c.md` | 3 | Internals; check_stack_depth coverage |
| `tsrank.c.md` | 2 | Ranking math; NaN handling |
| `trigfuncs.c.md` | 2 | Trigonometric edge cases |
| `pseudotypes.c.md` | 2 | Pseudo-type assertions |
| `skipsupport.c.md` | 0 | Trivially small |
| `waitfuncs.c.md` | 2 | Wait-event introspection |
| `multixactfuncs.c.md` | 2 | Multixact SQL exposure |
| `pg_upgrade_support.c.md` | 4 | (covered in P0) |
| `ddlutils.c.md` | 2 | DDL helper utilities |
| `funccache.c.md` | 2 | Function-call result cache |
| `relfilenumbermap.c.md` | 2 | Reverse-map lookups |
| `relmapper.c.md` | 4 | Shared-catalog map; failure mode |
| `oid8.c.md` | 2 | Scalar uint64 OID (not array — task framing error) |
| `bool.c.md` | 1 | Boolean I/O |
| `char.c.md` | 1 | Single-byte char |
| `inet_net_pton.c.md` | 3 | (listed above) |
| `datum.c.md` | 1 | Datum helpers |

---

## Cross-corpus pattern reinforcement

### The SecretBuf cluster reaches seven sweeps

A2 libpq + A4 psql/streamutil/initdb + A5 common (hosting site identified) + A6 pg_upgrade + now A7 utils (cryptohashfuncs minimal surface; ri_triggers safe; the gap remains in common/ from A5 — utils consumers would inherit the fix).

### genfile.c is the server-side dependency of A6 pg_rewind

A6 found pg_rewind's `libpq_source.c:562` uses `pg_read_binary_file()` returning null = unlink-target-file primitive. A7 found the server side: `pg_read_server_files` membership = total bypass; non-members can still escape via `Log_directory`. **Combined finding:** a malicious pg_rewind source with `pg_read_server_files` membership can list AND read AND (via null-bytea response from genfile when it errors) silently delete target files. Worth a coordinated patch.

### `processSQLNamePattern` / `patternToSQLRegex` / `ri_triggers.c quoteOneName` are three confirmed-safe pattern/identifier helpers

A4 found `processSQLNamePattern` (LIKE patterns from psql/pg_dump); A6 found `patternToSQLRegex` (regex patterns from pg_amcheck); A7 confirms `quoteOneName` in `ri_triggers.c` is correct. All three live in `fe_utils/string_utils.c` or `ruleutils.c`. Single `knowledge/idioms/safe-sql-identifiers.md` doc would document the pattern.

### XML parser is the third "trust an external library" gap

A5 found `pg_lzcompress.c` lacks decompression-ratio bound. A7 found `xml.c` uses custom XXE defense instead of `XML_PARSE_NONET`. Both inherit safety from upstream library behavior. Worth a single Phase D pitch hardening boundary discipline (cap inputs, set defensive flags) across the corpus's library-wrapper files.

---

## Corpus gaps surfaced (out of batch)

- `src/backend/storage/ipc/signalfuncs.c` — pg_terminate_backend / pg_cancel_backend live HERE, not misc.c (task framing was wrong). Worth single-file audit.
- `src/backend/statistics/{dependencies,mvdistinct}.c` — extended-stats deserialization issues actually live here; pg_dependencies.c / pg_ndistinct.c are just type wrappers.
- `src/backend/regex/*` — already documented (pre-existing) but worth re-verifying given A7's tsquery findings.
- `src/include/utils/*` — header files; mostly already documented but worth a header-completeness pass.

---

## Summary by tag type (rough)

| Type | Count |
|---|---:|
| trust-boundary | 38 |
| dos | 31 |
| info-disclosure | 19 |
| correctness | 35 |
| undocumented-invariant | 78 |
| wire-protocol | 16 |
| path-traversal | 5 |
| stale-todo | 24 |
| dead-code | 14 |
| state-transition | 6 |
| secret-scrub | 4 |
| injection | 3 |
| xxe | 2 |
| crypto-weakness | 2 |
| **Total** | **~310** (some entries double-tagged) |

Severity headline: ~16 `likely`, ~80 `maybe`, rest `nit`/by-design.

THE Phase D pitch order from this sweep:
1. **`genfile.c` hardening** — `O_NOFOLLOW`, refuse `Log_directory` escape (single-function patch, closes the pg_rewind/A6 server-side dependency).
2. **`xml.c` defense-in-depth** — add `XML_PARSE_NONET` + explicit billion-laughs cap.
3. **`pg_upgrade_support.c` gate strengthening** — second-layer check beyond `IsBinaryUpgrade`.
4. **`to_char` input-length cap** — 64 KiB format string limit + output cap.
5. **`record_recv` explicit `check_stack_depth()`** — match `record_in` posture for the binary protocol.
6. **Extended-stats runtime `nattributes` validation** — replace `Assert` with hard check against `STATS_MAX_DIMENSIONS`.
7. **`hbafuncs.c` secret masking** — RADIUS/LDAP password fields stripped from `pg_hba_file_rules.options[]`.

---

## A19 sweep bucket A append (2026-06-11) — backend utils tails

13 files covering `utils/{mb,misc,sort,activity,fmgr}` — small mb compare
routines, GUC support headers, tzparser, injection points, pgstat
shmem/lock, sharedtuplestore, and the fmgr dispatcher. The big
findings:

- **fmgr.c trampoline edge cases** — `pg_stat_user_functions` skews on
  SECURITY DEFINER, fmgr_hook ABORT/END contract subtle, CFuncHash
  has no eviction, function-pointer leaks in NULL-result ERROR.
- **injection_point.c** — documented dlopen leak on detach-after-load,
  TOCTOU between exists-check and dlopen (test-only build so low
  severity).
- **tzparser.c** — header openly admits OOM violates check_hook
  no-ERROR contract (stale TODO), alpha-only filename is sole
  path-traversal defense for `@INCLUDE`.
- **pgstat_shmem.c** — long-standing XXX wishes for
  `dshash_create_in_place`, ad-hoc DB-drop cascade, DSA OOM risk under
  high-cardinality custom stats kinds.
- **sharedtuplestore.c** — SHARED_TUPLESTORE_SINGLE_PASS flag is
  documented dead, read_buffer doubling never shrinks.

### Open / Triaged — A19A append

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | fmgr.c:633-779 | undocumented-invariant | nit | fmgr_hook FHET_START error path skips FHET_END | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:206-216 | undocumented-invariant | nit | pg_stat_user_functions skews for SECURITY DEFINER / proconfig functions (fn_stats forced TRACK_FUNC_ALL) | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:1752-1789 | leak | nit | OidInputFunctionCall et al. self-document as leaky in seldom-executed paths | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:556-558 | leak | nit | CFuncHash unbounded; no eviction, only invalidation on xmin/ctid mismatch | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:802-809 | info-disclosure | nit | function pointer (`%p`) printed in ERROR for NULL-result via DirectFunctionCallN — ASLR-sensitive | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:233 | leak | nit | prosrc not pfree'd when fmgr_lookupByName errors | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:1611,1666 | undocumented-invariant | maybe | Soft-error compliance is per-input-function; ereport(ERROR) inside _in escapes the soft path | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:2098-2108 | undocumented-invariant | nit | CheckFunctionValidatorAccess explicitly notes EXECUTE-priv bypass via cloning | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:2073-2076 | undocumented-invariant | nit | get_fn_opclass_options precondition (must call has_fn_opclass_options first) is implicit | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | fmgr.c:531-532 | style | nit | CFuncHash invalidation on FREEZE causes refetch (perf nit only) | open | knowledge/files/src/backend/utils/fmgr/fmgr.c.md |
| 2026-06-11 | injection_point.c:162-173 | leak | nit | Documented dlopen leak on detach-after-load | open | knowledge/files/src/backend/utils/misc/injection_point.c.md |
| 2026-06-11 | injection_point.c:189-198 | correctness | nit | TOCTOU between pg_file_exists and load_external_function (test-only) | open | knowledge/files/src/backend/utils/misc/injection_point.c.md |
| 2026-06-11 | injection_point.c:359-390 | style | nit | max_inuse can drift higher than strictly needed after middle-slot frees | open | knowledge/files/src/backend/utils/misc/injection_point.c.md |
| 2026-06-11 | injection_point.c:460-505 | style | nit | O(n) point lookup, acceptable at MAX=128 | open | knowledge/files/src/backend/utils/misc/injection_point.c.md |
| 2026-06-11 | injection_point.c:477 | style | nit | memcmp(name, namelen+1) trusts strlcpy NUL termination | open | knowledge/files/src/backend/utils/misc/injection_point.c.md |
| 2026-06-11 | tzparser.c:9-12 | stale-todo | maybe | Header openly admits OOM-via-ereport escapes check_hook no-ERROR convention | open | knowledge/files/src/backend/utils/misc/tzparser.c.md |
| 2026-06-11 | tzparser.c:294-306 | undocumented-invariant | maybe | Alpha-only filename check is sole path-traversal defense for @INCLUDE | open | knowledge/files/src/backend/utils/misc/tzparser.c.md |
| 2026-06-11 | tzparser.c:415-419 | undocumented-invariant | nit | @OVERRIDE flag scope vs @INCLUDE recursion is subtle | open | knowledge/files/src/backend/utils/misc/tzparser.c.md |
| 2026-06-11 | tzparser.c:250-263 | style | nit | Quadratic insertion sort, acceptable at current sizes | open | knowledge/files/src/backend/utils/misc/tzparser.c.md |
| 2026-06-11 | pgstat_shmem.c:204-206 | stale-todo | nit | XXX wish for dshash_create_in_place — long-standing | open | knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md |
| 2026-06-11 | pgstat_shmem.c:1039-1041 | stale-todo | nit | XXX ad-hoc database-drop cascade | open | knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md |
| 2026-06-11 | pgstat_shmem.c:625 | undocumented-invariant | maybe | release-vs-pending ordering contract; elog(ERROR) on misuse | open | knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md |
| 2026-06-11 | pgstat_shmem.c:680-685 | correctness | nit | Cache delete elog ERROR after shared refcount mutation = partial state | open | knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md |
| 2026-06-11 | pgstat_shmem.c:548-552 | undocumented-invariant | maybe | DSA OOM under high-cardinality custom stats kinds | open | knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md |
| 2026-06-11 | pgstat_shmem.c:1124 | undocumented-invariant | nit | Silent no-op on missing entry for pgstat_reset_entry | open | knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md |
| 2026-06-11 | sharedtuplestore.c:282-286 | stale-todo | nit | SHARED_TUPLESTORE_SINGLE_PASS flag accepted but no semantics | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | sharedtuplestore.c:141-152 | style | nit | strcpy after length check (vs strlcpy convention) | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | sharedtuplestore.c:463-467 | style | nit | errcode_for_file_access on corrupt chunk header — should be ERRCODE_DATA_CORRUPTED | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | sharedtuplestore.c:201 | undocumented-invariant | nit | memset after BufFileWrite relies on synchronous-copy semantics | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | sharedtuplestore.c:434 | leak | maybe | read_buffer doubling never shrinks within accessor lifetime | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | sharedtuplestore.c:124-130 | undocumented-invariant | nit | SharedTuplestore name uniqueness within fileset is caller responsibility | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | sharedtuplestore.c:232-246 | undocumented-invariant | nit | sts_reinitialize caller-side sync requirement | open | knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md |
| 2026-06-11 | pgstat_lock.c:130-133,145-148 | correctness | nit | release-build bounds check missing on locktag_type; Assert-only | open | knowledge/files/src/backend/utils/activity/pgstat_lock.c.md |
| 2026-06-11 | pgstat_lock.c:147 | style | nit | no clamp on negative msecs input | open | knowledge/files/src/backend/utils/activity/pgstat_lock.c.md |
| 2026-06-11 | pgstat_lock.c:133,149 | undocumented-invariant | nit | side effect on pgstat_report_fixed is implicit cross-module coupling | open | knowledge/files/src/backend/utils/activity/pgstat_lock.c.md |
| 2026-06-11 | queryenvironment.c:138 | undocumented-invariant | maybe | TupleDesc returned via NoLock open relies on outer relation pin | open | knowledge/files/src/backend/utils/misc/queryenvironment.c.md |
| 2026-06-11 | queryenvironment.c:109 | style | nit | linear strcmp lookup, O(N²) for N ENRs | open | knowledge/files/src/backend/utils/misc/queryenvironment.c.md |
| 2026-06-11 | queryenvironment.c:- | undocumented-invariant | nit | ENR name case-sensitivity contract implicit | open | knowledge/files/src/backend/utils/misc/queryenvironment.c.md |
| 2026-06-11 | help_config.c:113-114 | correctness | nit | misleading exit status (still 0) on unknown vartype | open | knowledge/files/src/backend/utils/misc/help_config.c.md |
| 2026-06-11 | help_config.c:66-69 | stale-todo | nit | comment references nonexistent user-mode output switch | open | knowledge/files/src/backend/utils/misc/help_config.c.md |
| 2026-06-11 | pg_config.c:23-49 | info-disclosure | nit | compile-time paths/options exposed to PUBLIC (intentional; fingerprinting surface) | open | knowledge/files/src/backend/utils/misc/pg_config.c.md |
| 2026-06-11 | stringinfo_mb.c:80-82 | undocumented-invariant | nit | "tail has no apostrophe" invariant implicit in quoted-string emission | open | knowledge/files/src/backend/utils/mb/stringinfo_mb.c.md |
| 2026-06-11 | stringinfo_mb.c:45 | style | nit | strlen called unconditionally even when about to clip | open | knowledge/files/src/backend/utils/mb/stringinfo_mb.c.md |
| 2026-06-11 | wstrcmp.c:43-46 | correctness | nit | signed-vs-unsigned promotion asymmetry between loop compare and return | open | knowledge/files/src/backend/utils/mb/wstrcmp.c.md |
| 2026-06-11 | wstrncmp.c:- | doc-drift | nit | divergence from wstrcmp.c sibling on char→pg_wchar widening (unsigned cast added here) | open | knowledge/files/src/backend/utils/mb/wstrncmp.c.md |

### A19A notes

- Several files in this bucket are "tail" infrastructure (mb compare
  primitives, GUC private header) with effectively zero issues —
  recorded as 1-2 nits each to preserve audit coverage.
- The `fmgr.c` trampoline is the highest-value target for follow-up
  review: it owns SECURITY DEFINER, proconfig GUC override, and the
  fmgr_hook plugin entry/exit contract. Anything that goes wrong
  there has system-wide blast radius.
- The injection_point.c lock-free generation protocol is well-commented
  and looks correct; tagged nits are quality-of-impl only.


---

## ISSUE-mode triage 2026-07-13 (pg-quality-auditor) — 18 line-cited rows re-verified @eed6c0d33e09

All 18 `[pending]` `utils` rows in `progress/_queues/issues.md` (seeded
2026-07-12) re-fetched at anchor `eed6c0d33e09` via raw.githubusercontent.
**16 still-present** (cite exact or ≤1-line drift, left as-is); **2
re-anchored** (reproducer drifted — pattern intact elsewhere in the file).

Still-present (cite verified exact unless noted):

- `genfile.c:53-92` trust-boundary — `convert_and_check_filename` + the
  `has_privs_of_role(...ROLE_PG_READ_SERVER_FILES)` bypass at `:66`; intact.
- `genfile.c:65` path-traversal — `Log_directory` escape block (`:71-82`),
  `!path_is_prefix_of_path(Log_directory, filename)`; intact.
- `xml.c:2046,1319` xxe — `xmlSetExternalEntityLoader(xmlPgEntityLoader)` at
  `:1319` exact; loader def at `:2046` (sig line) / `:2047` (name). No
  `XML_PARSE_NONET` anywhere; `XML_PARSE_NOENT` set at `:1886`. Intact.
- `xml.c:2042` stale-todo — "global XML catalog" comment now at `:2043-2044`
  (≤2-line drift, within tolerance). Intact.
- `formatting.c:3907` dos — `result = palloc(mul_size(fmt_len, DCH_MAX_ITEM_SIZ)+1)`
  exact at `:3907`; no format-length cap. Intact.
- `formatting.c:6236` correctness — `NUM_TOCHAR_prepare` silent
  `PG_RETURN_TEXT_P(cstring_to_text(""))` exact at `:6236`. Intact.
- `encode.c:282-306` dos — `hex_decode_safe_scalar` scalar loop, no
  `CHECK_FOR_INTERRUPTS`; grep confirms none in the whole file. A SIMD
  helper path (`hex_decode_simd_helper` :319 / `hex_decode_safe` :351) was
  added but also lacks an interrupt check. Pattern intact.
- `tsvector.c:461` dos — `if (nentries < 0 || nentries > (MaxAllocSize / sizeof(WordEntry)))`
  exact at `:461`. Intact.
- `tsquery.c:1240` dos — `if (size > (MaxAllocSize / sizeof(QueryItem)))`
  exact at `:1240`. Intact.
- `multirangetypes.c:352` dos — `ranges = palloc_array(RangeType *, range_count)`
  exact at `:352`, pre-alloc from 4-byte wire count at `:350`. Intact.
- `pg_dependencies.c (+ mvdistinct.c:310, dependencies.c:557)` trust-boundary —
  `Assert((k >= 2) && (k <= STATS_MAX_DIMENSIONS))` exact at
  `statistics/dependencies.c:557`; `Assert((item->nattributes >= 2) && ...)`
  exact at `statistics/mvdistinct.c:310`. Assert-only validation (no runtime
  hard check) intact.
- `ruleutils.c:5900-5965` info-disclosure — `make_viewdef` (now `:5903`) emits
  only `get_query_def(...)` + `;`; omits WITH CHECK OPTION / security_barrier /
  security_invoker / ACL. Range still bounds the function. Intact.
- `name.c:57 vs :90` wire-protocol — `namein` truncate at `:57-58`
  (`pg_mbcliplen`); `namerecv` `ERRCODE_NAME_TOO_LONG` at `:90-92`. Both exact.
- `numutils.c:947 vs :983` wire-protocol — `uint32in_subr` minus-sign
  backwards-compat comment at `:947`; `uint64in_subr` def `:984` (register `:983`
  = the `uint64` return-type line, ≤1-line drift) with no minus-sign path. Intact.
- `expandeddatum.c:88-145` undocumented-invariant — `MakeExpandedObjectReadOnlyInternal`
  `:95`, `TransferExpandedObject` `:118`, `DeleteExpandedObject` `:136`; range
  bounds all three. Intact.
- `windowfuncs.c:559` correctness — `(forward ? offset : -offset)` exact at
  `:559`; `-offset` unary-negation UB on `INT32_MIN`, no guard. Intact.

Re-anchored (drift-fixed this run, status stays `open`):

- `tsvector_op.c:926 → :376,380` — cite pointed at the maxpos scan inside
  `tsvector_concat`; the actual `MAXENTRYPOS-1` clamp is in helper `add_pos()`
  (`:376` stop-when-full, `:380` `LIMITPOS`). Register row + per-file doc inline
  tag re-anchored.
- `ri_triggers.c:288 → :4010 (decl :295)` — `:288` is now `ri_NullCheck`;
  `ri_CompareWithCast` def moved to `:4010`, forward-decl `:295`. Register row
  re-anchored. Per-file doc already read `decl 295, def 4010` (register was
  lagging the per-file doc, not vice-versa).

Net: 0 upstream fixes (no `landed`), 2 re-anchors, 16 still-present. The
`utils` line-cited pending register is now drained; `issues.md` refilled from
the `catalog` register (next security-relevant backend register).
