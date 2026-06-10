# Phase D pitch roadmap

**Status:** A→D bridge document. Consolidates the Phase D candidate pitches surfaced across A1–A17 (sweeps 2026-06-02 → 2026-06-09) plus A18 (anchor refresh).

**Inputs:** ~2,720 inline `[ISSUE-*]` tags across 38+ subsystem registers under `knowledge/issues/`. ~1,908 per-file docs covering 74.4% of `src/` + `contrib/` at source pin `e18b0cb7344` (was `4b0bf0788b0` for A1–A17).

**Purpose:** Move from "we mapped the surface" (Phase A) to "we have a prioritized hardening backlog" (Phase D). Each pitch is sized + sited + cross-linked. Triage matrix at the end.

---

## How to read this doc

Three tiers:

1. **Mega-pitches (MP1–MP10)** — cross-corpus patch series that close 3+ findings each. High effort, very high impact. Best PG-hackers list candidates.
2. **Single-site pitches (SP1–SP10)** — focused 1-file or 1-mechanism patches. Moderate effort, concrete impact.
3. **Confirmed bugs (CB1–CB10)** — already-identified concrete bugs that need a fix-and-submit cycle. Lowest effort to file, can run in parallel with mega-pitches.

Plus a **cross-corpus pattern catalog (P1–P9)** documenting the meta-findings that justify the mega-pitches.

---

## MP1 — `SecretBuf` hosting site (10+ secret-scrub sites)

**Pitch:** Add `src/include/common/secretbuf.h` + `src/common/secretbuf.c` providing a caller-owned scrubbing buffer type with `explicit_bzero` discipline. Migrate the ~10 secret-bearing paths to use it.

**Sites closed:**
- libpq A2 — connection-string password buffers freed without scrub
- psql A4 — `~/.psql_history` password capture, `-L` logfile, `\password` buffers, `main()` password buffer
- pg_basebackup A4 — `streamutil.c` connection string buffer
- initdb A4 — `--pwfile` `superuser_password` never zeroed
- common A5 — md5_common, scram-common, hmac, saslprep, sprompt, fe_memutils, logging, pg_get_line, sha1, cryptohash_openssl (10+ sites)
- pg_upgrade A6 — `pg_authid` hash file persistence
- walreceiver A8 — `primary_conninfo` plaintext window in WalRcv shmem
- pgcrypto A11 — wrapped legacy bcrypt/sha-crypt DO scrub but SQL boundary doesn't

**Existence proof:** `src/common/cryptohash.c:243` already does `explicit_bzero(ctx, sizeof(*ctx))` in `pg_cryptohash_free`. The pattern exists; SecretBuf generalizes it.

**Sketch:**
```c
typedef struct SecretBuf {
    char *data;
    size_t len;
    MemoryContext owner;
} SecretBuf;

SecretBuf *secret_buf_create(MemoryContext mcxt, size_t len);
void secret_buf_free(SecretBuf *b);  // calls explicit_bzero + pfree
void secret_buf_reset(SecretBuf *b); // scrub without free
```

**Effort:** ~200 LOC header + impl + ~10 call-site migrations (~50 LOC each). 1 contributor week.
**Impact:** Closes a documented decade-long backlog (A5 finding); makes "secret leaves a heap residue" structurally impossible in migrated paths.
**Cross-corpus:** A2 libpq + A4 psql/pg_basebackup/initdb + A5 common + A6 pg_upgrade + A8 walreceiver + A11 pgcrypto. 6-sweep cluster.

---

## MP2 — StringInfo quoting helpers (closes A7+A13+A14 injection cluster)

**Pitch:** Add `appendStringInfoQuotedIdentifier(StringInfo s, const char *name)` and `appendStringInfoShellQuoted(StringInfo s, const char *str)` to `src/include/lib/stringinfo.h` + `src/common/stringinfo.c`. These are the canonical safe helpers callers should reach for instead of `appendStringInfo(s, "%s", untrusted)`.

**Sites closed:**
- A13 tablefunc.connectby_text — 5 of 6 identifier args interpolated raw via `appendStringInfo` (`tablefunc.c:1227-1247`). **CB2 below.**
- A14 basebackup_to_shell — `%X` substitution model fragile (`basebackup_to_shell.c:211-217`)
- A7 to_char — `formatting.c` unbounded format strings (50 MB → 600 MB palloc) — also see SP2.
- A14 cube cubeparse — 16 MB palloc upstream of CUBE_MAX_DIM check (`cubeparse.y:154-166`)
- A11 dblink conninfo construction — partial coverage of identifier paths
- A11 postgres_fdw — shippable function/aggregate resolution by NAME

**Sketch:**
```c
/* In stringinfo.h */
extern void appendStringInfoQuotedIdentifier(StringInfo str, const char *name);
extern void appendStringInfoShellQuoted(StringInfo str, const char *s);

/* Migration example — tablefunc.connectby_text:1227 */
- appendStringInfo(&sql, "SELECT %s, %s FROM %s WHERE %s = %s",
-                  key_fld, parent_key_fld, relname, parent_key_fld,
-                  quote_literal_cstr(start_with));
+ appendStringInfoString(&sql, "SELECT ");
+ appendStringInfoQuotedIdentifier(&sql, key_fld);
+ appendStringInfoString(&sql, ", ");
+ appendStringInfoQuotedIdentifier(&sql, parent_key_fld);
+ appendStringInfoString(&sql, " FROM ");
+ appendStringInfoQuotedIdentifier(&sql, relname);
+ /* ... etc */
```

**Effort:** ~40 LOC helpers + ~5-10 high-value migrations + tree-wide grep audit. 3 days.
**Impact:** Closes the **5-sweep text-injection cluster**; makes future contrib/extension `appendStringInfo` calls hard to misuse.
**Cross-corpus:** A7 + A13 + A14 + A11 = 4 sweeps. Header anchor: `src/include/lib/stringinfo.h:193-256`.

---

## MP3 — pgcrypto modernization series (closes 6+ findings)

**Pitch:** Coordinated OpenSSL-3.0-era refresh of `contrib/pgcrypto`. Multiple sub-patches, one CF entry.

**Sub-patches:**

1. **`EVP_CIPHER_fetch` / `EVP_MD_fetch` migration** — port `contrib/pgcrypto/openssl.c` from deprecated `EVP_aes_128_cbc()` family to OpenSSL 3.0 provider-aware `EVP_CIPHER_fetch("AES-128-CBC", NULL)`. Lands the in-tree wrapper in `src/include/common/openssl.h` (A16 anchor — currently zero callsites).
2. **AEAD modes** — add GCM / CCM / ChaCha20-Poly1305 to `encrypt()` / `decrypt()` family. **Currently zero AEAD support in 2026.** Closes raw HMAC + SQL `=` timing-attack surface.
3. **`explicit_bzero` adoption** — replace `px_memset` (LTO-elidable) with `explicit_bzero` across `OSSLCipher` key/iv buffers + S2K outputs (10+ sites in pgcrypto). Cross-references MP1 SecretBuf.
4. **`BN_FLG_CONSTTIME` on RSA/Elgamal** — `BN_mod_exp` called without flag for `pgp_rsa_decrypt` / `pgp_elgamal_decrypt` (`pgp-mpi-openssl.c:266,183`). Classic Brumley-Boneh 2003 timing attack. **One-line fix per site.**
5. **S2K iter cap GUC** — `pgp_sym_decrypt` attacker controls iter via bytea (`pgp-s2k.c:270`). Add `pgcrypto.s2k_max_iterations` GUC (default ~16M = ~1s wall time).
6. **PGP decompression-bomb ceiling** — `pgp_sym_decrypt(small_compressed_blob, pw)` has NO output-size ceiling (`pgp-compress.c:278-310`). Add `pgcrypto.max_decompressed_size` GUC + enforce in `pgp_create_pkt_reader`. **CB1 below.**
7. **`ERR_get_error()` drain** — pgcrypto silently discards OpenSSL error stack (`px.c:42-84`). Add `pg_openssl_error_drain(StringInfo)` helper in `common/openssl.h`; adopt throughout pgcrypto.
8. **`crypt('aa')` deprecation warning** — `crypt(pw, 'aa')` silently returns DES. Add `WARNING` for `salt[0..1]` that selects DES; consider `pgcrypto.allow_legacy_crypt` PGC_SUSET GUC.
9. **`gen_salt('bf')` default bump** — currently cost=5 (OWASP min 12). Bump default to cost=12 + GUC override.

**Effort:** Large. ~600 LOC across 8-10 commits. 3-4 contributor weeks. Best-shaped as a CF entry with multiple commits.
**Impact:** Brings pgcrypto into OpenSSL 3.0 era; closes the most concrete known crypto findings in PG.
**Cross-corpus:** A11 pgcrypto + A5 pg_lzcompress + A16 openssl.h. 3-sweep cluster.

---

## MP4 — Centralized utility-statement PASSWORD redaction (closes A11 3-header cluster)

**Pitch:** Add a single chokepoint that redacts `PASSWORD '...'` literals from parsetree-string conversion before it reaches monitoring infrastructure. Hook all three current sinks.

**Sites closed:**
- A11 pg_stat_statements `track_utility=on` captures `CREATE/ALTER USER PASSWORD '...'` cleartext in `pgss_query_texts.stat` (readable by `pg_read_all_stats`). **A17 confirmed at API layer.**
- A17 `nodes/queryjumble.h:93-97` — utility statements EXCLUDED from normalization; jumble path stores verbatim text.
- A17 `tcop/cmdtaglist.h:53-94` — event-trigger dispatch table; handlers see raw parsetree including PASSWORD literals.
- A17 `tcop/deparse_utility.h:44-49` — `CollectedCommand.parsetree` retains PASSWORD nodes for logical-replication apply.
- A4 psql secret-scrub cluster — same family at frontend.
- A18 confirmed `psql/describe.c` schema-qualification fixes are A4-adjacent.

**Sketch:** Add `src/backend/parser/parse_password_redact.c` with:
```c
/* Walk a parsetree replacing AlterRoleStmt/CreateRoleStmt PASSWORD literals
 * with the constant string '<REDACTED>'. Used by:
 *   - pgss_store before jumbling
 *   - event-trigger handler dispatch
 *   - logical-replication command deparse
 *   - log_statement formatting
 */
Node *redact_password_literals(Node *parsetree);
```

Wire it into:
- `pg_stat_statements.c::pgss_store` before query-text capture
- `commands/event_trigger.c::EventTriggerCommonSetup` before passing parsetree to handlers
- `replication/logical/launcher.c` worker apply path
- `tcop/postgres.c::log_statement` formatting

**Effort:** ~150 LOC walker + 4 call-site changes + tests. 1 week.
**Impact:** Closes the A4 + A11 + A17 cleartext-password 3-header cluster centrally.
**Cross-corpus:** A4 + A11 + A17 = 3-sweep cluster.

---

## MP5 — AM/extension-routine version+magic+selfcheck (closes "load arbitrary code" thread)

**Pitch:** Add version/magic fields + optional self-check hook to the extension-loadable routine structs. Closes the "load arbitrary AM/output_plugin" thread at the validation layer.

**Sites closed:**
- A17 `amapi.h:233` — `IndexAmRoutine` required callbacks Assert-only in cassert-off prod
- A17 `tableam.h:312` — `TableAmRoutine` required callbacks Assert-only
- A17 `nodeCustom.h:21` — `CustomExecMethods` vtable unsandboxed extension RCE surface
- A14 `tsmapi.h:37` — `TsmRoutine` no bounds check
- A8 `replication/logical/logical.c::LoadOutputPlugin` — output_plugin name → dlopen primitive (5th "load arbitrary code" in corpus)
- A6 `pg_upgrade::check_loadable_libraries` — actually `LOAD`s old-cluster `.so` files on NEW cluster (**CB9** below)

**Sketch:**
```c
/* In amapi.h */
#define INDEX_AM_ROUTINE_VERSION 1
typedef struct IndexAmRoutine {
    NodeTag type;
    uint32  magic;          /* = 0xA1AB000_INDEX_AM_ROUTINE_VERSION */
    uint32  version;
    /* required callbacks */
    ambuild_function ambuild;
    /* ... */
    /* optional self-check (new) */
    ambeselfcheck_function ambeselfcheck;
} IndexAmRoutine;

/* In RegisterIndex etc. */
if (routine->magic != EXPECTED_INDEX_AM_MAGIC)
    ereport(ERROR, errcode(ERRCODE_INVALID_OBJECT_DEFINITION),
            errmsg("index AM \"%s\" has invalid routine magic", amname));
if (routine->ambuild == NULL)
    ereport(ERROR, errmsg("index AM \"%s\" missing required callback ambuild", amname));
if (routine->ambeselfcheck != NULL && !routine->ambeselfcheck(&error))
    ereport(ERROR, errmsg("index AM \"%s\" self-check failed: %s", amname, error));
```

Same pattern for `TableAmRoutine`, `CustomExecMethods`, `TsmRoutine`. Output_plugin gets a stricter version: validate the `OutputPluginCallbacks` struct + reject any `_PG_init` side effects until validation succeeds.

**Effort:** Medium. ~80 LOC per routine type × 4 routine types + Phase-D ambeselfcheck hooks for in-tree AMs. ~3 weeks.
**Impact:** Closes "load arbitrary code" Phase D thread at validation layer for 5 primitives.
**Cross-corpus:** A6 + A8 + A14 + A17 = 4-sweep cluster.

---

## MP6 — MCV-leak central chokepoint (closes per-estimator gap)

**Pitch:** Refactor the per-estimator `statistic_proc_security_check` + `acl_ok` gate (A15 finding) into a single chokepoint, eliminating the "new estimators forget to call it" risk.

**Sites closed:**
- A15 `selfuncs.h:99-100,165` — per-estimator gate enforced N times across the planner
- A15 + A17 `selfuncs.h:149-158` — `get_relation_stats_hook` / `get_index_stats_hook` FDW override path bypasses the audit trail (A11 echo)
- CVE history — MCV leakage is a well-known CVE class (CVE-2017-7484 family)

**Sketch:** Move the gate into `get_attstatsslot` / `get_relation_statistics` so estimators receive ALREADY-FILTERED stats, not raw + check-or-skip. Drop the per-estimator `acl_ok` argument. Add a regression test that exercises a custom selectivity estimator that "forgets" the check — the new chokepoint makes the failure impossible to express.

**Effort:** Medium. ~200 LOC + ~20 estimator-site migrations + tests. 2 weeks.
**Impact:** Closes a recurring CVE class structurally.
**Cross-corpus:** A11 postgres_fdw stats-import + A12 amcheck/pageinspect/pgstattuple + A15 selfuncs.h.

---

## MP7 — Monitoring-as-extraction per-relation gate (closes 8+ site cluster)

**Pitch:** Add a documented "monitoring-with-RLS-awareness" mode for integrity / introspection functions that currently expose RLS-protected data.

**Sites closed (8+ sites):**
- A7 `genfile.c` — `pg_read_server_files` total bypass
- A11 `pg_stat_statements` — `track_utility=on` password capture (covered by MP4 too)
- A12 `amcheck` — zero C-side permission checks + page LSN/heap-TID/XID leak in errdetail
- A12 `pageinspect` — `tuple_data_split(do_detoast=true)` cross-table read
- A12 `pgstattuple` — VM-trust fail-open + RLS row-count leak
- A14 `pg_walinspect` — `show_data=true` raw FPI bytes (most sensitive)
- A14 `pg_visibility` — no C-side privilege checks on 8 entrypoints
- A14 `pg_buffercache` — REVOKE-only gate, no per-relation check
- A14 `pgrowlocks` — per-tuple lock-holder PID disclosure
- A17 `syncscan.h:25` — cross-tenant seq-scan position leak (128-block granularity)
- A17 `sequence.h:20` — cross-tenant `nextval()` side-channel

**Sketch:** Add a per-function macro `MONITORING_RLS_CHECK(rel)` that:
1. Verifies `has_table_privilege(relid, 'SELECT')` for the caller
2. If RLS is enabled on `rel`, verifies caller is BYPASSRLS or owner
3. Logs the access if `monitoring.audit_rls_bypass = on`

Adopt across the 11+ sites above. Provide a "fail-closed" GUC `monitoring.require_per_relation_check` (default off for backwards compat; on for security-conscious deployments).

**Effort:** Medium-large. ~100 LOC macro + ~15 site migrations + GUC plumbing + tests. 3 weeks.
**Impact:** Closes the **8+ site monitoring-as-extraction cluster** in one coherent series. Could be a major Phase D press piece.
**Cross-corpus:** A7 + A11 + A12 + A14 + A17 = 5-sweep cluster.

---

## MP8 — Hardened `readfuncs.h` deserializer

**Pitch:** Make `stringToNode` reject unknown / unexpected node tags by default. Document the catalog columns + IPC paths that carry serialized node trees.

**Sites closed:**
- A17 `nodes/readfuncs.h:36` — hostile-input deserializer never named as trust boundary
- A14 `prs2lock.h:24-32` — `pg_rewrite.ev_action` node-tree string deserialized by readfuncs
- A14 `pg_proc.prosrc` (for SQL functions), `pg_class.relpartbound`, plan-cache, parallel-worker DSM, logical-replication apply (7+ sources, not all fully sanitized at write)

**Sketch:** Add a `READ_STRICT` flag to `stringToNode` that:
1. Rejects unknown node tags (vs current silent skip)
2. Rejects unexpected types in typed slots (Const→Const, not Const→FuncExpr)
3. Optionally validates against a per-callsite allowlist

Cross-reference catalog columns that carry node trees in a header comment so future maintainers add to the allowlist.

**Effort:** Medium. ~150 LOC + per-callsite mode selection + tests. 2 weeks.
**Impact:** Closes the silent-deserialize-hostile-bytes Phase D concern across 7+ catalog/IPC sources.
**Cross-corpus:** A14 hstore forgery + A17 readfuncs.h hostile-deserialization. 2-sweep cluster, but high latent value.

---

## MP9 — `heap_fetch_toast_slice` toastrel cross-check

**Pitch:** Add a `valueid → toastrel` ownership check in `heap_fetch_toast_slice`. Closes A12's `tuple_data_split(do_detoast=true)` cross-table read primitive at the API layer.

**Sites closed:**
- A17 `heaptoast.h:145` — `heap_fetch_toast_slice(rel, valueid, ...)` API trusts caller-supplied valueid against toastrel (the API host)
- A12 `pageinspect::tuple_data_split(do_detoast=true)` — caller-supplied toast pointer can reference any TOAST relation
- A14 `pg_surgery` — adjacent risk if force-* operations ever take toast pointers

**Sketch:**
```c
HeapTuple
heap_fetch_toast_slice(Relation toastrel, Oid valueid,
                       int32 attrsize, int32 sliceoffset,
                       int32 slicelength, struct varlena *result)
{
    /* NEW: verify valueid is a chunk_id owned by toastrel */
    if (!toast_chunkid_belongs_to_toastrel(toastrel, valueid))
        ereport(ERROR,
                errcode(ERRCODE_FEATURE_NOT_SUPPORTED),
                errmsg("toast valueid %u does not belong to toast relation %s",
                       valueid, RelationGetRelationName(toastrel)));
    /* ... existing logic */
}
```

A maintaining catalog `pg_toast_chunkid_owner(valueid)` may be needed, OR the check can scan the first chunk's `chunk_id` row for ownership (cheap when toast is hit anyway).

**Effort:** Small. ~80 LOC + test exercising the cross-relation read. 3-5 days.
**Impact:** Closes a concrete A12 finding at the canonical API layer.
**Cross-corpus:** A12 + A14 + A17 = 3-sweep cluster.

---

## MP10 — RLS `leakproof`/`stable` runtime cross-check

**Pitch:** Add a runtime guard that catches mis-flagged extension support functions / subscripting handlers BEFORE they reorder RLS quals.

**Sites closed:**
- A17 `subscripting.h:39-48` — extension-set leakproof flag self-asserted
- A17 `supportnodes.h:114-116` — `InlineInFrom` can drop RLS quals if implementer not careful
- A11 postgres_fdw shippable functions — similar trust by name

**Sketch:** In `match_clauses_to_rel`, when reordering quals based on a function's `proleakproof`, do a debug-mode (`Assert`) cross-check: walk the function body for known leak primitives (ereport with %s of args, dlopen, etc.) and FAIL if found in a function flagged leakproof. Don't enable in production (too expensive); make it a `pg_dump`-time / `CREATE FUNCTION`-time check that warns.

Alternative: enforce at `CREATE FUNCTION ... LEAKPROOF` time — verify the function body doesn't call non-leakproof functions transitively. Reject if so.

**Effort:** Medium-large. ~250 LOC walker + tests. 3 weeks.
**Impact:** Catches a class of silent RLS-leak vulnerabilities at extension-author-write time.
**Cross-corpus:** A11 + A17 = 2-sweep, but high latent CVE risk.

---

## SP1 — SCRAM iteration cap GUC

**Pitch:** Add `scram.max_iterations` GUC (default 1M = OWASP 2026 / 4× recommendation). `scram-common.h:50` finding.

**Sketch:** Frontend-side reject ServerSignature with iter > GUC. Backend-side reject `SCRAM-SHA-256$iter:salt$...` strings with iter > GUC. Prevents malicious server from coercing client into long PBKDF2 + DoS during connection storms.

**Effort:** ~30 LOC + tests. 1 day.
**Impact:** Closes A16 finding; defense-in-depth for connection-storm scenarios.

---

## SP2 — `pg_str{lower,upper,fold}` MaxAllocSize cap

**Pitch:** Add caller-side `MaxAllocSize` cap before invoking ICU's 3× casemap expansion. A15+A16 finding (`pg_locale.h:183-194` + `formatting.h:21-24`).

**Sketch:** Wrap with size-check helper:
```c
if (srclen > MaxAllocSize / 3)
    ereport(ERROR, errmsg("input string too long for case folding"));
```

**Effort:** ~10 LOC × 4 sites + tests. 1 day.
**Impact:** Closes A7's 50 MB → 600 MB to_char echo at the case-folding layer. Affects citext (A13), pg_trgm (A14), every text comparison.

---

## SP3 — `pg_get_viewdef` security-clause round-trip

**Pitch:** Make `pg_get_viewdef()` re-emit `WITH (security_barrier=...)` / `security_invoker` / `check_option`. A7 cross-finding confirmed at header layer by A15 (`ruleutils.h:54` + `rel.h:426-485`).

**Sketch:** ~30 LOC in `ruleutils.c::pg_get_viewdef_internal` — append the WITH clause from `rel->rd_options`. `pg_dump` already does this via direct `pg_class.reloptions` read; the SQL function should match.

**Effort:** ~50 LOC + tests. 2 days.
**Impact:** Closes A7 cross-finding; eliminates user-confusion vector ("but `pg_get_viewdef` didn't show security_barrier!").

---

## SP4 — `execParallel.h` security-envelope documentation

**Pitch:** Add a header-level contract block to `src/include/executor/execParallel.h` enumerating what's serialized into worker DSM (user identity, search_path, SecurityRestrictionContext, snapshot, PARAM_EXEC) and what the parallel_safe/restricted labels MUST guarantee.

**Effort:** Documentation-only. ~80 lines of header comment. ½ day.
**Impact:** Reduces the "new parallel-aware code mis-labels a function" risk class.

---

## SP5 — `lwlocklist.h` CI cross-check

**Pitch:** Add a CI lint that asserts `src/include/storage/lwlocklist.h` IDs match `src/backend/utils/activity/wait_event_names.txt` entries. A15 finding.

**Sketch:** A Perl script in `src/tools/ci/` that parses both files and diffs the lock-name sets. Run in GitHub Actions.

**Effort:** ~50 LOC perl + workflow integration. 1 day.
**Impact:** Catches silent gaps in `pg_stat_activity` wait reporting when locks are added/removed.

---

## SP6 — `autoprewarm` REVOKE-from-PUBLIC

**Pitch:** Add `REVOKE EXECUTE ON FUNCTION autoprewarm_start_worker, autoprewarm_dump_now FROM PUBLIC` to `pg_prewarm--1.6.sql` (or current). A14 finding.

**Sketch:** 2 lines of SQL in the upgrade file + matching downgrade entry.

**Effort:** ~5 LOC + back-patch consideration. 1 hour.
**Impact:** Closes CB5 (PUBLIC autoprewarm controls).

---

## SP7 — `tablefunc.connectby_text` identifier quoting

**Pitch:** Wrap the 5 raw-interpolated identifier args in `tablefunc.c:1227-1247` with `quote_identifier`. Use MP2's `appendStringInfoQuotedIdentifier` once MP2 lands.

**Effort:** ~10 LOC + regression test exercising hostile column name. 1 day.
**Impact:** Closes CB2 (tablefunc SQL injection).

---

## SP8 — Per-process keying in `hashfn.h`

**Pitch:** Add a per-process random salt to the hashfn family to defend against hash-flood DoS on dynahash tables with attacker-controlled keys.

**Sketch:**
```c
static uint64 pg_hashfn_global_seed;  /* initialized once from pg_strong_random */

uint32
hash_bytes(const unsigned char *k, int keylen)
{
    /* mix in pg_hashfn_global_seed */
    ...
}
```

Document explicitly: "fasthash family STILL stable across runs; only `hash_bytes` gets keyed." A16 finding (`hashfn.h:23`).

**Effort:** ~50 LOC + tests + perf benchmark. 1 week.
**Impact:** Closes hash-flood DoS surface on dynahash, simplehash, syscache.

---

## SP9 — `nodeCustom` provider attestation

**Pitch:** Add an opt-in supply-chain attestation field to `CustomExecMethods` — a signed manifest indicating the provider/version. A17 finding (`nodeCustom.h:21`).

**Sketch:** New `CustomScanProviderManifest` struct that the extension declares; `RegisterCustomScanMethods` validates against an optional GUC allowlist (`custom_scan.allowed_providers = 'citus@1.0,timescale@*'`).

**Effort:** Large; requires hackers-list discussion on the manifest format. ~300 LOC + design memo. 2-3 weeks.
**Impact:** Hardens the supply-chain attack surface for Citus/Timescale/Hydra/pg_strom deployments.

---

## SP10 — PS title password redaction

**Pitch:** Add `pgsql_redact_ps_title()` to `set_ps_display` that redacts PASSWORD literals before publishing. A15 finding (`ps_status.h:32`).

**Sketch:** ~30 LOC scan-and-replace + tests covering `ALTER USER ... PASSWORD '...'`. Optional GUC `track_ps_redact_passwords` (default on).

**Effort:** ~50 LOC + tests. 2 days.
**Impact:** Closes A15 finding (any OS user seeing SQL text via `ps`).

---

## CB1 — 🚨 pgcrypto decompression bomb (`pgp-compress.c:278-310`)

**Status:** Confirmed. A11 critical finding. **Closed by MP3 sub-patch 6.**

`pgp_sym_decrypt(small_compressed_blob, pw)` has NO output-size ceiling. 10 KB ciphertext → multi-GB plaintext → backend OOM. Reachable via public SQL API with attacker-controlled bytea.

**Suggested patch shape:** Add `pgcrypto.max_decompressed_size` GUC (default 1 GiB), enforce in `pgp_create_pkt_reader` + every decompression entry. Defense in depth: also cap intermediate compression-format frames.

---

## CB2 — 🚨 `tablefunc.connectby_text` SQL injection (`tablefunc.c:1227-1247`)

**Status:** Confirmed. A13 critical finding. **Closed by SP7 + MP2.**

5 of 6 identifier args interpolated raw via `appendStringInfo` (`key_fld`, `parent_key_fld`, `relname`, `parent_key_fld`-again). Only `start_with` is `quote_literal_cstr`'d. Apps exposing these to user input = straight-line SQL injection gated only by SPI `read_only=true` (still permits `pg_authid` reads, `pg_read_server_files`).

`build_tuplestore_recursively` has NO `check_stack_depth()` — only `strstr`-based cycle check + user-supplied `max_depth` (0=unlimited).

---

## CB3 — 🚨 sepgsql permissive-mode AVC cache widening (`uavc.c:384`)

**Status:** Confirmed. A12 critical finding.

Permissive-mode AVC cache permanently mutates `cache->allowed`. Flipping `sepgsql.permissive` PERMISSIVE→DEFAULT without policy reload carries widened entries in existing backends. Plus: parallel workers + bgworkers use server's SELinux label as `client_label_peer` and stay in `SEPGSQL_MODE_INTERNAL`, silently non-enforcing AND non-auditing. Plus: `proc.c:279` typo — ALTER FUNCTION SET SCHEMA does NOT check `add_name` on destination namespace.

**Suggested patch shape:** Invalidate AVC cache on `sepgsql.permissive` toggle (RELCACHE_INVALIDATE). Force parallel workers into SEPGSQL_MODE_DEFAULT or document non-enforcement. Fix `proc.c:279` typo.

---

## CB4 — 🚨 pg_walinspect `show_data=true` RLS bypass (`pg_walinspect.c:377-409,425-467`)

**Status:** Confirmed. A14 critical finding. **Partly closed by MP7.**

Returns raw FPI page bytes from WAL including DELETE'd + pre-UPDATE tuple contents. Gated only by `pg_read_server_files` grant, no per-relation check. **Most sensitive A14 finding.**

**Suggested patch shape:** Add per-relation `pg_walinspect.show_data_owner_only` GUC. Optionally require explicit `WITH (table_oids = ARRAY[1234, 5678])` argument that filters to those relations. Audit-log every `show_data=true` access.

---

## CB5 — 🚨 pg_prewarm autoprewarm PUBLIC (`autoprewarm.c:814,846`)

**Status:** Confirmed. A14 critical finding. **Closed by SP6.**

`autoprewarm_start_worker` / `autoprewarm_dump_now` have NO REVOKE in any install script (`pg_prewarm--1.1.sql` etc.) and NO C-side check. Any logged-in user can trigger a full NBuffers dump and contend for buffer-header spinlocks. Plus: autoprewarm dump-file path is unvalidated + `<<N>>` signed-int parse → `dsm_create(20*N)` OOM.

---

## CB6 — 🚨 `pg_surgery.heap_force_freeze` resurrects aborted tuples (`heap_surgery.c:289-308`)

**Status:** Confirmed. A14 critical finding.

Silently makes aborted-xact tuples visible to ALL snapshots, including prior ones that already observed them as aborted. Documented only as "potentially-garbled data" — the snapshot violation is unnamed. HOT-chain root freezes leave dangling successors. Accepts system catalog OIDs.

**Suggested patch shape:** Add `IsCatalogRelation` reject. Document snapshot-violation explicitly in errmsg. Refuse HOT-chain root freeze unless `force_unsafe=true`.

---

## CB7 — 🚨 ltree `parse_lquery` ~400000× memory amplification (`ltree_io.c:322,329`)

**Status:** Confirmed. A13 critical finding.

`parse_lquery` allocates `nodeitem[numOR+1]` PER LEVEL where numOR is the GLOBAL `|` count. A ~256 KB query with ~65000 levels × ~65000 `|`s = ~100 GB scratch.

**Suggested patch shape:** Add `ltree.max_lquery_size` GUC (default ~1 MB). Reject queries exceeding it before allocation.

---

## CB8 — 🚨 hstore forged `HS_FLAG_NEWVERSION` (`hstore_compat.c:242-243`)

**Status:** Confirmed. A13 critical finding.

Fast path trusts version bit on structurally-old hstore — downstream macros (`HSE_ISFIRST`, `HSE_ENDPOS`) read garbage; `HSTORE_KEY`/`HSTORE_VAL` memcpy off attacker-controlled offsets = **controllable OOB-read**. Dump/restore is the realistic forgery vector.

**Suggested patch shape:** Validate the bit against actual structure (check offset arithmetic before trusting flag). Add `hstore_compat.c::hstoreUpgrade` defensive validation.

---

## CB9 — 🚨 pg_upgrade `check_loadable_libraries` RCE

**Status:** Confirmed. A6 critical finding. **Partly closed by MP5.**

Actually `LOAD`s old-cluster-named `.so` files into the NEW cluster (concrete privilege-escalation primitive). Combined with old-catalog trust (`/tmp/evil.so` reference) = arbitrary code execution against just-built new cluster's backend.

**Suggested patch shape:** Whitelist `shared_preload_libraries` family. Reject `/tmp/`, `..`, unsigned libraries. Refuse to LOAD any library not in `pg_extension` at OLD cluster time.

---

## CB10 — 🚨 pg_rewind zero `O_NOFOLLOW`

**Status:** Confirmed. A6 critical finding.

All 6 file_ops.c open/truncate/remove/symlink call sites dereference symlinks. Combined with `create_target_symlink` accepting server-supplied `source_link_target` unchecked + `recurse_dir` following symlinks in pg_tblspc/pg_wal = real escape-the-data-dir primitive across repeated rewinds.

**Suggested patch shape:** Add `O_NOFOLLOW` to all 6 call sites. Validate `source_link_target` against absolute paths + canonical form.

---

## Cross-corpus patterns — the meta-findings

### P1 — "Load arbitrary code from untrusted name" cluster (5 primitives)

Sweeps: A3 pg_dump archive `te->defn` + A6 `pg_upgrade::check_loadable_libraries` + A6 pg_rewind file ops + A7 pg_upgrade_support (gated by `IsBinaryUpgrade`) + A8 output_plugin `LoadOutputPlugin` (5th canonical).

**Pattern:** A NAME (string) supplied by an attacker controls which native code gets loaded. No allowlist, no signing, no validation.

**Phase D meta-pitch:** A shared `validate_loadable_module_name(const char *name, LoadValidationContext *ctx)` helper rejecting `/`, `..`, `/tmp/`, world-writable, AND whitelisting against `pg_extension`. Adoption across all 5 primitives closes the cluster.

### P2 — NAME-vs-OID resolution race (8+ sites)

Sweeps: A3 (pg_dump OID resolution) + A6 (pg_upgrade catalog trust) + A7 (regproc.h NAME→OID) + A8 (subscriber `nspname.relname`) + A9 (plpgsql `%TYPE` baked at compile) + A10 (plpython `parseTypeString`) + A11 (postgres_fdw shippable functions, dblink) + A12 (sepgsql proc.c:279 typo) + A15 (`guc_hooks.h check_*` PGC_S_TEST-forgiving) + A17 (deparse_utility CollectedCommand).

**Pattern:** Code resolves a name to an OID at time T, then uses the OID at time T+N without verifying the name still resolves the same way. Concurrent DDL can swap which object the name binds to.

**Phase D meta-pitch:** Document the family explicitly + add `name_to_oid_with_lock(name, lockmode, time_t expires)` chokepoint. Audit known sites for missing lock acquisition.

### P3 — Secret-scrub gaps (`explicit_bzero`) — 10+ sites

Already covered by MP1 (SecretBuf hosting site). Cluster spans A2 + A4 + A5 + A6 + A8 + A11.

### P4 — Text-to-SPI injection sinks — 5-sweep cluster

Sweeps: A9 plpgsql `exec_stmt_dynexecute` + A10 plperl `spi_exec_query` + A10 plpython `plpy.execute(text)` + A10 pltcl `spi_exec` + A13 tablefunc `connectby_text` + A15 spi.h API host.

**Phase D meta-pitch:** Each PL's text-to-SPI entry should require an explicit `caller_validated=true` flag; default rejects raw text containing single-quote/backslash/semicolon outside literal contexts. Document at `spi.h` API layer.

### P5 — GiST signature-collision attacks on attacker data — 5 modules

Sweeps: A11 pgcrypto + A13 hstore (CRC32) + A13 ltree (CRC32) + A13 intarray (mod-hash) + A14 pg_trgm (mod-hash) + A14 bloom (Park-Miller LCG). 5-module cluster + the in-tree generic `bloomfilter.h` (A15 anchor).

**Phase D meta-pitch:** Audit each signature hash for per-process keying (SP8 generalizes). Document the cluster as a single advisory; provide a `gist_audit` extension that flags suspicious collision rates at runtime.

### P6 — Monitoring-as-extraction (8+ sites)

Already covered by MP7. Cluster: A7 + A11 + A12 + A14 + A17 = 5-sweep, 8+ site cluster.

### P7 — X-macro coordination — 4 sites

Sweeps: A15 `lwlocklist.h` + A17 `rmgrlist.h` + A17 `cmdtaglist.h` + A17 `parser/kwlist.h`. 4-site INCLUDE-trick cluster.

**Phase D meta-pitch:** SP5 (lwlocklist CI lint) is the template; extend to rmgrlist + cmdtaglist + kwlist. Document the X-macro idiom in a new `knowledge/idioms/x-macro-coordination.md`.

### P8 — Float NaN divergence — 4 sites

Sweeps: A13 btree_gist (float4/float8 EXCLUDE-USING-gist permits duplicate NaN) + A14 cube + A14 seg + A15 `float.h` header anchor + A15 `geo_decls.h` (non-transitive EPSILON FPeq).

**Phase D meta-pitch:** Document the NaN-handling contract in `float.h`; add `Assert`-time check in btree_gist + cube + seg comparator paths.

### P9 — A11 cleartext-password 3-header cluster

Already covered by MP4. Cluster: queryjumble.h + cmdtaglist.h + deparse_utility.h.

---

## Triage matrix

| Pitch | Severity | Effort | Sites | Closes pattern |
|---|---|---|---|---|
| **MP1** SecretBuf | High | 1 week | 10+ | P3 |
| **MP2** StringInfo quoting | High | 3 days | 5+ | A7+A13+A14 |
| **MP3** pgcrypto modernization | Critical | 3-4 weeks | 9 | (own series) |
| **MP4** PASSWORD redaction chokepoint | High | 1 week | 4 | P9 |
| **MP5** Routine version+magic+selfcheck | High | 3 weeks | 5 | P1 |
| **MP6** MCV-leak chokepoint | High | 2 weeks | 3 | CVE-2017-7484 class |
| **MP7** Monitoring-as-extraction gate | High | 3 weeks | 11+ | P6 |
| **MP8** Hardened readfuncs.h | Medium | 2 weeks | 7+ | (latent) |
| **MP9** Toast cross-relation check | High | 3-5 days | 3 | A12 anchor |
| **MP10** RLS leakproof runtime check | Medium | 3 weeks | 2 | CVE class |
| **SP1** SCRAM iter cap GUC | Low | 1 day | 1 | A16 |
| **SP2** pg_str* MaxAllocSize cap | Medium | 1 day | 4 | A7 echo |
| **SP3** pg_get_viewdef round-trip | Low | 2 days | 1 | A7 |
| **SP4** execParallel doc | Documentation | ½ day | 1 | A15 |
| **SP5** lwlocklist CI lint | Low | 1 day | 1 | P7 |
| **SP6** autoprewarm REVOKE | Critical (CB5) | 1 hour | 1 | CB5 |
| **SP7** tablefunc identifier quoting | Critical (CB2) | 1 day | 1 | CB2 |
| **SP8** hashfn per-process keying | Medium | 1 week | 3 | P5 |
| **SP9** nodeCustom attestation | Medium | 2-3 weeks | 1 | supply-chain |
| **SP10** PS title password redact | Medium | 2 days | 1 | A15 |
| **CB1** pgcrypto decompression bomb | Critical | (in MP3) | 1 | A11 |
| **CB2** tablefunc SQL injection | Critical | (in SP7) | 1 | A13 |
| **CB3** sepgsql AVC cache widening | Critical | 1 week | 3 (uavc + parallel + proc.c:279) | A12 |
| **CB4** pg_walinspect RLS bypass | Critical | (in MP7) | 1 | A14 |
| **CB5** pg_prewarm PUBLIC | Critical | (in SP6) | 1 | A14 |
| **CB6** pg_surgery freeze resurrects | Critical | 1 week | 1 | A14 |
| **CB7** ltree parse_lquery amplification | Critical | 3 days | 1 | A13 |
| **CB8** hstore forged version bit | Critical | 1 week | 1 | A13 |
| **CB9** pg_upgrade RCE | Critical | (in MP5) | 1 | A6 |
| **CB10** pg_rewind no O_NOFOLLOW | Critical | 1-2 weeks | 6 | A6 |

## Submission strategy

**Quick wins (1-day patches, file immediately):**
- SP6 autoprewarm REVOKE (1 hour)
- SP1 SCRAM iter cap (1 day)
- SP2 pg_str* MaxAllocSize cap (1 day)
- SP3 pg_get_viewdef round-trip (2 days)
- SP5 lwlocklist CI lint (1 day)
- SP7 tablefunc identifier quoting (1 day)
- SP10 PS title redact (2 days)
- CB7 ltree amplification cap (3 days)

These are all small, focused, hackers-list-friendly patches. Could ship 8 CF entries in ~2 weeks.

**Mid-term series (1-month CF entries):**
- MP1 SecretBuf (1 week)
- MP2 StringInfo quoting helpers (3 days)
- MP4 PASSWORD redaction chokepoint (1 week)
- MP9 Toast cross-relation check (3-5 days)
- CB6 pg_surgery hardening (1 week)
- CB8 hstore forgery defense (1 week)
- CB10 pg_rewind O_NOFOLLOW (1-2 weeks)

**Long-term series (2-3 month CF entries with design memos):**
- MP3 pgcrypto modernization (3-4 weeks)
- MP5 Routine version+magic+selfcheck (3 weeks)
- MP6 MCV-leak chokepoint (2 weeks)
- MP7 Monitoring-as-extraction gate (3 weeks)
- MP8 Hardened readfuncs (2 weeks)
- MP10 RLS leakproof runtime check (3 weeks)
- SP8 hashfn per-process keying (1 week)
- SP9 nodeCustom attestation (2-3 weeks)
- CB3 sepgsql cluster (1 week)
- CB9 pg_upgrade RCE (in MP5)

## Next steps

1. **Review this doc with maintainer** (Matej) for prioritization adjustment.
2. **Pick 2-3 quick wins** to file as CF entries first — establishes credibility on hackers-list.
3. **Build a pg-implement plan** for the chosen mid-term pitch using the three-phase planner suite (`pg-feature-plan` → `pg-implement`).
4. **Cross-reference with `pgsql-hackers` ML** — verify no concurrent in-flight work covers the chosen pitches.
5. **Update this doc** as pitches land or get superseded.

## See also

- `progress/STATE.md` — Phase A position + narrative chain
- `knowledge/issues/*.md` — 38+ subsystem registers with the source `[ISSUE-*]` entries
- `knowledge/files/*` — per-file docs with file:line cites
- `progress/anchor-refresh-2026-06-10.md` — source pin drift inventory
- `pg-claude-plan.md` (parent dir) — master design with 4-phase arc

## Acknowledgments

This roadmap is the synthesis of 17 foreground sweeps + 1 source anchor refresh + ~30 nightly cloud runs over 8 days (2026-06-02 → 2026-06-10). The high-value Phase D candidates emerged organically as cross-corpus patterns; this doc is the first attempt at consolidating them into actionable patch series.

Source pin at consolidation: `e18b0cb7344` (2026-06-10).
