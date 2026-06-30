# pgzx — the full C extension ABI re-expressed as a Zig library, leaning on `@cImport` instead of committed bindings

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `xataio/pgzx` @ branch `main`. All `file:line` cites below point into
> that repo (not `source/`), since this doc characterizes an *external*
> framework's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-30 (see Sources footer).

## Domain & purpose

pgzx is "a library for developing PostgreSQL extensions written in Zig … a set
of utilities (e.g. error handling, memory allocators, wrappers) as well as a
development environment that simplifies integrating with the Postgres code base"
(`README.md:15`) `[from-README]`. Like `[[knowledge/ideologies/pgrx]]` (its Rust
sibling), pgzx is a **meta-substrate**, not a single extension: it characterizes
*how* a non-C systems language reaches into the C backend ABI. The pitch is that
Zig "can interact with C code quite naturally … it supports the C ABI, can work
with C pointers and types directly, it can import header files and even translate
C code to Zig" (`README.md:21`) `[from-README]`, so "a Postgres extension written
in Zig can, theoretically, accomplish anything that a C extension can"
(`README.md:21`) `[from-README]`. The wrinkle pgzx exists to smooth is that
"Postgres makes extensive use of macros, and not all of them can be translated
automatically" (`README.md:23`) `[from-README]` — pgzx hand-fills the gaps Zig's
C translator leaves.

The user-facing minimum is a one-file extension (`nix/templates/init/src/main.zig:1-12`)
`[verified-by-code]`:

```zig
const pgzx = @import("pgzx");
comptime {
    pgzx.PG_MODULE_MAGIC();
    pgzx.PG_FUNCTION_V1("hello", hello);
}
fn hello() ![:0]const u8 { return "Hello, world!"; }
```

— no `PG_FUNCTION_INFO_V1` boilerplate, no `Datum` unpacking, no fmgr glue
written by hand. A conventional `.control` file is still shipped verbatim
(`nix/templates/init/extension/my_extension.control:1-5`) `[verified-by-code]`,
so unlike pgrx's generated catalog DDL, pgzx leaves the `.control` /
install-SQL convention untouched — only the C-side of the ABI is replaced.

## How it hooks into PG

pgzx re-expresses the C extension ABI but does it through a fundamentally
different binding mechanism than pgrx. The layering is:

1. **`pgzx_pgsys` — a live `@cImport` of the backend headers.** `src/pgzx/c.zig`
   is a single `@cImport({...})` block that `@cInclude`s ~150 PostgreSQL server
   headers — `postgres.h`, `fmgr.h`, `varatt.h`, the whole `catalog/pg_*.h`
   set, `nodes/*.h`, `optimizer/*.h`, `executor/spi.h`, `postmaster/bgworker.h`,
   `libpq-fe.h`, etc. (`src/pgzx/c.zig:3-200`) `[verified-by-code]`, then
   `pub usingnamespace includes;` (`:202`) re-exports the lot. This is the raw,
   unsafe `pg.*` surface. The decisive divergence from pgrx: pgrx ships
   *committed, per-major-version bindgen output*; pgzx regenerates bindings
   **at build time** from the installed server's headers, so one source tree
   targets whatever PG the `pg_config` on `PATH` points at (the build module
   adds `pgbuild.getIncludeServerDir()` to the include path,
   `build.zig:36-42`) `[verified-by-code]`.

2. **`src/pgzx/c/translate.c` — a manual escape hatch for untranslatable macros.**
   This file is marked "DO NOT COMPILE" (`src/pgzx/c/translate.c:1`)
   `[verified-by-code]`; it is an input to `zig translate-c -I $(pg_config
   --includedir-server)` (`:9`) used to "manually translate some postgres
   headers to zig so we can copy and fix symbols that zig could not handle
   correctly" (`:5`) `[from-comment]`. The hand-fixed output of that process is
   what lands in modules like `varatt.zig` (below).

3. **`src/pgzx.zig` — the module map** (the pgrx-`lib.rs`-equivalent), exposing
   `bgworker`, `datum`, `elog`, `err`, `fmgr`, `lwlock`, `mem`, `shmem`, `spi`,
   `collections` (List/SList/DList/HTab), `node`, `guc`, etc.
   (`src/pgzx.zig:13-57`) `[verified-by-code]`. `pub const c = @import("pgzx_pgsys")`
   (`:9`) keeps the raw surface reachable as `pgzx.c`.

4. **`build.zig` as the PGXS replacement.** There is no Makefile. `build.zig`
   declares the `pgzx_pgsys` and `pgzx` Zig modules, links `libpq`
   (`build.zig:57`), runs a `gennodetags` codegen tool that emits `nodetags.zig`
   from the headers (`build.zig:64-76`), and `pgbuild.addInstallExtension(...)`
   builds + installs the shared library and extension dir
   (`build.zig:136-143`, helper at `src/pgzx/build.zig:181-228`)
   `[verified-by-code]`. The shared lib is built with
   `linker_allow_shlib_undefined = true` (`src/pgzx/build.zig:396`)
   `[verified-by-code]` — the extension's `.so` is allowed to leave backend
   symbols unresolved, to be bound when the postmaster `dlopen`s it.

5. **`_PG_init` / module magic via `@export` codegen.** `PG_MODULE_MAGIC()`
   `@export`s a `Pg_magic_func` returning a `Pg_magic_struct` whose fields
   (version, `FUNC_MAX_ARGS`, `NAMEDATALEN`, `FLOAT8PASSBYVAL`, the
   `"PostgreSQL"` `abi_extra`) are pulled from the `@cImport`ed constants at
   comptime (`src/pgzx/fmgr.zig:20-50`) `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]`, `[[knowledge/idioms/memory-contexts]]`,
`[[knowledge/idioms/error-handling]]`, `.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. Error handling: a *hand-rolled* `sigsetjmp` ↔ Zig-error bridge, not a universal FFI guard

This is the central divergence and the direct analogue of pgrx's
`pg_guard_ffi_boundary`. Postgres `ereport(ERROR)` does a `siglongjmp` off
`PG_exception_stack`; a `longjmp` across live Zig frames skips their `defer` /
`errdefer` cleanup (`README.md:91`, `src/pgzx/err.zig:57-60`) `[from-comment]`.
pgzx's answer is `err.Context`: `init()` snapshots `PG_exception_stack`,
`error_context_stack`, and `CurrentMemoryContext` (`src/pgzx/err.zig:111-118`);
`pg_try()` calls `pg.sigsetjmp(&self.local_sigjump_buf, 0)`, installs the local
buffer as `PG_exception_stack`, and returns `true` on the straight path / `false`
on a longjmp landing (`src/pgzx/err.zig:130-137`); `pg_try_end()` restores all
three saved stacks (`:145-149`) `[verified-by-code]`.

The architecturally load-bearing detail — pgzx's equivalent of pgrx's
"NEVER remove this" invariant — is that `pg_try` **must be `inline`**: the file
shouts "NEVER RENMOVE THE 'inline'. `sigsetjmp` will not work correctly if used
within a function … By forcing the function to be inline the `sigsetjmp` happens
correctly within the stack context of the caller" (`src/pgzx/err.zig:126-129`)
`[from-comment]`. This is the same `setjmp`-must-not-return-before-`longjmp`
hazard core C sidesteps with the `PG_TRY` *macro*; pgzx cannot use a macro, so it
leans on Zig `inline fn` to reproduce the stack-frame guarantee.

The contrast with pgrx is the key anthropological finding. pgrx wraps **every**
bindgen-generated `pg_sys` call in `pg_guard_ffi_boundary` automatically and
bidirectionally. pgzx does **not** guard every call — the raw `pg.*` surface is
called directly, and guarding is *opt-in* per call site via `err.wrap(f, args)`
(`src/pgzx/err.zig:174-182`) or the `err.Context` pattern. The developer must
know which C calls can `ereport` and wrap those (the README explicitly hands the
user this responsibility, `README.md:91-105`) `[from-README]`. So where pgrx
buys universal safety at the cost of a guard on every FFI crossing, pgzx trades
that safety away for zero-overhead direct C calls and pushes the
`longjmp`-awareness onto the extension author. Cross-ref
`[[knowledge/idioms/error-handling]]`, `.claude/skills/error-handling/SKILL.md`.

### 2. The reverse direction: Zig errors → `ereport` via `throwAsPostgresError`

The fmgr entry wrapper closes the loop the other way. `throwAsPostgresError`
switches on the Zig error value: `error.PGErrorStack` → `pgRethrow()` (which
first switches back to `ErrorContext` then `PG_RE_THROW()`,
`src/pgzx/err.zig:46-53`); `error.OutOfMemory` → `ereport(ERROR,
ERRCODE_OUT_OF_MEMORY)`; anything else → `ereport(ERROR, ERRCODE_INTERNAL_ERROR,
"Unexpected error: {name}")` (`src/pgzx/elog.zig:290-311`) `[verified-by-code]`.
So a Zig error union returned from a user function is marshalled into a proper
`ereport` longjmp at the C boundary. `pgRethrow` carries a subtle correctness
note: Postgres sets the active context to `ErrorContext` during its longjmp, so
after pgzx has restored the saved context it must switch *back* to `ErrorContext`
before re-throwing (`src/pgzx/err.zig:48-52`) `[from-comment]`.

### 3. Memory contexts: Zig's `std.mem.Allocator` vtable implemented over palloc

Core C uses `palloc` / `MemoryContextSwitchTo` with the OOM-throws-`ereport`
contract (`memory-contexts` skill). pgzx projects this onto Zig's allocator
interface: `PGCurrentContextAllocator` is a `std.mem.Allocator` whose vtable
points at `pgAlloc`/`pgFree`/`pgResize`/`pgRemap`, where `pgAlloc` calls
`pg.palloc_aligned(len, align, MCXT_ALLOC_NO_OOM)` (`src/pgzx/mem.zig:22-36`)
`[verified-by-code]`. The deliberate inversion: it passes `MCXT_ALLOC_NO_OOM` so
Postgres returns NULL instead of throwing, which pgzx surfaces as Zig's
`error.OutOfMemory` — "The zig allocation APIs will still return an OutOfMemory
error that can be handled internally" (`src/pgzx/mem.zig:17-21`) `[from-comment]`.
This is the opposite of core's "palloc never returns NULL" contract: pgzx
*re-enables* NULL-returning allocation so the failure can travel as a Zig error
rather than a longjmp. `MemoryContextAllocator` binds a specific context so all
allocations land there (`src/pgzx/mem.zig:188-282`), and `TempMemoryContext`
switches `CurrentMemoryContext` on `init` and restores it on `deinit`
(`:140-160`), wrapping the AllocSet/Slab/Generation context constructors
(`:87-138`). Cross-ref `[[knowledge/idioms/memory-contexts]]`.

### 4. comptime codegen replaces the C preprocessor macros

Where core uses `PG_FUNCTION_INFO_V1(foo)` (a macro emitting a `pg_finfo_foo`
symbol) and `PG_GETARG_*`/`PG_RETURN_*`, pgzx uses Zig `comptime` + `@export`.
`PG_FUNCTION_V1(name, callback)` exports a `pg_finfo_<name>` record *and* an
`extern "C"` trampoline (`src/pgzx/fmgr.zig:56-66`) `[verified-by-code]`. The
trampoline `pgCall` uses `std.meta.ArgsTuple` + `inline for` over the user
function's argument types to read each Datum via a per-type `ArgType(field).read`
and repack the result via `datum.findConv(...).toNullableDatum`, routing any Zig
error through `throwAsPostgresError` (`src/pgzx/fmgr.zig:96-126`)
`[verified-by-code]`. `PG_EXPORT(module)` goes further: it `inline for`s over a
struct's decls and auto-registers every non-generic function as a SQL-callable
(`src/pgzx/fmgr.zig:68-82`) `[verified-by-code]`. So the fmgr calling convention
becomes comptime reflection over Zig types instead of preprocessor text
substitution. Cross-ref `[[knowledge/idioms/fmgr]]`,
`.claude/skills/fmgr-and-spi/SKILL.md`.

### 5. varlena/TOAST macros are hand-transliterated `zig translate-c` output

The `VARDATA`/`VARSIZE`/`VARATT_IS_*` family in `utils/varatt.h` is pure C
macros that Zig's `@cImport` "didn't compile correctly"
(`src/pgzx/varatt.zig:1-2`) `[from-comment]`. pgzx therefore copies the
`zig translate-c` output verbatim into `varatt.zig` — the body still carries the
generator's `@import("std").zig.c_translation.cast(...)` boilerplate
(`src/pgzx/varatt.zig:54-89`) `[verified-by-code]` — and flags it "Taken from
translated C code and mostly untested. The zig compiler will not complain about
errors if inline functions are not used" (`src/pgzx/varatt.zig:6-12`)
`[from-comment]`. This is a concrete instance of the README's "not all macros
translate automatically" gap (`README.md:23`): the cost of the live-`@cImport`
choice is that every macro-heavy header needs a hand-maintained shim, and those
shims are explicitly under-tested.

## Notable design decisions (cited)

- **Bindings are generated at build time from the live server headers, not
  committed.** `build.zig:36-42` adds `pgbuild.getIncludeServerDir()` to the
  `@cImport` include path; `src/pgzx/build.zig:660` resolves `pg_config` from
  `$PG_CONFIG` or `PATH`. `[verified-by-code]` This is the single sharpest
  contrast with pgrx (committed per-version `pgNN.rs`): pgzx needs no vendored
  bindings but needs `pg_config` + the server headers + libclang at every build.
- **Guarding the `longjmp` boundary is opt-in, not universal.** `err.wrap` /
  `err.Context` must be wrapped around C calls that can `ereport` by the author
  (`src/pgzx/err.zig:174-182`, `README.md:91-105`). `[verified-by-code]` Unlike
  pgrx's blanket `pg_guard_ffi_boundary`, an unwrapped C call that throws will
  longjmp straight past Zig `defer`s.
- **The `inline` keyword is load-bearing for `sigsetjmp` correctness.** An
  all-caps comment forbids removing it (`src/pgzx/err.zig:126-129`).
  `[from-comment]` This is the macro-vs-function tension core avoids with
  `PG_TRY` being a macro.
- **OOM is re-exposed as a returnable error via `MCXT_ALLOC_NO_OOM`.**
  `src/pgzx/mem.zig:32-36,17-21` `[verified-by-code]` — inverts core's
  "palloc never returns NULL" guarantee so failure can be a Zig error.
- **Shared-memory + hook registration is comptime-generic over a state struct.**
  `shmem.registerSharedState(T, &ptr)` installs `shmem_request_hook` /
  `shmem_startup_hook` that `RequestAddinShmemSpace(@sizeOf(T))` and
  `ShmemInitStruct`, preserving the previous hook in the chain
  (`src/pgzx/shmem.zig:14-60`) `[verified-by-code]`.
- **LWLock IDs into `MainLWLockArray` are hard-coded from `lwlocknames.txt`.**
  `src/pgzx/lwlock.zig:13-70` maps `ShmemIndex = mainLock(1)` … through
  `InjectionPoint = mainLock(51)` by literal index because "global locks … are
  not directly accessible from the generated C bindings" (`:3-5`).
  `[verified-by-code]` This is a brittle ABI coupling: the index list must track
  the running server's `lwlocknames.txt` by hand.
- **bgworker registration copies fixed-size name fields with comptime length
  checks.** `bgworker.register` zero-inits a `BackgroundWorker` and
  `copyForwards`es `bgw_name`/`bgw_library_name`/`bgw_function_name`, with a
  `@compileError` if a name overflows its field (`src/pgzx/bgworker.zig:65-100`).
  `[verified-by-code]`
- **The dev-environment is Nix-flake-based, not PGXS.** `nix flake init -t
  github:xataio/pgzx` scaffolds a working extension; `zig build pg_regress`
  drives the upstream `pg_regress`, and `zig build unit` runs unit tests *inside
  a live backend* via a SQL-callable `run_tests()` (`README.md:44-58,147-187`).
  `[from-README]` Like pgrx's `cargo pgrx test`, "unit tests" are really
  in-backend integration tests.
- **Maturity caveat.** The README marks SPI and Shared memory as unchecked on
  the roadmap and only PG 17 as a confirmed target, warning "expect breaking
  changes and potential instability" (`README.md:189-223`). `[from-README]`

## Links into corpus

- `[[knowledge/ideologies/pgrx]]` — the canonical sibling: pgrx is the Rust
  meta-substrate, pgzx the Zig one. The sharpest contrasts: (a) committed
  bindings vs live `@cImport`; (b) universal `pg_guard_ffi_boundary` vs opt-in
  `err.wrap`; (c) pgrx generates `.control`/SQL, pgzx keeps them hand-written.
- `[[knowledge/ideologies/pg-extend-rs]]` — **does not yet exist** in
  `knowledge/ideologies/` as of 2026-06-30 (verified by `ls`); listed in the
  task as a sibling-to-be. No file to link.
- `[[knowledge/idioms/error-handling]]` — `err.Context` (`sigsetjmp`) +
  `throwAsPostgresError` are the bidirectional `ereport`/`longjmp` ↔ Zig-error
  bridge; the `inline`-for-`sigsetjmp` constraint is the Zig analogue of the
  `PG_TRY` macro requirement.
- `[[knowledge/idioms/memory-contexts]]` — `MemoryContextAllocator` /
  `PGCurrentContextAllocator` implement `std.mem.Allocator` over palloc, and
  `MCXT_ALLOC_NO_OOM` re-enables NULL-returning allocation.
- `[[knowledge/idioms/fmgr]]` — `PG_FUNCTION_V1` / `pgCall` synthesize the
  `pg_finfo` record + Datum-marshalling trampoline via comptime reflection.
- `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/fmgr-and-spi/SKILL.md`,
  `.claude/skills/memory-contexts/SKILL.md`,
  `.claude/skills/error-handling/SKILL.md`,
  `.claude/skills/bgworker-and-extensions/SKILL.md` — pgzx is the systematic
  Zig restatement of all five.

## Anthropology takeaway (for STATE.md / cross-corpus)

pgzx and pgrx solve the *same* problem — bring a memory-safe systems language up
to the full C extension ABI — and land on opposite points of the safety/overhead
tradeoff. pgrx makes the `ereport`/`longjmp` ↔ unwinding bridge **universal and
invisible** (every `pg_sys` call guarded); pgzx makes it **explicit and opt-in**
(`err.wrap` only where the author knows a C call can throw), preserving direct,
zero-cost C calls and a live `@cImport` of the running server's headers instead
of committed per-version bindings. The load-bearing artifact is
`src/pgzx/err.zig`: the all-caps "NEVER REMOVE THE 'inline'" comment is a precise
restatement of why core's `PG_TRY` is a *macro* and not a function — `sigsetjmp`
must execute in the caller's stack frame. Any future "should core offer a
non-C-caller-friendly error boundary?" discussion now has two reference
implementations to compare: pgrx's blanket guard and pgzx's per-site wrap.

## Sources

Fetched 2026-06-30 (branch `main`):

- `https://raw.githubusercontent.com/xataio/pgzx/main/README.md` → HTTP 200 (25323 bytes).
- `https://raw.githubusercontent.com/xataio/pgzx/main/build.zig` → HTTP 200 (5811 bytes).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx.zig` → HTTP 200 (2107 bytes; module map).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/c.zig` → HTTP 200 (6949 bytes; the `@cImport` of ~150 headers).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/c/translate.c` → HTTP 200 (395 bytes; the `zig translate-c` shim, "DO NOT COMPILE").
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/mem.zig` → HTTP 200 (13149 bytes; allocator-over-palloc — deep-read).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/err.zig` → HTTP 200 (6346 bytes; `sigsetjmp`/`Context`/`wrap` — deep-read).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/elog.zig` → HTTP 200 (21505 bytes; `ereport` wrappers + `throwAsPostgresError` — deep-read of bridge).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/fmgr.zig` → HTTP 200 (4092 bytes; magic + `PG_FUNCTION_V1` + `pgCall` codegen — deep-read).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/varatt.zig` → HTTP 200 (12147 bytes; hand-transliterated varlena macros — header + sample read).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/shmem.zig` → HTTP 200 (2345 bytes).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/lwlock.zig` → HTTP 200 (2574 bytes; hard-coded MainLWLockArray IDs).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/bgworker.zig` → HTTP 200 (3384 bytes).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/spi.zig` → HTTP 200 (8733 bytes; skimmed).
- `https://raw.githubusercontent.com/xataio/pgzx/main/src/pgzx/build.zig` → HTTP 200 (helper module; `addInstallExtension`, `pg_config`, `allow_shlib_undefined` — fetched in addition to the manifest).
- `https://raw.githubusercontent.com/xataio/pgzx/main/nix/templates/init/src/main.zig` → HTTP 200 (200 bytes; minimal extension example).
- `https://raw.githubusercontent.com/xataio/pgzx/main/nix/templates/init/extension/my_extension.control` → HTTP 200 (144 bytes).

All 16 manifest URLs (+ the `src/pgzx/build.zig` helper) returned HTTP 200; no
404 gaps. Cites tagged `[verified-by-code]` are read directly from the fetched
`.zig`/`.c` files; `[from-comment]` cites quote in-file doc comments;
`[from-README]` cites the dev-environment / roadmap narrative. `spi.zig` was
skimmed (status-check + Rows pattern only), not deep-read.
