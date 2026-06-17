# pg_tle — extensions as in-database SQL objects: a fork of core's CREATE EXTENSION machinery that reads control/script "files" out of the catalog instead of the filesystem

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `aws/pg_tle` @ branch `main`. All `file:line` cites point into THAT
> repo (not `source/`). Cites verified against files fetched 2026-06-16 (see
> Sources footer). pg_tle is the substrate under PgQue's
> `pgtle.install_extension` (already covered in `[[knowledge/ideologies/pgque.md]]`).
> Read alongside `[[knowledge/idioms/process-utility-hook-chain.md]]`,
> `[[knowledge/idioms/background-worker-startup.md]]`,
> `.claude/skills/extension-development/SKILL.md`.

## Domain & purpose

`pg_tle` ("Trusted Language Extensions") lets developers "create and install
extensions on restricted filesystems and work with PostgreSQL internals
through a SQL API" (`README.md:3`) `[from-README]`. The problem it solves:
"Installing a new PostgreSQL extension involves having access to the underlying
filesystem. Many managed service providers or systems running databases in
containers disallow users from accessing the filesystem" (`README.md:17`)
`[from-README]`. Instead of shipping a `.control` + `--version.sql` pair into
`SHAREDIR/extension`, a TLE is *installed as catalog objects*: the control file
and each install/upgrade script become the bodies of SQL functions in a
private `pgtle` schema, and a `ProcessUtility_hook` reroutes `CREATE
EXTENSION` / `ALTER EXTENSION` to read those functions instead of files
(`docs/30_architecture.md:21-36`) `[from-README]`. It is the corpus's sharpest
example of an extension that **reimplements a core backend subsystem
(`commands/extension.c`) against a different storage substrate** — the catalog
rather than `$libdir`/`SHAREDIR` — while keeping the user-facing SQL grammar
unchanged. The reason to document it: it inverts two core assumptions at once
(extensions come from files; backend hooks are C in a `.so`), and it does so by
literally copying core's command code and editing the file-access seams.

## How it hooks into PG

`pg_tle` must be in `shared_preload_libraries`: `pg_tle_init` `ereport(ERROR)`s
if `!process_shared_preload_libraries_in_progress`
(`src/tleextension.c:4119-4123`) `[verified-by-code]`. Its `_PG_init`
fans out to three subsystem initializers, each of which chains a different core
hook:

- **`pg_tle_init`** saves the prior `ProcessUtility_hook` into `prev_hook` and
  installs `PU_hook` (`src/tleextension.c:4124-4128`) `[verified-by-code]`. This
  is the extension-management interceptor.
- **`passcheck_init`** chains `check_password_hook` →
  `passcheck_check_password_hook` (`src/passcheck.c:124-125`), plus
  `shmem_request_hook`/`shmem_startup_hook` for a shared-memory slot, and
  defines the `pgtle.enable_password_check` enum GUC (`src/passcheck.c:142-150`)
  `[verified-by-code]`.
- **`clientauth_init`** chains `ClientAuthentication_hook` → `clientauth_hook`,
  registers N background workers (`clientauth_launcher_main`) via
  `RegisterBackgroundWorker`, and defines the `pgtle.enable_clientauth` GUC
  (`src/clientauth.c:252-261, 324-344`) `[verified-by-code]`.

Constants pin the private namespace and the magic markers:
`PG_TLE_NSPNAME = "pgtle"`, `PG_TLE_EXTNAME = "pg_tle"`,
`PG_TLE_ADMIN = "pgtle_admin"`, and two dollar-quote sentinels
`PG_TLE_OUTER_STR = "$_pgtle_o_$"` / `PG_TLE_INNER_STR = "$_pgtle_i_$"`
(`include/tleextension.h:21-26`) `[verified-by-code]`.

`pgtle.install_extension(name, version, description, ext, requires, schema)`
is the entry point that stores a TLE. It builds an `ExtensionControlFile`
struct in C, serializes it to a control-file string, then issues two `CREATE
FUNCTION` statements via SPI: `pgtle.<name>.control()` returning the control
text, and `pgtle.<name>--<version>.sql()` returning the install script
(`src/tleextension.c:4647-4697`) `[verified-by-code]`. Each function gets a
`recordDependencyOn` the `pg_tle` extension OID so dropping `pg_tle` cascades to
the TLE artifacts (`src/tleextension.c:4754-4767`) `[verified-by-code]`. So an
extension's "files" are literally rows of `pg_proc` whose `prosrc` is the
control/script body. The `ProcessUtility_hook` (`PU_hook`) only fires its TLE
path when (a) the `pg_tle` extension is installed in the database
(`get_extension_oid`, `src/tleextension.c:4172-4185`) and (b) no *file-based*
extension of that name exists — `filestat()` of the real
`SHAREDIR/extension/<name>.control` is checked first and wins
(`src/tleextension.c:4199-4223`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. It forks `commands/extension.c` and swaps file reads for catalog reads

`tleextension.h` is candid: "Extension management commands (create/drop
extension), sans files. Copied from src/include/commands/extension.h and
modified to suit" (`include/tleextension.h:3-7`) `[from-comment]`. The whole of
core's `CreateExtension` / `ApplyExtensionUpdates` / version-path graph logic is
re-vendored as `tleCreateExtension` / `tleExecAlterExtensionStmt` /
`ApplyExtensionUpdates` (`include/tleextension.h:40-51`,
`src/tleextension.c:201-206`) `[verified-by-code]`. The divergence is
surgically localized to the file-access seams. The filename helpers branch on a
`tleext` flag: in file mode they `snprintf` a `SHAREDIR/extension/...` path; in
TLE mode they return a bare `"<name>.control"` /
`"<name>--<version>.sql"` *function name* string
(`get_extension_control_filename`, `src/tleextension.c:593-604`;
`get_extension_script_filename`, `src/tleextension.c:667-698`)
`[verified-by-code]`. Where core would `read_whole_file`, the TLE path calls
`exec_scalar_text_sql_func`, which `SELECT pgtle.<funcname>()` over SPI and
returns the scalar text (`src/tleextension.c:321-357`) `[verified-by-code]`.
`read_whole_file` itself survives unchanged for the file path
(`src/tleextension.c:4057-4095`). This is "don't reinvent PostgreSQL
functionality" (`docs/30_architecture.md:13`) taken literally — same code,
different I/O backend.

### 2. Existence is `SearchSysCache`, not `stat()`

Core decides an extension exists by `stat()`-ing its control file. pg_tle's
`funcstat()` instead does `SearchSysCache3(PROCNAMEARGSNSP, ...)` for a
zero-arg function of that name in the `pgtle` schema
(`src/tleextension.c:376-397`) `[verified-by-code]`, paired with the still-real
`filestat()` (`src/tleextension.c:362-371`). The `PU_hook` runs `filestat`
first and only falls to `funcstat` if no real file exists — pg_tle deliberately
refuses to let a TLE *shadow* a file-based extension of the same name
(`src/tleextension.c:4194-4223`) `[verified-by-code]`.

### 3. C-level backend hooks driven by user-supplied SQL — inverting "hooks are C in a .so"

Core's `check_password_hook` and `ClientAuthentication_hook` are function
pointers a C module sets in `_PG_init`. pg_tle keeps the C hook but makes its
*body* a dispatch into user SQL: `feature_proc("passcheck")` queries
`pgtle.feature_info` for `(schema_name, proname)` rows registered against the
feature, assembles qualified names, and the hook then `SPI_execute_with_args`
each as `SELECT <fn>($1::text, $2::text, $3::pgtle.password_types, ...)`
(`src/feature.c:39-128`, `src/passcheck.c:536-571`) `[verified-by-code]`. So a
backend C hook's behavior is now a table of SQL functions an unprivileged-ish
`pgtle_admin` registered at runtime — "Users can define their own SQL-based
hook functions" (`docs/30_architecture.md:42-46`) `[from-README]`. `clientauth`
goes further: because `ClientAuthentication_hook` fires before a normal backend
exists, it ships the user SQL out to dedicated background workers
(`clientauth_launcher_main`, registered N-wide) that hold a database connection
and run the functions on the client backend's behalf via shared memory
(`src/clientauth.c:325-344`) `[verified-by-code]`. The docs warn these run with
elevated authority: "**clientauth functions are executed as superuser!**"
(`docs/04_hooks.md:204`) and, when `pgtle.passcheck_db_name` is set,
"**passcheck functions are executed as superuser!**" (`docs/04_hooks.md:74`)
`[from-README]`.

### 4. A trust boundary built from catalog privileges, not OS privileges

Core gates extension installation on `superuser` (or the `trusted` flag) and on
filesystem access. pg_tle relocates the boundary into the catalog: only the
`pgtle_admin` role may register hook functions or modify `pgtle.feature_info`
(`docs/04_hooks.md:11,19`; `docs/20_security.md:15`) `[from-README]`, and the
`check_password_hook` itself is only enabled by a real superuser through
`pgtle.enable_password_check` (`docs/20_security.md:25`) `[from-README]`.
Installed TLEs are forced non-superuser and non-trusted: `install_extension`
hard-sets `control->superuser = false`, `control->trusted = false`,
`control->relocatable = false` regardless of input
(`src/tleextension.c:4648-4652`) `[verified-by-code]`. The security model is
explicit that `pgtle_admin` "is still not a PostgreSQL superuser and should not
perform superuser-specific functionality" (`docs/20_security.md:15`)
`[from-README]` — yet the password/clientauth hooks are exactly where that
line is thinnest, hence the dictionary of warnings.

### 5. Catalog-as-code-store demands hand-rolled injection defenses

Because the install script is concatenated into a `CREATE FUNCTION ... AS
$_pgtle_o_$ SELECT $_pgtle_i_$<sql>$_pgtle_i_$ $_pgtle_o_$` body
(`src/tleextension.c:4684-4697`), pg_tle must defend the dollar-quote sentinels
by hand. `validate_tle_sql` rejects any script containing `PG_TLE_OUTER_STR` or
`PG_TLE_INNER_STR` (`src/tleextension.c:5217-5224`), and a duplicate-function
error is rewritten to "extension already installed"
(`src/tleextension.c:4722-4735`) `[verified-by-code]`. The feature dispatcher
separately scans every resolved `schema.proname` for a `;` to stop SPI from
running multiple statements (`check_valid_name`, `src/feature.c:160-184`)
`[verified-by-code]`. These are defenses a file-based extension never needs —
they exist only because the "file" is now untrusted catalog text assembled into
a SQL string.

## Notable design decisions (cited)

- **Reserved-namespace enforcement in the utility hook.** `PU_hook` intercepts
  `CREATE FUNCTION` into the `pgtle` schema and errors `"%s schema reserved for
  pg_tle functions"` unless the call is flagged as a pg_tle artifact
  (`tleart`) or is `pg_tle` itself bootstrapping
  (`src/tleextension.c:4273-4321`) `[verified-by-code]`. The control/script
  functions are not meant to be writable directly.
- **`PG_TLE_MAGIC` as a provenance tag.** When the hook reroutes to
  `tleCreateExtension`, it stamps a dummy `ParseState->p_sourcetext =
  PG_TLE_MAGIC` (`src/tleextension.c:4216-4219`) `[verified-by-code]`, a
  marker the copied extension code keys on to know it is running a TLE.
- **Transaction-scoped flag reset.** `pg_tle_xact_callback` clears the
  `tleart`/`tleext` flags (`UNSET_TLEART`/`UNSET_TLEEXT`) at every
  transaction end so an aborted install can't leave the hook in TLE mode
  (`src/tleextension.c:4100-4108`) `[verified-by-code]`.
- **Three-state feature GUC.** `enable_feature_mode` is `on`/`off`/`require`:
  `require` errors if the extension or a `feature_info` entry is missing,
  `on` silently no-ops in that case (`include/feature.h:22-55`,
  `src/passcheck.c:503-523`) `[verified-by-code]` — letting an operator demand
  the check cluster-wide or treat it as best-effort.
- **Password-leak hardening in error paths.** Both `feature_proc` and the
  passcheck hook wrap SPI in `PG_TRY`/`PG_CATCH` that call `errhidestmt(true)`
  / `errhidecontext(true)` / `internalerrquery(NULL)` so a thrown error can't
  echo the password into the log (`src/feature.c:112-124`,
  `src/passcheck.c:200-213`) `[verified-by-code]`.
- **`clientauth` runs in a configurable side database** via
  `pgtle.clientauth_db_name` (default `postgres`, `PGC_POSTMASTER`,
  `GUC_SUPERUSER_ONLY`) with a bounded worker pool
  (`pgtle.clientauth_num_parallel_workers`, capped by `MaxConnections`)
  (`src/clientauth.c:263-283`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/pgque.md]]` — PgQue's `pgtle.install_extension` is
  exactly the API in §How-it-hooks; pg_tle is the substrate that lets PgQue
  ship as a catalog-resident extension on managed PG.
- `[[knowledge/idioms/process-utility-hook-chain.md]]` — pg_tle's whole
  rerouting trick is one `ProcessUtility_hook` that conditionally intercepts
  `T_CreateExtensionStmt`/`T_AlterExtensionStmt` and else chains the prior hook.
- `[[knowledge/idioms/background-worker-startup.md]]` — `clientauth` registers
  N bgworkers (`clientauth_launcher_main`) to run user SQL during
  authentication, when no normal backend exists yet.
- `[[knowledge/idioms/fmgr.md]]`, `[[knowledge/idioms/spi.md]]` — the
  control/script functions are read back via SPI scalar-select; feature hooks
  dispatch user functions via `SPI_execute_with_args`.
- `[[knowledge/idioms/guc-variables.md]]` — `pgtle.enable_password_check` /
  `pgtle.enable_clientauth` enum GUCs gate the C hooks.
- `.claude/skills/extension-development/SKILL.md` — the file-based model pg_tle
  deliberately mirrors-and-replaces (`.control` + `--version.sql`).
- `.claude/skills/bgworker-and-extensions/SKILL.md` — `RegisterBackgroundWorker`
  + chained-hook-on-`_PG_init` pattern, both used here.
- `.claude/skills/catalog-conventions/SKILL.md` — the TLE store *is* `pg_proc`
  rows plus `recordDependencyOn` the `pg_tle` extension OID.

## Anthropology takeaway

pg_tle is the doc-set's cleanest **"reimplement a core subsystem against a
different storage substrate"** case. Rather than extend `commands/extension.c`,
it *copies* it (`include/tleextension.h:3-7`) and edits only the file-access
seams so an extension's control file and scripts live as `pg_proc.prosrc` text
read back over SPI, with a `ProcessUtility_hook` making the unchanged `CREATE
EXTENSION` grammar route there. That single move buys filesystem-free extension
install on managed PG — and forces pg_tle to re-derive, in SQL space, two things
the filesystem gave core for free: a trust boundary (now the `pgtle_admin` role
+ forced `superuser=false`/`trusted=false`, `src/tleextension.c:4648-4652`) and
input safety (dollar-quote sentinel rejection + `;`-scanning,
`src/tleextension.c:5217-5224`, `src/feature.c:160-184`). The second, larger
inversion is the "feature" framework: C-level `check_password_hook` and
`ClientAuthentication_hook` whose bodies dispatch into user-registered SQL
functions — sometimes executed as superuser (`docs/04_hooks.md:74,204`). For a
`knowledge/issues` note this is the standout: a managed-PG extension that lets a
non-superuser role inject code onto the password-check and authentication paths
is a genuinely novel privilege-surface, and the cascade of "executed as
superuser!" warnings in its own docs is the author-acknowledged sharp edge worth
flagging to anyone auditing a TLE-enabled cluster.

## Sources

Fetched 2026-06-16 (branch `main`), via
`raw.githubusercontent.com/aws/pg_tle/main/<path>`:

- `README.md` @ 2026-06-16 → HTTP 200 (4100 bytes; overview + motivation read).
- `pg_tle.control.in` @ 2026-06-16 → HTTP 200 (180 bytes; the `.control`
  template with `EXTNAME`/`EXTVERSION`/`SCHEMA` substitution tokens — pg_tle
  itself is a normal file-based extension).
- `include/tleextension.h` @ 2026-06-16 → HTTP 200 (2114 bytes; constants,
  the "copied from extension.h, sans files" provenance comment, `tle*` API).
- `src/tleextension.c` @ 2026-06-16 → HTTP 200 (152705 bytes, 5394 lines;
  deep-read of `_init`/`PU_hook`, filename helpers, `exec_scalar_text_sql_func`,
  `install_extension`, `validate_tle_sql`; the version-graph / update-path code
  was skimmed, not audited).
- `include/feature.h` @ 2026-06-16 → HTTP 200 (2477 bytes; `enable_feature_mode`
  enum + `feature_proc`/`check_string_in_guc_list` signatures).
- `src/feature.c` @ 2026-06-16 → HTTP 200 (4698 bytes; full read — the SQL
  dispatch + `check_valid_name` `;`-guard + log-leak hardening).
- `src/passcheck.c` @ 2026-06-16 → HTTP 200 (19052 bytes; `passcheck_init` hook
  chain, `passcheck_run_user_functions` SPI dispatch, shmem startup; the
  bgworker path was read for structure, not line-audited end to end).
- `src/clientauth.c` @ 2026-06-16 → HTTP 200 (29421 bytes; `clientauth_init`
  GUCs + hook + bgworker registration read; launcher/worker IPC skimmed).
- `docs/30_architecture.md` @ 2026-06-16 → HTTP 200 (3850 bytes; design
  principles + `ProcessUtility_hook` CREATE EXTENSION walkthrough).
- `docs/20_security.md` @ 2026-06-16 → HTTP 200 (2302 bytes; `pgtle_admin` trust
  model, global-hook / `check_password_hook` warnings).
- `docs/04_hooks.md` @ 2026-06-16 → HTTP 200 (18084 bytes; `register_feature` /
  `feature_info`, passcheck + clientauth function definitions and the
  "executed as superuser!" warnings).

No paths 404'd; all manifest files fetched HTTP 200. Cites are
`[verified-by-code]` against the fetched `.c`/`.h` files except design-principle
and trust-model claims drawn from `docs/*` and `README.md`, tagged
`[from-README]`; the "copied from extension.h, sans files" provenance is
`[from-comment]`. The copied version-path/update-graph logic in
`tleextension.c` was confirmed present but not line-by-line compared against
core `extension.c`.
