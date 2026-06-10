# orafce — Oracle-compatibility layer that reproduces Oracle's quirks (and bugs) as GUC-selectable policy, with its own shmem message bus

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `orafce/orafce` @ branch `master`. All `file:line` cites point into that
> repo (not `source/`). Cites verified against the files fetched on 2026-06-10
> (see Sources footer). Read alongside `[[knowledge/ideologies/plv8]]` and
> `[[knowledge/ideologies/pg_squeeze]]` (vendored-shmem / behavior-toggle
> neighbors) and `[[knowledge/idioms/error-handling]]`.

## Domain & purpose

orafce is a long-lived Oracle-compatibility extension: it implements Oracle's
built-in functions and `DBMS_*` packages (`DBMS_PIPE`, `DBMS_ALERT`,
`DBMS_ASSERT`, `DBMS_SQL`, `UTL_FILE`), Oracle's date/number/string functions
(`to_char`, `to_date`, `to_number`, `substr`, `nvl`), and Oracle-flavored types
(`varchar2`, `nvarchar2`). The interesting thing anthropologically is *how* it
reaches Oracle compatibility: rather than approximate, it reproduces specific
Oracle semantics — including a documented Oracle **bug** — and exposes the
choice of "behave like Oracle vs behave like Postgres" as runtime GUCs. The
extension has shipped continuously from v3.2 through v4.x (the upgrade-script
chain `orafce--3.2--3.3.sql … orafce--4.13--4.14.sql` is in-tree)
`[verified-by-code]`, making it one of the oldest extensions in the doc-set.

## How it hooks into PG

A `shared_preload`-friendly module (it reserves shmem) but also useful lazily.
From `_PG_init` (`orafce.c:103-189`) `[verified-by-code]`:

- **Reserves shared memory** for the DBMS_PIPE/DBMS_ALERT message area:
  `RequestAddinShmemSpace(SHMEMMSGSZ)`, wired through a `shmem_request_hook` on
  PG ≥ 15 and called directly on older PG (`orafce.c:46-57, 107-116`)
  `[verified-by-code]`.
- **Registers a transaction callback**: `RegisterXactCallback(orafce_xact_cb,
  NULL)` (`orafce.c:186`) `[verified-by-code]` — used to give `DBMS_ALERT`
  Oracle's transactional semantics (signals are buffered and only delivered at
  commit).
- Defines **eight compatibility GUCs** (`orafce.c:118-184`), most of which select
  Oracle-vs-Postgres behavior rather than tune performance (see Divergence 1).

It defines its `varchar2`/`nvarchar2` types and hundreds of SQL functions in the
install script, exposing C entry points via `PG_FUNCTION_INFO_V1` across
`convert.c`, `datefce.c`, `nvarchar2.c`, `alert.c`, etc.

Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]` (shmem reservation),
`.claude/skills/extension-development/SKILL.md`,
`.claude/skills/error-handling/SKILL.md`.

## Where it diverges from core idioms

### 1. Behavior — including a known Oracle bug — is GUC-selectable policy, not fixed semantics

orafce turns "which database's quirks do you want" into configuration:

- `orafce.oracle_compatibility_date_limit` — *"Specify if an error is raised when
  the Oracle to_date() bug is reached"* (`orafce.c:175-182`) `[verified-by-code]`.
  The extension knowingly carries an Oracle `to_date()` edge-case and lets you
  choose whether to error at the boundary, i.e. **bug-for-bug compatibility as an
  opt-in**.
- `orafce.using_substring_zero_width_in_substr` — an enum over
  `{warning_oracle, warning_orafce, oracle, orafce}` controlling whether
  zero-width `substr` follows Oracle or Postgres semantics, with or without a
  warning (`orafce.c:32-38, 156-163`) `[verified-by-code]`.
- `orafce.varchar2_null_safe_concat` — toggles Oracle's "empty string is NULL"
  concat behavior for the `varchar2`/`nvarchar2` types (`orafce.c:138-145`)
  `[verified-by-code]`.
- `orafce.nls_date_format` / `orafce.timezone` — emulate Oracle's `NLS` date
  output and `SYSDATE` timezone (`orafce.c:119-136`) `[verified-by-code]`.
- `orafce.sys_guid_source` — picks which `uuid-ossp` function backs `SYS_GUID()`,
  with a `check` hook that canonicalizes aliases (`check_sys_guid_source`,
  `orafce.c:59-100, 147-154`) `[verified-by-code]`.

Core decides a function's semantics at the call site and treats GUCs as tuning,
not as a behavior switch between two SQL dialects. orafce makes the *dialect*
itself a session variable — the defining divergence. Cross-ref
`[[knowledge/idioms/error-handling]]` (warning-vs-error chosen by GUC).

### 2. Custom Oracle types that reuse core `varchar`/`text` support functions wholesale

`nvarchar2` is a distinct SQL type but its on-disk representation *is* core
`VarChar`/`text`: `nvarchar2in`/`out`/`recv` convert through
`cstring_to_text_with_len` / `TextDatumGetCString`, and the source comments
explicitly say to reuse core for the rest — *"nvarchar2send … just use
varcharsend()"*, *"nvarchar2_transform … just use varchar_transform()"*,
*"nvarchar2typmodin … just use varchartypmodin()"* (`nvarchar2.c:126-202`)
`[from-comment]`. Only the input path adds Oracle's typmod/truncation rules
(multibyte-aware length check, no blank-space truncation on implicit cast,
`nvarchar2_input` + `nvarchar2`, `nvarchar2.c:39-189`) `[verified-by-code]`. So
the divergence is a *thin semantic shim* over a core type's binary layout and
support functions — the type system's pluggability used to re-skin `varchar`
with Oracle truncation behavior rather than to introduce a new storage format.
Cross-ref `[[knowledge/idioms/catalog-conventions]]`,
`[[knowledge/ideologies/uuidv47]]` (another type that delegates I/O to a core
type's functions).

### 3. DBMS_PIPE / DBMS_ALERT is a hand-rolled shared-memory message bus, not LISTEN/NOTIFY

Postgres already has an inter-backend signaling mechanism (LISTEN/NOTIFY).
orafce instead reimplements Oracle's pipe/alert packages on its own shared
memory: `alert.c` includes a custom shared-memory allocator header `shmmc.h` and
a `pipe.h`, declares an `extern ConditionVariable *alert_cv` for waiters, and
takes LWLocks + reads `procarray.h` to coordinate across backends
(`alert.c:1-48`) `[verified-by-code]`. Alerts honor transaction boundaries by
buffering signals in a backend-local `MemoryContext` keyed on the current
`LocalTransactionId` (`local_buf_cxt`, `local_buf_lxid`, `signals` list,
`alert.c:57-59`) and flushing via the `RegisterXactCallback` from `_PG_init`
`[verified-by-code]`. Waiters block on the shared `ConditionVariable` up to a
`MAXWAIT` of 1000 days (`alert.c:73-74`) `[verified-by-code]`. This is a second,
parallel notification subsystem living entirely in extension shmem — divergent
from core's NOTIFY queue, and a maintenance burden (its own allocator, its own
cross-version `MyProc->vxid.lxid` vs `MyProc->lxid` shim at `alert.c:76-84`).
Cross-ref `[[knowledge/subsystems/storage-ipc]]`, `[[knowledge/idioms/locking-overview]]`,
`.claude/skills/locking/SKILL.md`.

### 4. Server-side filesystem access (UTL_FILE) gated by an extension umask GUC

orafce implements Oracle's `UTL_FILE` (file I/O from SQL), and exposes
`orafce.umask` — *"Specify umask used by utl_file.fopen"* — with dedicated
check/assign hooks (`orafce_umask_check_hook`/`orafce_umask_assign_hook`,
`orafce.c:165-173`) `[verified-by-code]`. Backend code that reads and writes
arbitrary server files under a configurable umask is a security-relevant surface
core keeps tightly held (only superuser COPY, `adminpack`, etc.); orafce
recreates Oracle's directory-based file API on top of it. Cross-ref
`[[knowledge/idioms/error-handling]]` (file-access errno reporting).

## Notable design decisions (cited)

- **Compatibility GUCs use `check`/`assign` hooks to canonicalize and validate**:
  `check_sys_guid_source` rewrites aliases (`uuid_generate_v4` → `uuid_generate_v1`)
  and `guc_malloc`/`guc_free` the canonical string on PG ≥ 16, falling back to raw
  `malloc`/`free` earlier (`orafce.c:59-100`) `[verified-by-code]` — version-aware
  GUC memory management.
- **`to_char(int/float/numeric/timestamp)`** are separate `PG_FUNCTION_INFO_V1`
  entry points building text via `StringInfo` (`convert.c:22-55`)
  `[verified-by-code]` — Oracle's overloaded `TO_CHAR` mapped onto one C function
  per Postgres input type.
- **Pervasive `PG_VERSION_NUM` shimming** — `wait_event.h` vs `pgstat.h`,
  `instr_time.h` on PG ≥ 19, `varatt.h` on PG ≥ 16, the `lxid` field move on PG ≥ 17
  (`alert.c:16-30, 76-84`, `convert.c:16-20`) `[verified-by-code]`: one tree builds
  against a wide PG range, the recurring extension tax.
- **Long upgrade chain preserved**: every `orafce--X--Y.sql` from 3.2 forward is
  retained (tree listing) `[verified-by-code]`, the disciplined "never edit a
  released install script; only add upgrade diffs" practice the
  `extension-development` skill prescribes.

## Links into corpus

- `[[knowledge/ideologies/uuidv47]]` — sibling "custom type that delegates I/O to a
  core type's functions" (uuid47 → core `uuid`; nvarchar2 → core `varchar`/`text`).
- `[[knowledge/idioms/error-handling]]` — orafce makes warning-vs-error and
  Oracle-bug-vs-clean behavior a GUC, contra core's fixed call-site semantics.
- `[[knowledge/subsystems/storage-ipc]]` + `[[knowledge/idioms/locking-overview]]` —
  DBMS_PIPE/ALERT's hand-rolled shmem allocator (`shmmc.h`), `ConditionVariable`,
  LWLocks, and `RegisterXactCallback`-driven transactional delivery: a parallel
  notification bus next to core LISTEN/NOTIFY.
- `[[knowledge/idioms/catalog-conventions]]` — `varchar2`/`nvarchar2` type
  registration reusing core support functions.
- `.claude/skills/extension-development/SKILL.md` — `shmem_request_hook` shmem
  reservation; disciplined long upgrade-script chain.

## Anthropology takeaway

orafce's organizing idea is **compatibility-as-policy**: it does not merely add
Oracle functions, it makes the *choice of dialect* — down to whether to honor a
known Oracle `to_date()` bug — a set of `PGC_USERSET` GUCs. That is a distinct
posture from the rest of the doc-set (which mostly adds capability); it is worth
an idiom note as "behavior-toggle GUCs that select between two semantic
contracts," and a cautionary tale for testing (the same query yields different
results under different `orafce.*` settings). Two reusable threads: (a) the
`nvarchar2`-over-`text` pattern — reuse a core type's storage + send/transform/
typmod functions and override only input semantics — is the lightweight way to
introduce a "type" that is really a semantic skin, and pairs with the uuid47
observation about types delegating to core I/O. (b) DBMS_PIPE/ALERT is the
corpus's clearest case of an extension **rebuilding a core subsystem (NOTIFY) in
its own shmem** with a private allocator, condition variable, and xact-callback
delivery — a concrete data point for the recurring "core's useful internals
aren't exported, so extensions reimplement them" finding shared with
`[[knowledge/ideologies/pg_squeeze]]` and `[[knowledge/ideologies/pg_auto_failover]]`.
The `UTL_FILE` + `orafce.umask` surface is the natural Phase-D flag: configurable
server-side filesystem read/write reachable from SQL.

## Sources

Fetched 2026-06-10 (branch `master`):

- `https://api.github.com/repos/orafce/orafce/git/trees/master` @ 2026-06-10 →
  HTTP 200 (root tree listing; README is `README.asciidoc`, not `README.md`;
  confirmed the full `orafce--*.sql` upgrade chain and flat source layout).
- `https://raw.githubusercontent.com/orafce/orafce/master/README.md`
  @ 2026-06-10 → HTTP 404 (does not exist).
- `.../master/README.asciidoc` @ 2026-06-10 → HTTP 200 (41076 bytes; skimmed for
  package/function inventory).
- `.../master/orafce.control` @ 2026-06-10 → HTTP 200 (205 bytes).
- `.../master/orafce.c` @ 2026-06-10 → HTTP 200 (4306 bytes; deep-read — `_PG_init`,
  shmem reservation, xact callback, all eight compatibility GUCs + check hooks).
- `.../master/builtins.h` @ 2026-06-10 → HTTP 200 (18048 bytes; skimmed for the
  function/type declaration surface).
- `.../master/convert.c` @ 2026-06-10 → HTTP 200 (16767 bytes; head read —
  to_char/to_number entry points, version shims).
- `.../master/nvarchar2.c` @ 2026-06-10 → HTTP 200 (4972 bytes; deep-read —
  custom type reusing core varchar/text I/O + support functions).
- `.../master/alert.c` @ 2026-06-10 → HTTP 200 (23952 bytes; head read — shmem
  allocator include, ConditionVariable, LWLock, xact-callback transactional
  delivery, lxid shim).

All cites are `[verified-by-code]` against the fetched `.c`/`.h`/`.control`
except the nvarchar2 "reuse core" intentions, which are `[from-comment]`, and the
package inventory + Oracle-semantics framing, which are `[from-README]` /
`[inferred]` from the GUC descriptions. `pipe.c`, `shmmc.c` (the shared-memory
allocator), `dbms_sql.c`, `datefce.c`, and `file.c` (UTL_FILE) were not fetched;
claims about *how* DBMS_PIPE allocates shmem and *how* UTL_FILE performs I/O rest
on the includes + GUC declarations + `alert.c` call sites, tagged accordingly.
