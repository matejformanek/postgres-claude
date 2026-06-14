# GUC variables — long-form

Conceptual reference for the GUC (Grand Unified Configuration) subsystem.
For the procedural cookbook see `.claude/skills/gucs-config/SKILL.md`.

## Big picture

GUC is the single mechanism Postgres uses for *every* configuration knob —
boolean, int, real, string, enum. Same code paths apply to in-tree
parameters like `work_mem` and to extension-defined parameters like
`pg_stat_statements.max`. Each variable has:

- a **type** (`PGC_BOOL` / `PGC_INT` / `PGC_REAL` / `PGC_STRING` / `PGC_ENUM`)
  — [verified-by-code `source/src/include/utils/guc_tables.h:22-27`]
- a **context** (`PGC_INTERNAL` .. `PGC_USERSET`) controlling who can change
  it and when — [verified-by-code `source/src/include/utils/guc.h:71-80`]
- a **source** tracker (`PGC_S_DEFAULT` .. `PGC_S_SESSION`) recording where
  the current value came from, so a later-priority source can override
  while a same-or-lower one is ignored — [verified-by-code
  `source/src/include/utils/guc.h:111-127`]
- a **boot_val** (compile-time default), a **reset_val** (target for
  RESET), and a stack of saved values for transactional rollback —
  [from-README `source/src/backend/utils/misc/README:130-150`].

The defining table is `ConfigureNames` in `guc_tables.c`; in-tree GUCs
live in static arrays `ConfigureNamesBool[]`, `...Int[]`, `...Real[]`,
`...String[]`, `...Enum[]`. Custom GUCs are appended at runtime via
`DefineCustom*Variable`.

## Namespacing — why `module.var`

Every extension-defined GUC must use a dotted name like `my_ext.naptime`.
The first segment ("class prefix") namespaces the variable.

Two reasons:

1. **Forward-references work.** A user can put `my_ext.naptime = 30` in
   `postgresql.conf` before `my_ext` is loaded. guc.c accepts the
   setting as a *placeholder* — a `config_string` with the
   `GUC_CUSTOM_PLACEHOLDER` flag — and stashes the value. When the
   extension loads and calls `DefineCustomIntVariable("my_ext.naptime",
   ...)`, guc.c sees the placeholder and applies its stored value to
   the freshly-typed variable.
   [verified-by-code `source/src/include/utils/guc.h:223`]

2. **Typo detection.** `MarkGUCPrefixReserved("my_ext")` registers the
   prefix and refuses any future placeholders under it. A line
   `my_ext.napitme = 30` then errors out with `unrecognized configuration
   parameter` instead of being silently accepted.
   [verified-by-code `source/src/backend/utils/misc/guc.c:5178-5228`]

**Operational rule**: call `MarkGUCPrefixReserved("prefix")` at the *end*
of `_PG_init` after every `DefineCustom*Variable`. Before — and you'd
delete your own variables. After — and you get the typo-detection
benefit cleanly.

## `ALTER SYSTEM` and `postgresql.auto.conf`

`ALTER SYSTEM SET foo = 'x'` doesn't change the running value directly.
It writes a key/value into `$PGDATA/postgresql.auto.conf`. That file is
parsed by the normal config-file machinery after the main
`postgresql.conf`, so its values win on (re)load. The current process
applies the new value only on the next config reload (SIGHUP or
`pg_reload_conf()`) — or, for `PGC_POSTMASTER` GUCs, only on the next
postmaster restart.

A GUC marked `GUC_DISALLOW_IN_AUTO_FILE` cannot be set this way; one
marked `GUC_DISALLOW_IN_FILE` cannot be set in any file (only at runtime).
[verified-by-code `source/src/include/utils/guc.h:222-228`]

The constant `PG_AUTOCONF_FILENAME = "postgresql.auto.conf"` is in
`guc.h:37`. [verified-by-code `source/src/include/utils/guc.h:37`]

## Hot-reload vs restart-required

The context value answers "what changes at reload":

- `PGC_INTERNAL` — never user-changeable. Show-only.
- `PGC_POSTMASTER` — read once at postmaster start. SIGHUP ignores
  changes; you'd need a full server restart.
- `PGC_SIGHUP` — applied at next config reload. The postmaster and each
  backend re-read the file when SIGHUP'd.
- `PGC_BACKEND` / `PGC_SU_BACKEND` — frozen for the life of one
  connection; client can pick a value via libpq `PGOPTIONS` at connect
  time. Once a backend is running, file changes don't affect it.
- `PGC_SUSET` — runtime, superuser-only via `SET` or
  `ALTER {DATABASE,ROLE,SYSTEM}`.
- `PGC_USERSET` — runtime, anyone via `SET`.

[verified-by-code `source/src/include/utils/guc.h:71-80`]

Picking the right context is the only way to guarantee invariants. If
your extension allocates a shared-memory area sized from `my_ext.size`,
`PGC_POSTMASTER` is mandatory — anything looser and a SIGHUP could
"change" the value while the allocation is fixed, silently breaking the
size assumption everywhere.

## Stacking and rollback

Inside a transaction, every modification to a GUC pushes a stack entry
keyed by the current "nest level" (incremented per subtransaction or per
function call with a `SET` option). At commit/abort, entries are popped:

- abort → restore prior values
- commit at level 1 → `SET LOCAL` rolls back, plain `SET` sticks

The full state-machine for combining SET / SET LOCAL / SAVE entries at
the same level is documented in `source/src/backend/utils/misc/README:162-234`.
The key invariant for hook authors: `assign_hook` may be called during
rollback. Hence its prohibition on catalog lookups (which would re-enter
SnapshotXY machinery during transaction teardown). All possibly-failing
work goes into `check_hook` and is passed through `extra`.
[from-README `source/src/backend/utils/misc/README:78-109`]

## Source precedence

A pending change is accepted only if its `GucSource` value is `>=` the
recorded source of the current setting:

```
PGC_S_DEFAULT < S_DYNAMIC_DEFAULT < S_ENV_VAR < S_FILE < S_ARGV
              < S_GLOBAL < S_DATABASE < S_USER < S_DATABASE_USER
              < S_CLIENT < S_OVERRIDE < S_INTERACTIVE < S_TEST < S_SESSION
```

So a SIGHUP'd config file (`PGC_S_FILE`) cannot override a postmaster
command-line setting (`PGC_S_ARGV`), but a `SET` (`PGC_S_SESSION`) can
override anything except `PGC_S_OVERRIDE`. This is the source of the
"setting doesn't take effect on reload" surprise: the new value is
strictly lower-priority than the current source, so it's discarded.
[verified-by-code `source/src/include/utils/guc.h:88-127`]

## Custom GUCs — what guc.c stores for you

For every `DefineCustom*Variable` call, guc.c:

1. Allocates a `config_X` struct (one of the type-specific structs in
   `guc_tables.h:139-209`) wrapped in a `config_generic`.
2. Records your `valueAddr` — the address of *your* C variable. From
   now on guc.c writes the live value through that pointer.
3. Picks an initial value: if a placeholder exists for this name,
   applies its stored value; otherwise applies the boot_val.
4. Adds the struct to the global GUC hashtable and to a sorted
   `guc_variables` array.

The `valueAddr` aliasing matters: anywhere in your code, reading
`my_naptime` reads the current effective GUC value, no helper call
needed.

## String GUCs are special

Strings own heap storage. The actual `char *` is owned by guc.c (the
underlying buffer is allocated with `guc_malloc`), and guc.c may reassign
it. Hence the variable type is `char **` — `valueAddr` is the address of
the pointer, not of the storage. A check_hook that wants to canonicalize
a string must `guc_malloc` the replacement and `guc_free` the previous
one. [from-README `source/src/backend/utils/misc/README:51-60, 255-272`]

A NULL `boot_val` is allowed; SQL `SET` and config files cannot produce
NULL (only empty strings), so consumers must be prepared for NULL only
if a static initializer can produce it. [from-README
`source/src/backend/utils/misc/README:274-294`]

## Files examined

| File | Depth | Produced |
|---|---|---|
| `source/src/backend/utils/misc/README` | full read | this doc + SKILL.md |
| `source/src/include/utils/guc.h` | full read | SKILL.md §1 (Define* signatures, GucContext, GucSource, flags) |
| `source/src/include/utils/guc_tables.h` | scanned (lines 22-209 for structs) | conceptual model |
| `source/src/backend/utils/misc/guc.c:5178-5228` | targeted (`MarkGUCPrefixReserved`) | §"Namespacing" + SKILL.md §1.4 |
| `source/src/test/modules/worker_spi/worker_spi.c:303-360` | targeted (custom-GUC defs + MarkGUCPrefixReserved) | SKILL.md §1.3 |
