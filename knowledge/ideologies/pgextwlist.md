# pgextwlist — a ProcessUtility interceptor that runs whitelisted CREATE EXTENSION as the bootstrap superuser

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `dimitri/pgextwlist` @ branch `master`, fetched 2026-07-05.
> Caveat: characterization based on the files actually fetched — `README.md`,
> `Makefile`, `pgextwlist.c` (the 498-line core, read in full), `utils.c` (the
> 679-line script-runner, read in full), `utils.h`, and `pgextwlist.h`. NOT
> fetched: the `expected/` + `test/`(`sql/`) regression fixtures named by
> `REGRESS = setup pgextwlist errors crossuser hooks` in the Makefile, and the
> packaging spec files (`debian/`, `pgextwlist.spec`). There is no
> `pgextwlist.control` (probe → 404): the module is loaded as a plain shared
> library via `local_preload_libraries`, never `CREATE EXTENSION`'d — despite
> being *about* extensions.

## Domain & purpose

pgextwlist solves the oldest managed-Postgres problem: **let a non-superuser
install a curated set of extensions, without handing them superuser**. Its
thesis, verbatim: "this extension implements a form of `sudo` facility in that
the whitelisted extensions will get installed as if *superuser*. Privileges are
dropped before handing the control back to the user" [from-README, README.md:5-7].
It does two things at once — (1) a **guard**: actively refuse `CREATE EXTENSION`
for anything not on an admin-provided allowlist; and (2) a **proxy**: for
allowlisted names, transiently elevate to the bootstrap superuser so the install
succeeds even though the caller has no such right [from-README, README.md:3-10].
The commands it proxies are `CREATE EXTENSION`, `DROP EXTENSION`,
`ALTER EXTENSION … UPDATE`, and `COMMENT ON EXTENSION`; `ALTER EXTENSION …
ADD|DROP` is deliberately *not* supported, so a user cannot mutate an
already-installed extension's object set [from-README, README.md:9-13;
verified-by-code, pgextwlist.c:397-399]. It ships no SQL objects and no catalog
entries — all behavior is driven by two `PGC_SUSET` GUCs.

This is the **historical ancestor** of the privilege-emulation pattern later
generalized by `supautils` (copyright here is "Dimitri Fontaine, 2011-2013",
pgextwlist.c:5 — predating the cloud-Postgres vendors that productized it).

## How it hooks into PG

Load model is **`local_preload_libraries = 'pgextwlist'`** with the `.so`
installed into `` `pg_config --pkglibdir`/plugins `` [from-README,
README.md:37-52]. This is the unusual middle path between the two common
options: not `shared_preload_libraries` (postmaster-wide) and not lazy
`CREATE EXTENSION` load. `local_preload_libraries` loads the module into every
*ordinary backend* at connection start but forbids modules outside the `plugins`
subdirectory and grants no elevated init — exactly right for a per-session
utility hook that must be installed before the user runs any DDL, yet must not
require a server restart or a superuser to enable per-role via `ALTER ROLE …
SET` [from-README, README.md:49-62]. The build is plain PGXS, `MODULE_big =
pgextwlist` over `OBJS = utils.o pgextwlist.o` — a two-TU shared object with no
`EXTENSION`/`DATA` line, confirming there is no installable SQL side
[verified-by-code, Makefile:4-6].

`_PG_init` does three things: define the two string GUCs, call
`EmitWarningsOnPlaceholders("extwlist")`, and chain the utility hook
[verified-by-code, pgextwlist.c:151-180]:

```c
prev_ProcessUtility = ProcessUtility_hook;
ProcessUtility_hook = extwlist_ProcessUtility;
```

The GUCs are `extwlist.extensions` (the comma-separated allowlist) and
`extwlist.custom_path` (where before/after scripts live), **both `PGC_SUSET`**
so an ordinary user cannot widen their own allowlist — only a superuser (or
`ALTER ROLE … SET` applied by one) can [verified-by-code, pgextwlist.c:154-174].
`PG_MODULE_MAGIC` is the bare no-arg form [verified-by-code, pgextwlist.c:62].

### The core mechanism: the SECURITY DEFINER identity swap

The dispatcher `extwlist_ProcessUtility` first short-circuits for the two cases
where it must do nothing — outside a transaction, or when the caller is already
a superuser [verified-by-code, pgextwlist.c:282-286]:

```c
if (!IsTransactionState() || superuser())
{
    call_RawProcessUtility(PROCESS_UTILITY_ARGS);
    return;
}
```

Otherwise it switches on `nodeTag(parsetree)` for the four supported extension
statements, extracts the extension name, checks it against the allowlist, and
for a match routes through `call_ProcessUtility` [verified-by-code,
pgextwlist.c:288-400]. That function is the load-bearing trick — it emulates a
`SECURITY DEFINER` procedure owned by a superuser, hard-coded to the bootstrap
user [verified-by-code, pgextwlist.c:413-429]:

```c
GetUserIdAndSecContext(&save_userid, &save_sec_context);
SetUserIdAndSecContext(BOOTSTRAP_SUPERUSERID,
                       save_sec_context
                       | SECURITY_LOCAL_USERID_CHANGE
                       | SECURITY_RESTRICTED_OPERATION);
/* ...run before-scripts, the real command, after-scripts... */
SetUserIdAndSecContext(save_userid, save_sec_context);
```

The final `SetUserIdAndSecContext(save_userid, save_sec_context)` is the "drop
privileges before handing control back" step the README promises
[verified-by-code, pgextwlist.c:488]. The real command runs via
`call_RawProcessUtility`, which chains `prev_ProcessUtility` or falls back to
`standard_ProcessUtility` — the textbook save-previous-then-chain idiom
[verified-by-code, pgextwlist.c:491-498].

## Where it diverges from core idioms

- **An "extension" that is never `CREATE EXTENSION`'d.** The whole module is a
  hook library with no `.control` file (probe → 404) and no SQL install script.
  It is loaded through `local_preload_libraries` into the `plugins` directory,
  not through the extension machinery it governs [from-README, README.md:37-52].
  Core's mental model is "an extension is a catalog-tracked bundle of SQL
  objects"; pgextwlist is a bare `.so` that *intercepts* that machinery from
  outside it.

- **Hard-coded `BOOTSTRAP_SUPERUSERID`, not a configurable proxy role.** Core
  gates superuser-only DDL with a binary `superuser()` check and no in-between.
  pgextwlist inserts a policy layer that runs the command *as the bootstrap
  superuser itself* — the single most-privileged identity, chosen unconditionally
  rather than as a named, lesser role [verified-by-code, pgextwlist.c:426]. This
  is simpler and blunter than the descendant `supautils`, which lets the
  provider name a specific `supautils.superuser` role.

- **Objects stay owned by the superuser.** Unlike `supautils`, pgextwlist does
  *not* re-own the created objects back to the caller: "the extension and all
  its objects are owned by this *superuser*" [from-README, README.md:15-17]. The
  privilege is borrowed for the duration of the command and the resulting
  objects are simply superuser-owned; granting the caller usage is left to the
  optional custom scripts. This is the single biggest behavioral contrast with
  its descendant.

- **Vendors core's static internals rather than calling them.** `utils.c` is,
  by its own header comment, code "from the PostgreSQL source tree in
  `src/backend/commands/extension.c`, with some modifications" [verified-by-code,
  utils.c:11-17]. Because `execute_sql_string`, `read_binary_file`, and the
  control-file parser are `static` in core and therefore un-callable from an
  extension, pgextwlist copies them: `execute_sql_string` (utils.c:381-510),
  `read_custom_script_file` (a re-implementation of the 9.5-static
  `read_binary_file`, utils.c:307-366), and
  `parse_default_version_in_control_file` (utils.c:71-126). This copy-and-drift
  is a maintenance liability the code openly accepts — it even re-derives the
  extension's default version by opening and parsing `…/extension/<name>.control`
  by hand with `ParseConfigFp` [verified-by-code, utils.c:86-121].

- **Deliberately avoids SPI.** The vendored `execute_sql_string` explains it
  does not use SPI because "SPI will parse, analyze, and plan the whole string
  before executing any of it … this fails if there are any planable statements
  referring to objects created earlier in the script" — so it hand-rolls the
  parse → `pg_analyze_and_rewrite` → `pg_plan_queries` → `ExecutorRun` /
  `ProcessUtility` loop with a `CommandCounterIncrement()` between statements
  [verified-by-code, utils.c:368-510]. This mirrors exactly why core's own
  `CREATE EXTENSION` script runner avoids SPI.

- **All-or-nothing elevation for multi-target `DROP EXTENSION`.** `DROP
  EXTENSION a, b, c` only gets superpowers if *every* named extension is
  whitelisted; a single non-whitelisted name in the list drops the elevation and
  the command runs as the plain user — "better play safe" [verified-by-code,
  pgextwlist.c:330-369].

## Notable design decisions

- **Whitelist is a plain comma-list GUC parsed with `SplitIdentifierString`.**
  `extension_is_whitelisted` `pstrdup`s the GUC, splits on `,`, and does a linear
  `strcmp` scan; a syntax error in the list raises
  `ERRCODE_INVALID_PARAMETER_VALUE` [verified-by-code, pgextwlist.c:235-261].
  No pattern matching, no wildcards (contrast `supautils`'s trailing-`*`
  "configurable" marker).

- **`SECURITY_RESTRICTED_OPERATION` hardens the elevated window.** ORing it in
  alongside `SECURITY_LOCAL_USERID_CHANGE` blocks the search-path / trojan-function
  attacks that a naive `SetUserId(superuser)` would expose during the elevated
  command [verified-by-code, pgextwlist.c:426-429]. This is the same defensive
  pairing `supautils` later uses in its `switch_to_superuser`.

- **Before/after custom scripts around the real command.** For each supported
  action, `call_extension_scripts` looks for version-specific then generic
  scripts under `${extwlist.custom_path}/${extname}/` and runs the ones that
  exist — `before--1.0.sql` / `before-create.sql` … `after--1.0.sql` /
  `after-create.sql`, and the `before--old--new.sql` form for updates
  [verified-by-code, pgextwlist.c:182-233, utils.c:128-172; from-README,
  README.md:144-188]. These run *inside* the elevated window, so they too
  execute as the superuser — the intended hook point for `GRANT`-ing the new
  objects to the caller.

- **Custom-script templating + `\echo` stripping.** Before execution each script
  gets `@extschema@`, `@current_user@`, and `@database_owner@` substituted (via
  `replace_text` `DirectFunctionCall`s), and any line starting with `\echo` is
  regex-blanked so an operator can paste a normal psql-guarded script
  [verified-by-code, utils.c:611-667; from-README, README.md:190-206].

- **Copies core's script-execution GUC discipline.** `execute_custom_script`
  forces `client_min_messages` / `log_min_messages` to at least `WARNING`, pins
  `search_path` to the target schema via `set_config_option(… GUC_ACTION_SAVE)`,
  and unwinds everything with `AtEOXact_GUC(true, save_nestlevel)` — lifted
  straight from core's `execute_extension_script` [verified-by-code,
  utils.c:544-679].

- **A decade-plus of version-shim macros.** `PROCESS_UTILITY_PROTO_ARGS` /
  `PROCESS_UTILITY_ARGS` are redefined five times across `PG_MAJOR_VERSION`
  boundaries (< 903, < 1000, < 1300, < 1400, else) to track the evolving
  `ProcessUtility_hook` signature (addition of `ProcessUtilityContext`,
  `QueryEnvironment`, `QueryCompletion`, `readOnlyTree`) [verified-by-code,
  pgextwlist.c:72-121]; the `strVal` node-extraction path similarly forks at
  `< 1000` / `< 1500` for the `Value` → `String` node split [verified-by-code,
  pgextwlist.c:343-349]. README claims PG 10+ support [from-README,
  README.md:19]; the macro floor in `pgextwlist.h` errors below 9.1.

- **`EmitWarningsOnPlaceholders`, the pre-`MarkGUCPrefixReserved` API.** The
  module uses the older placeholder-reservation call [verified-by-code,
  pgextwlist.c:176], reflecting its age; modern extensions call
  `MarkGUCPrefixReserved("extwlist")` instead.

## Links into corpus

- [[supautils]] — **the direct descendant.** `knowledge/ideologies/supautils.md`
  (§Notable design decisions) states its `CREATE EXTENSION` delegation was
  "adapted from pgextwlist." pgextwlist is the seed: the *switch to superuser →
  run the real utility command → restore the caller* pattern
  (`GetUserIdAndSecContext` / `SetUserIdAndSecContext` with
  `SECURITY_LOCAL_USERID_CHANGE | SECURITY_RESTRICTED_OPERATION`) is identical in
  both. supautils **generalized** it from "just the four extension DDLs, elevated
  to the hard-coded bootstrap superuser, objects left superuser-owned" into a
  whole privilege-emulation layer: a *configurable* proxy role, a giant
  `utilityStmt->type` switch spanning roles / publications / FDWs / event
  triggers / policies, and `alter_owner()` re-ownership of the created object
  back to the privileged role. pgextwlist = the minimal ancestor; supautils =
  the maximal generalization.
- [[pg_tle]] — the *other* answer to "let non-superusers install extensions
  safely," from the opposite mechanism: instead of a ProcessUtility proxy that
  runs the real `CREATE EXTENSION` as superuser, pg_tle makes extensions
  first-class trusted-language artifacts installed through a controlled SQL API,
  sidestepping filesystem `.control`/`.sql` files entirely. Same problem,
  disjoint solution.
- [[pgaudit]] — another `ProcessUtility_hook` consumer, but for *observation*
  (logging DDL/DML), not privilege emulation; useful contrast on hook intent
  (watch vs. elevate).
- [[pg_permissions]] — adjacent "who can do what" auditing angle; complements
  pgextwlist's enforcement stance.

## Sources

- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/README.md` — HTTP 200.
  Thesis, load model (`local_preload_libraries` + `plugins` dir), supported
  commands, custom-scripts spec, templating rules, Internals note.
- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/Makefile` — HTTP 200.
  `MODULE_big = pgextwlist`, `OBJS = utils.o pgextwlist.o`,
  `REGRESS = setup pgextwlist errors crossuser hooks`. No `EXTENSION`/`DATA`.
- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/pgextwlist.c` — HTTP 200.
  The core; all `pgextwlist.c` cites point here (`_PG_init`, GUCs,
  `extwlist_ProcessUtility` dispatcher, `call_ProcessUtility` identity swap,
  `extension_is_whitelisted`, version-shim macros).
- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/utils.c` — HTTP 200.
  The vendored-from-core script runner: `parse_default_version_in_control_file`,
  `get_extension_current_version`, `fill_in_extension_properties`,
  `execute_sql_string`, `read_custom_script_file`, `execute_custom_script`.
- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/utils.h` — HTTP 200.
  Function decls + `MAXPGPATH` + extern GUC decls.
- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/pgextwlist.h` — HTTP 200.
  `PG_MAJOR_VERSION` derivation + the 9.1 version floor.
- `https://raw.githubusercontent.com/dimitri/pgextwlist/master/pgextwlist.control` — HTTP 404.
  No control file; the module is a `local_preload_libraries` library, never
  `CREATE EXTENSION`'d.
- GitHub git/trees + Contents API — not usable (session scoped to a different
  repo; 403). File set resolved from the Makefile `OBJS` line + raw-CDN probes.
- NOT fetched: `sql/` + `expected/` regression fixtures (`setup`, `pgextwlist`,
  `errors`, `crossuser`, `hooks`), `debian/`, `pgextwlist.spec`.
