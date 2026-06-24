# plsh — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `petere/plsh` @ branch `master`. All `file:line` cites below point into
> that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-23 (see Sources footer).

PL/sh is a procedural-language handler that lets you write a stored function's
body in "a shell of your choice" — the body's first line is a `#!`-style
shebang and the rest is a shell script (`README.md:4-21`) `[from-README]`. The
control comment is just `'PL/sh procedural language'` (`plsh.control:1`)
`[verified-by-code]`. **Headline divergence:** unlike every other PL handler in
this corpus — plv8 (embeds V8), pljava (embeds a JVM), PL/pgSQL (an in-backend
interpreter) — plsh embeds *no interpreter at all*. The call handler writes the
function body to a temp file, `fork()`s, and `execv()`s an external shell as a
child process of the backend (`plsh.c:600-635`) `[verified-by-code]`. A PG
backend shelling out to a forked child is the un-Postgres move the whole design
turns on.

## Domain & purpose

plsh answers: *how do you call out to shell utilities, system commands, or
`psql` from inside a SQL function without writing C?* The canonical example
returns the concatenation of two text args by `echo "$1$2"` under `/bin/sh`
(`README.md:7-10`) `[from-README]`. The contract is deliberately Unix-shaped:
arguments arrive as `$1`, `$2`, …; the function's return value is whatever the
script prints to **stdout** (one trailing newline stripped); empty stdout means
SQL NULL; anything on **stderr** aborts the function as an error; a non-zero
exit status also raises an error (`README.md:12-21`, `plsh.c:668-724`)
`[verified-by-code]`. It cannot touch the database through SPI; instead it sets
libpq environment variables so the script can re-enter via `psql`
(`README.md:35-49`, `plsh.c:348-395`) `[from-README]` `[verified-by-code]`.

## How it hooks into PG

plsh implements the PL call-handler protocol — the same `pg_language` /
`CREATE LANGUAGE` machinery PL/pgSQL uses — but its "language runtime" is the OS.

- **Three C entry points**, all `PG_FUNCTION_INFO_V1`:
  - `plsh_handler(PG_FUNCTION_ARGS)` — the call handler, returns
    `language_handler`; it just delegates to
    `handler_internal(fcinfo->flinfo->fn_oid, fcinfo, true)`
    (`plsh.c:737-743`) `[verified-by-code]`.
  - `plsh_validator(oid)` — runs `handler_internal(..., false)`, which parses
    the shebang but stops before executing ("validation stops here",
    `plsh.c:453-458`); it first gates on `CheckFunctionValidatorAccess`
    (`plsh.c:750-758`) `[verified-by-code]`.
  - `plsh_inline_handler(internal)` — the `DO`-block path (`plsh.c:766-784`)
    `[verified-by-code]`, compiled only when
    `CATALOG_VERSION_NO >= 200909221` (`plsh.c:762`) `[verified-by-code]`.
- **`pg_language` wiring** lives in the install SQL: `CREATE LANGUAGE plsh
  HANDLER plsh_handler INLINE plsh_inline_handler VALIDATOR plsh_validator`
  (`plsh--1--2.sql:5-8`, `plsh-inline.sql:13-16`) `[verified-by-code]`. The
  no-inline variant for older servers omits the `INLINE` clause
  (`plsh-noinline.sql:9-11`) `[verified-by-code]`.
- **fmgr argument source.** The handler does *not* read `PG_GETARG_*` for the
  body — it pulls the source text out of the catalog itself:
  `SearchSysCache(PROCOID, …)` then `SysCacheGetAttr(…, Anum_pg_proc_prosrc)`
  and `textout` to a cstring (`plsh.c:441-449`) `[verified-by-code]`. Argument
  *values* come from `PG_GETARG_DATUM(i)` / `pg_proc_entry->proargtypes`
  (`plsh.c:520-533`) `[verified-by-code]`.
- **`PG_MODULE_MAGIC`** at `plsh.c:41`; built as `MODULE_big = plsh` via PGXS
  (`Makefile:9,24-25`) `[verified-by-code]`.
- **Extension packaging.** `default_version = 2`, `relocatable = true`
  (`plsh.control:2-3`) `[verified-by-code]`; the unpackaged→1 migration
  `ALTER EXTENSION plsh ADD …` adopts a pre-extension install
  (`plsh--unpackaged--1.sql:1-3`) `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. It executes the function body as an external process, not an embedded interpreter

This is the spine. The interpreter PLs (plv8, pljava, PL/pgSQL) all run the
function body *inside the backend address space*. plsh instead:

1. Writes the post-shebang body to a temp file via `mkstemp`
   (`plsh.c:231-275`, called at `plsh.c:460`) `[verified-by-code]`.
2. Builds an `argv` whose `argv[0]` is the interpreter path parsed from the
   shebang and whose last positional element is the temp-file path
   (`plsh.c:451,460-461`) `[verified-by-code]`.
3. `pipe()`s stdout and stderr, `fork()`s, and in the child `dup2`s the pipe
   write-ends onto fds 1/2 and `execv(arguments[0], arguments)`
   (`plsh.c:583-635`) `[verified-by-code]`.

A core PG backend essentially never forks a child to run user code — the
per-connection fork model is the postmaster's job, and backends are expected to
stay single-process. plsh hands a backend's child a `/bin/sh` (or perl, python,
awk — whatever the shebang names). The README states the obvious corollary:
"this language should not be declared as `TRUSTED`" (`README.md:25-26`)
`[from-README]`; nothing sandboxes the child, so it inherits the backend's OS
privileges. That is *why* it must be untrusted, and why only a superuser can
create functions in it (core's untrusted-language rule, enforced by
`pg_language.lanpltrusted`) `[inferred]`.

### 2. The shebang is parsed by hand, not by the kernel or a lexer

`parse_shell_and_arguments` skips one leading blank line, demands the body start
with `#!/` or `#! /` else `ereport(ERROR, ERRCODE_SYNTAX_ERROR …)`
(`plsh.c:161-172`) `[verified-by-code]`, then slices the interpreter line at the
first `/` through end-of-line and `split_string`s it on spaces into argv
(`plsh.c:174-188`, `split_string` at `plsh.c:123-140`) `[verified-by-code]`.
So plsh re-implements the kernel's `#!` handling in userspace — it explicitly
`execv`s the parsed interpreter rather than `execv`ing the temp file and letting
the kernel honor the shebang. `split_string` caps at `SPLIT_MAX` (64) tokens
(`plsh.c:116,128`) `[verified-by-code]`.

### 3. Argument and return marshalling goes through fmgr I/O functions, but the wire format is text-over-pipes

There is no value protocol — every argument is rendered to a C string and every
result is parsed from one:

- **In:** `type_to_cstring` does `SearchSysCache(TYPEOID,…)`, reads
  `typoutput`, and `OidFunctionCall3`s it (`plsh.c:92-112`); each non-NULL arg
  becomes `arguments[argc++]` (`plsh.c:520-533`) `[verified-by-code]`. A NULL
  argument is passed as the empty string `""` (`plsh.c:524-525`)
  `[verified-by-code]` — so plsh **cannot distinguish NULL from empty string on
  the way in**, a lossy mapping core's strict-function machinery would normally
  guard.
- **Out:** stdout is slurped, one trailing `\n` stripped, and fed to
  `cstring_to_type`, which reads `typinput` and `OidFunctionCall3`s it against
  `prorettype` (`plsh.c:65-85`, `plsh.c:558-559`, `plsh.c:668-673`)
  `[verified-by-code]`. Empty stdout ⇒ `return_null` ⇒ `PG_RETURN_NULL`
  (`plsh.c:669-670,726-727,560-561`) `[verified-by-code]`.

So fmgr's `typinput`/`typoutput` is the type-coercion bridge (the one idiom plsh
shares with everyone), but the transport is a Unix pipe carrying text, not
Datums.

### 4. Errors are an exit code / stderr convention, not ereport-from-the-runtime

An embedded PL propagates its runtime's exceptions into `ereport`. plsh has no
runtime to ask, so it reverse-engineers failure from POSIX `wait` status:

- Any bytes on the child's **stderr** ⇒ `ereport(ERROR, errmsg("%s: %s",
  proname, stderr_buffer))` (`plsh.c:699-708`) `[verified-by-code]`. Note this
  fires *even on exit status 0* — stderr output alone aborts the function.
- `WIFEXITED` with non-zero status ⇒ `"script exited with status %d"`
  (`plsh.c:712-718`); `WIFSIGNALED` ⇒ `"script was terminated by signal %d"`
  (`plsh.c:719-724`) `[verified-by-code]`.
- The `fork`/`pipe`/`exec`/`wait`/temp-file failures all route through
  `errcode_for_file_access()` + `%m` (`plsh.c:246-248`, `586-588`, `609-611`,
  `632-634`, `414-416`) `[verified-by-code]` — the one place plsh's error
  handling looks like idiomatic backend C.

### 5. The backend blocks in `wait()` while a child runs arbitrary code

The parent reads stdout then stderr to EOF (`read_from_file`, `plsh.c:196-227`)
and then `wait_and_cleanup` loops on `wait(&child_status)` until it reaps the
right pid, removing the temp file (`plsh.c:401-419`, called repeatedly on every
exit path) `[verified-by-code]`. For the duration the backend is parked in a
blocking syscall running no PG code — no `CHECK_FOR_INTERRUPTS`, no statement
timeout enforcement on the child `[inferred]`. A hung script hangs the backend.

### 6. Trigger / event-trigger data is delivered as environment variables, not as a TriggerData struct the body can read

Because the body is an opaque external process, plsh flattens the trigger
context into `setenv` calls made *in the child after fork* (`plsh.c:624-629`):

- Row/statement triggers: `PLSH_TG_NAME`, `PLSH_TG_WHEN`
  (BEFORE/INSTEAD OF/AFTER), `PLSH_TG_LEVEL` (ROW/STATEMENT), `PLSH_TG_OP`
  (DELETE/INSERT/UPDATE/TRUNCATE), `PLSH_TG_TABLE_NAME`, `PLSH_TG_TABLE_SCHEMA`
  (`plsh.c:281-323`, `README.md:54-62`) `[verified-by-code]`. For ROW triggers
  the OLD/NEW tuple columns are appended to argv as cstrings via `heap_getattr`
  + `type_to_cstring` (`plsh.c:480-497`) `[verified-by-code]`.
- Event triggers: `PLSH_TG_EVENT`, `PLSH_TG_TAG` (with a `GetCommandTagName`
  shim for PG ≥ 13 vs the raw `tag` string before) (`plsh.c:329-342`,
  `README.md:67-71`) `[verified-by-code]`.
- **Triggers can't modify rows.** The handler sets up the return tuple *before*
  running the script (the comment: "since we can't alter the tuple anyway")
  and returns the unmodified trigtuple/newtuple (`plsh.c:499-510,548-551`),
  matching the README's "they can't change the rows" (`README.md:24-25`)
  `[verified-by-code]` `[from-README]`. A BEFORE-trigger row rewrite — routine
  in PL/pgSQL — is structurally impossible here.

### 7. Database access is "shell out to psql", wired via injected libpq env vars

With no SPI, the database back-channel is `psql` re-connecting to the same
cluster. `set_libpq_envvars` (run in the child, `plsh.c:629`) sets
`PGAPPNAME=plsh`, unsets `PGCLIENTENCODING`, sets `PGDATABASE` from
`get_database_name(MyDatabaseId)`, derives `PGHOST` from the first
`unix_socket_directories` entry (or `localhost`), sets `PGPORT` from
`PostPortNumber`, and prepends the server's own `bin` dir (`my_exec_path`) to
`PATH` — but only if `PATH` is already set (`plsh.c:348-395`, `README.md:49`)
`[verified-by-code]`. This is a deliberate inversion: rather than embed a client
library, plsh leans on the *separate* `psql` binary the script can already see.

## Notable design decisions (with cites)

- **Temp-file race / CVE-2014-0061.** The NEWS file marks version 1.20140221 as
  a "Security release (CVE-2014-0061)" (`NEWS` line for that version)
  `[from-comment]`. The current code creates the temp file with `mkstemp` into
  `$TMPDIR/plsh.XXXXXX` or `/tmp/plsh-XXXXXX` (`plsh.c:239-244`)
  `[verified-by-code]` — `mkstemp` (vs a predictable name) is the fix shape for
  a `/tmp` symlink/predictable-name attack `[inferred]`.
- **Fixed-size, non-reentrant buffers.** `tempfile` is a single reused
  `static char[MAXPGPATH]` (`plsh.c:235`) and argv is
  `char *arguments[FUNC_MAX_ARGS + 2]` (`plsh.c:435,773`) NULL-terminated
  (`plsh.c:536-537`) — fine only because a backend runs one plsh function to
  completion at a time `[verified-by-code]` `[inferred]`.
- **Memory comes from palloc**, not malloc: `read_from_file` `palloc`/`repalloc`s
  its growing buffer (`plsh.c:199-227`), arg conversion palloc's via fmgr
  `[verified-by-code]`. The child inherits these post-fork; the parent's
  buffers die with the per-call memory context `[inferred]`.
- **Validator honors `check_function_bodies`** indirectly via
  `CheckFunctionValidatorAccess`, and only ever parses the shebang — it never
  forks (`plsh.c:453-458,750-758`) `[verified-by-code]`, so `CREATE FUNCTION`
  validation is cheap and side-effect-free.
- **Broad version portability via `#if PG_VERSION_NUM` / `CATALOG_VERSION_NO`**
  shims: event triggers stubbed out pre-9.3 (`plsh.c:27-50`), `TupleDescAttr`
  back-compat macro (`plsh.c:53-55`), inline handler gated on catversion
  (`plsh.c:762`). NEWS claims support for PG 8.4 through 15 (`NEWS:3`)
  `[from-comment]`. The Makefile computes `inline_supported` /
  `event_trigger_supported` feature flags from `pg_config --version`
  (`Makefile:3-6,20`) `[verified-by-code]`.
- **`-Wmissing-prototypes` is filtered out of CFLAGS** (`Makefile:27`)
  `[verified-by-code]` — because several handler-internal functions
  (`parse_shell_and_arguments`, `set_libpq_envvars`) are non-static without
  headers (`plsh.c:147,348`) `[verified-by-code]`.

## Links into corpus

- [[fmgr]] / [[spi]] — plsh uses fmgr `typinput`/`typoutput` for arg/return
  coercion (`plsh.c:65-112`) but pointedly has **no SPI**; the contrast with
  the SPI-based PLs is the point.
- [[error-handling]] — `errcode_for_file_access()` + `%m` for the
  fork/pipe/exec/wait failures; the stderr/exit-status→`ereport(ERROR)`
  convention is a non-standard error source.
- [[memory-contexts]] — palloc/repalloc growing buffers across a fork boundary.
- [[catalog-conventions]] — reads `prosrc`/`proargtypes`/`prorettype` out of
  `pg_proc`; `pg_language` HANDLER/INLINE/VALIDATOR registration.
- [[extension-development]] — `.control` (`relocatable`, `default_version`),
  `--unpackaged--1` adopt script, PGXS `MODULE_big`.
- [[event-trigger-firing]] / [[trigger-firing-order]] — plsh exposes trigger and
  event-trigger context, but flattened to env vars and unable to rewrite rows.
- [[process-utility-hook-chain]] — `DO … LANGUAGE plsh` rides the inline-handler
  path of utility processing.
- Sibling PL ideologies — the load-bearing contrast set: [[plv8]] (embeds V8),
  [[pljava]] (embeds a JVM), [[plpgsql_check]] (a static-analysis parasite on
  PL/pgSQL). plsh is the only one that embeds *no* runtime and instead
  `fork`/`exec`s an external process.
- Scenario refs: `scenarios/integrate-with-plpgsql.md` (the in-tree PL it most
  differs from); `scenarios/add-new-extension.md`.

> Corpus gap: there is no idiom doc for the **PL call-handler protocol** itself
> — the `language_handler`/validator/inline-handler triple, `pg_language`
> registration, and how `prosrc` is the function body. Every PL ideology in the
> corpus (plv8, pljava, plsh) re-derives it; worth a dedicated
> `idioms/pl-call-handler-protocol.md`.
> Corpus gap: no idiom doc for **a backend safely forking/exec'ing an external
> process** (pipe setup, `wait` reaping, temp-file `mkstemp` hygiene, the
> blocking-in-`wait` interrupt hole). `pg_background` (bgworker) and `dblink`
> (libpq) are cousins but neither `fork`/`exec`s a raw child the way plsh does.

## Sources

All fetched 2026-06-23.

- Tree listing: `https://api.github.com/repos/petere/plsh/git/trees/master?recursive=1` — 200
- `https://raw.githubusercontent.com/petere/plsh/master/README.md` — 200
- `https://raw.githubusercontent.com/petere/plsh/master/plsh.control` — 200
- `https://raw.githubusercontent.com/petere/plsh/master/plsh.c` — 200 (785 lines)
- `https://raw.githubusercontent.com/petere/plsh/master/plsh--1--2.sql` — 200
- `https://raw.githubusercontent.com/petere/plsh/master/plsh--unpackaged--1.sql` — 200
- `https://raw.githubusercontent.com/petere/plsh/master/plsh-inline.sql` — 200 (the inline-capable `CREATE LANGUAGE` script; the `plsh--1--2.sql` upgrade only adds the inline handler, so the full handler/validator wiring is here)
- `https://raw.githubusercontent.com/petere/plsh/master/plsh-noinline.sql` — 200 (pre-inline fallback)
- `https://raw.githubusercontent.com/petere/plsh/master/Makefile` — 200
- `https://raw.githubusercontent.com/petere/plsh/master/NEWS` — 200 (CVE-2014-0061 + version/PG-support history)

Substitution note: the prompt listed `plsh--1--2.sql` and `plsh--unpackaged--1.sql`
(both fetched, 200); the canonical full `CREATE LANGUAGE` wiring lives in
`plsh-inline.sql` / `plsh-noinline.sql` (templates the Makefile copies into
`plsh.sql` / `plsh--2.sql`, `Makefile:30-36`), so those were fetched in addition.

Skimmed-but-not-fetched: `test/sql/*.sql` and `test/expected/*.out` (function,
trigger, event_trigger, inline, crlf, psql) — behavior cross-checked against the
README contract, not directly cited; `COPYING`, `.cirrus.yml`, `.gitattributes`,
`.gitignore` (build/CI/licensing, not behavioral).
