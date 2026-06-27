# pldotnet — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `Brick-Abode/pldotnet` @ branch `master`. All `file:line` cites below
> point into THAT repo (not PG `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-27 (see Sources footer).
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** pldotnet is the CLR member of the foreign-runtime-PL family
> the corpus already covers with [[pljava]] (JVM via JNI) and [[plv8]] (V8
> isolate). The recurring question — *how do you host a managed, GC'd execution
> engine inside a single-threaded, longjmp-driven PG backend?* — gets its .NET
> answer here. Read it against [[pljava]] especially: both embed a full managed
> runtime per backend, but pldotnet's CLR↔PG boundary is far thinner (raw P/Invoke
> + function-pointer delegates, no bidirectional ErrorData round-trip), and it
> ships **two** PG languages (`plcsharp` + `plfsharp`) from one `.so`.

## Domain & purpose

pldotnet "adds full support for C# and F# to PostgreSQL"
`[from-README: README.md:5]`, claiming to be "the fastest PL in PostgreSQL" and
"the only PL using the native database API; our database access (SPI) is fully
NPGSQL-compatible" `[from-README: README.md:7,10]`. You write a function body in
C# or F# inside `CREATE FUNCTION … LANGUAGE plcsharp` / `LANGUAGE plfsharp`
`[from-README: README.md:21-40]`, or load a precompiled `.dll`
`[from-README: README.md:11]`. It supports functions, procedures, `DO` blocks,
triggers, SRFs, records, OUT/INOUT, and table functions
`[from-README: README.md:8,49-59]`, and marshals 38 of 46 standard PG types into
Npgsql/.NET shapes `[from-README: README.md:9]`. The control file's
`default_version = '0.9'` `[verified-by-code: pldotnet.control:2]` lags the
README's "0.99 … public beta" `[from-README: README.md:5]`. Written in C (the PG
glue + Datum decomposition) plus a large C# runtime under `dotnet_src/` (the
engine, code generator, and per-type handlers).

## How it hooks into PG

- **Two full PL handler trios from one module.** `pldotnet--0.9.sql` registers
  `plcsharp_call_handler` / `plcsharp_inline_handler` / `plcsharp_validator` and
  the matching `plfsharp_*` trio, then two `CREATE LANGUAGE plcsharp` /
  `plfsharp` statements binding `HANDLER` / `INLINE` / `VALIDATOR`
  `[verified-by-code: pldotnet--0.9.sql:4-37]`. All six entry points are
  `PG_FUNCTION_INFO_V1` `[verified-by-code: src/pldotnet_main.c:29-34]`; each is a
  thin wrapper over `pldotnet_generic_handler(fcinfo, is_inline, language)` /
  `pldotnet_validator(fcinfo, language)` with the language enum threaded through
  `[verified-by-code: src/pldotnet_main.c:444-469]`. This is the standard
  `pg_language.lanplcallfoid` seam, used exactly as core plperl/plpython do.

- **CLR hosted via hostfxr/nethost (CoreCLR), not Mono.** The host layer dlopens
  `libhostfxr.so` and binds `hostfxr_initialize_for_runtime_config`,
  `hostfxr_get_runtime_delegate`, `hostfxr_set_runtime_property_value`,
  `hostfxr_close` `[verified-by-code: src/pldotnet_hostfxr.c:104-127]`. It first
  asks `nethost`'s `get_hostfxr_path`, falling back to literally shelling out
  `dpkg -L dotnet-hostfxr-6.0 | grep libhostfxr.so | … | xargs dirname` via
  `popen` `[verified-by-code: src/pldotnet_hostfxr.c:76-100,110-112]` — i.e. a
  hard dependency on .NET 6 installed as a Debian package.
  `GetNetLoadAssemblySetup` initializes the runtime config, optionally sets
  `APP_CONTEXT_BASE_DIRECTORY`, and fetches the
  `hdt_load_assembly_and_get_function_pointer` delegate
  `[verified-by-code: src/pldotnet_hostfxr.c:129-160]`.

- **`_PG_init` eagerly boots the CLR and wires delegates.** Unlike pljava (which
  defers JVM start to first call), pldotnet's `_PG_init` runs the whole bring-up
  synchronously: `pldotnet_LoadHostFxrIfNeeded` → `pldotnet_BuildPaths` →
  `pldotnet_SetNetLoader` → `pldotnet_SetDotNetMethods`, then allocates the
  `procedures` cache `[verified-by-code: src/pldotnet.c:35-56]`. Any failure is a
  hard `elog(ERROR)` at load time `[verified-by-code: src/pldotnet.c:42-49]`.

- **The C↔CLR API is seven static-method function pointers into one assembly.**
  `pldotnet_SetDotNetMethods` resolves `CompileUserFunction`, `RunUserFunction`,
  `RunUserTFunction`, `BuildDatumList`, `AddDatumToList`, `FreeGenericGCHandle`,
  and `UnloadAssemblies` — all `PlDotNET.Engine` statics, each via its declared
  delegate type `[verified-by-code: src/pldotnet_main.c:495-525]`. The delegate
  signatures are C function-pointer typedefs (`compile_user_fn`, `run_user_fn`,
  `run_user_tg_fn`, …) `[verified-by-code: src/pldotnet_hostfxr.h:78-89,90-101,
  103-111]`. There is no JNI-style env handle and no message pump — it is raw
  native↔managed calls across the P/Invoke boundary.

- **No GUCs; no `shared_preload_libraries` requirement.** The module exposes no
  `DefineCustom*Variable` calls; engine tunables (verbose level, save-source,
  paths) are C# static fields `[verified-by-code: dotnet_src/Engine.cs:68-82]`.
  Loading happens at `CREATE EXTENSION`/first use through the normal fmgr path.

Cross-ref [[fmgr-and-spi]], [[error-handling]], [[memory-contexts]],
[[extension-development]].

## Where it diverges from core idioms

### 1. A whole CoreCLR embedded in the backend, booted eagerly at `_PG_init`, one runtime per backend

The defining divergence. The CLR is brought up inside the backend via hostfxr and
kept for the backend's life. Two things make pldotnet's posture distinct from its
siblings. First, **eager init**: the runtime + delegate table are built during
`_PG_init` `[verified-by-code: src/pldotnet.c:42-52]`, so every backend that loads
the module pays CLR-startup cost up front — contrast [[pljava]], whose multi-stage
sequencer defers `JNI_CreateJavaVM` until first PL/Java use, and [[plv8]], which
creates a V8 isolate lazily per user. Second, **runtime granularity is
per-backend, not per-user**: there is one process-wide CLR and one global
`procedures` hash table keyed by function OID
`[verified-by-code: src/pldotnet_main.c:48,1245,1292-1295]`, with no `GetUserId()`
partitioning of compiled code (contrast [[plv8]]'s per-`user_id` `ContextVector`).
Under PG's one-process-per-backend fork model each forked backend gets its own
CLR — tolerable, but it means no in-session "restart the runtime" hook: `_PG_fini`
explicitly leaves runtime teardown as a `TODO`
`[verified-by-code: src/pldotnet.c:61-66]`. Cross-ref
[[bgworker-and-extensions]].

### 2. Datum marshalling by *attribute decomposition* into Npgsql/.NET types, not a per-type C vtable

Where [[pljava]] dispatches Datum↔jobject through a per-type C `TypeClass`
vtable, pldotnet decomposes each Datum into primitive C fields via a wide family
of exported `pldotnet_GetDatum*Attributes` functions —
`pldotnet_GetDatumPointAttributes(datum, &x, &y)`,
`…BoxAttributes`, `…TextAttributes(datum, &len, …)`,
`…TimestampAttributes`, `…InetAttributes`, `…MoneyAttributes`, etc.
`[verified-by-code: src/pldotnet_conversions.h:89-376]` — and the C# side
reassembles them into Npgsql/.NET values (`README.md:10` claims NpgsqlSPI
compatibility) `[from-README: README.md:10]`. The reverse direction collects
results into a `pldotnet_Result` buffer (`RESIZE_RESULT` / `pldotnet_CreateResult`)
`[verified-by-code: src/pldotnet_main.c:71-74,371,406]`. Managed↔native object
identity is bridged with GC handles: a `BuildDatumList`/`AddDatumToList` pair
builds lists on the managed heap and `FreeGenericGCHandle(IntPtr)` releases pinned
handles back from C `[verified-by-code: src/pldotnet_hostfxr.h:13-31;
src/pldotnet_main.c:511-520]`. Per-type C# handlers live under
`dotnet_src/TypeHandlers/` (IntegerHandler, DateTimeHandler, GeometricHandler,
RangeHandler, RecordHandler, …) `[verified-by-code: tree listing]`. Cross-ref
[[fmgr-and-spi]].

### 3. User code compiled with Roslyn in-memory — or shelled out to `dotnet build` — into a per-function collectible AssemblyLoadContext

User C# is compiled with **Roslyn** (`CSharpCompilation.Create`, emitting to a
`MemoryStream`) `[verified-by-code: dotnet_src/Engine.cs:132-137,196-209,301-302]`.
F# is compiled either via F# Compiler Services or, by default, **externally via
`dotnet build`** — `CompileFSharpWithFCS = false`
`[verified-by-code: dotnet_src/Engine.cs:74]` and the comment "the external build
is the default for F# because of typing and linkage issues with FCS-generated
code" `[from-comment: dotnet_src/Engine.cs:67-68]`. That external path literally
spawns `/usr/bin/dotnet build {projectPath} --configuration Release` via
`ProcessStartInfo`/`Process` `[verified-by-code: dotnet_src/DotNetProjectBuilder.cs:
219-247]` — a child process forked from inside a backend, per first compile.
Each function's emitted assembly is loaded into its own **collectible**
`AssemblyLoadContext` (`new($"UserFunction_{functionId}", true)`)
`[verified-by-code: dotnet_src/Engine.cs:440-444]`, cached in
`FuncBuiltCodeDict`/`TrigBuiltCodeDict`
`[verified-by-code: dotnet_src/Engine.cs:82-83]`, and recompilation `.Unload()`s
the old ALC first `[verified-by-code: dotnet_src/Engine.cs:404-421]`. pldotnet
also generates a wrapper "UserHandler" around the user's snippet to marshal
in/out `[from-comment: dotnet_src/Engine.cs:51-63 (CompileUserFunction comment)]`,
generated by `CodeGenerator.cs` (1569 lines) `[verified-by-code: tree listing]`.
This is heavier than [[plv8]] (V8 just compiles a JS string) and unusual among PLs
in that it can invoke a full MSBuild toolchain at runtime.

### 4. The exception bridge is *one-directional and lossy* — no ErrorData round-trip

This is the sharpest contrast with [[pljava]]. pljava round-trips a full PG
`ErrorData` (SQLSTATE included) through a Java `ServerException` and back, with
`FlushErrorState()` marking the handoff. pldotnet does **not**. The managed side
reports diagnostics by P/Invoking back into the `.so`'s `pldotnet_Elog`, which is
just `elog(level, "%s", message)` `[verified-by-code: src/pldotnet_main.c:532]`;
`Elog.Warning/Notice/Info/Log/Debug` map to PG elevels via integer constants
`[verified-by-code: dotnet_src/Common/Elog.cs:15-50,81-82]`. Crucially
`Elog.Error` does **not** raise a PG ERROR directly — it just `throw new
Exception(message)` on the managed side
`[verified-by-code: dotnet_src/Common/Elog.cs:55-58]`. Managed exceptions are
caught broadly inside the Engine (`catch (Exception e) { Elog.Warning($"{e…}") }`)
`[verified-by-code: dotnet_src/Engine.cs:269-275,369-395,425-435]` and the failure
surfaces to C only as a non-`RETURN_NORMAL` integer return code, which the C
handler turns into a generic `elog(ERROR, "Unknown error(return=%d): PL.NET
function \"%s\"")` `[verified-by-code: src/pldotnet_main.c:1014-1021]`. So the
.NET exception type, stack, and any PG SQLSTATE are flattened to a warning string
plus a code — there is no structured error object crossing the seam, and (unlike
[[pjava]]/[[plv8]]/[[pgrx]]) no symmetric longjmp↔managed-unwind firewall guarding
managed frames from PG's `siglongjmp`. The seam is held together by the
assumption that the managed engine catches its own exceptions before returning.

### 5. SPI wrapped per-call in PG_TRY, errors captured to a passed-out ErrorData

SPI access from .NET goes through C shims (`pldotnet_SPIExecute`,
`pldotnet_SPIExecutePlan`, `pldotnet_SPIPrepare`, `pldotnet_SPICommit`,
`pldotnet_SPIRollback`), each bracketing the SPI call in `PG_TRY`/`PG_CATCH`,
running it inside a freshly-created `AllocSetContext` that is reset on both paths,
and on error doing `*errorData = CopyErrorData(); FlushErrorState();` then
returning the captured `ErrorData *` to the caller
`[verified-by-code: src/pldotnet_spi.c:71-97,99-127,129-146,148-165,205-224]`.
This is a sane longjmp containment at the SPI boundary specifically — but note it
demotes the caught PG error to `elog(WARNING, "Exception: …")` plus a returned
struct, rather than re-raising, leaving re-raise policy to the managed side. The
result-row plumbing reads tuples directly via `heap_getattr`
`[verified-by-code: src/pldotnet_spi.c:193-203]`. Cross-ref [[fmgr-and-spi]],
[[error-handling]] (PG_TRY/PG_CATCH, CopyErrorData/FlushErrorState).

### 6. Allocation straddles two heaps; long-lived C state parked in TopMemoryContext

Compiled-function metadata lives outside any per-query context: `pldotnet_TopAlloc`
switches to `TopMemoryContext`, `palloc`s, zeroes, and switches back, and the
function-decl cache entries are allocated this way and stored in the GLib
`procedures` hash for the backend's life
`[verified-by-code: src/pldotnet_main.c:1216-1241,1243-1246]`. Meanwhile the
entire managed object graph (compiled assemblies, Npgsql values, user state) lives
on the **CLR GC heap, entirely outside PG MemoryContexts** — so the
OOM-throws-ereport contract ([[memory-contexts]]) does not cover it, and unlike
[[plv8]] there is no per-function CLR memory cap wired in
`[inferred: no DefineCustom* GUC, no ResourceConstraints analogue found]`. Note
also the dependency on **GLib** (`g_hash_table_new_full`, `GUINT_TO_POINTER`)
`[verified-by-code: src/pldotnet.c:54-55,63; src/pldotnet_main.c:1245,1292-1295]`
— a non-PG allocator/container library linked into the backend, itself a small
divergence from the PG-native `HTAB`/`dynahash` idiom.

## Notable design decisions (with cites)

- **`DO` blocks unload their assembly immediately.** Both inline handlers call
  `unload_assemblies(fcinfo->flinfo->fn_oid)` right after running, so a one-shot
  `DO` block's collectible ALC is torn down at once
  `[verified-by-code: src/pldotnet_main.c:448-452,462-466]`.
- **hostfxr discovery shells out to `dpkg`.** When `nethost`'s `get_hostfxr_path`
  fails, the fallback `popen`s a `dpkg -L dotnet-hostfxr-6.0` pipeline
  `[verified-by-code: src/pldotnet_hostfxr.c:76-100]` — couples the extension to
  Debian packaging and to .NET 6 specifically.
- **Source code persisted to `/tmp` by default.** `SaveSourceCode = true` and
  `PathToSaveSourceCode = "/tmp/PlDotNET/GeneratedCodes"`,
  `PathToTemporaryFiles = "/tmp/PlDotNET/"`
  `[verified-by-code: dotnet_src/Engine.cs:72,78-80]`; `CompileUserFunction`
  enforces `0700` on those dirs via `CheckDirectoriesAccess()`
  `[verified-by-code: dotnet_src/Engine.cs:33-41 (in CompileUserFunction)]`.
- **Sandboxing: effectively none.** Trusted/untrusted is not modeled — there is
  no opcode mask (plperl), no Safe interpreter (pltcl), no
  binding-absence sandbox ([[plv8]]), and no SecurityManager policy ([[pljava]]).
  User C#/F# runs with the full BCL (filesystem, process spawn — pldotnet itself
  spawns `dotnet build`) `[inferred: no policy/permission layer found in
  Engine.cs or pldotnet_main.c; full BCL available to user code]`. Both languages
  are de-facto untrusted.
- **`plfsharp` UserHandlers are C#.** Even for F# functions the marshalling
  wrapper is generated in C#; the F# UserHandler path is "mostly disabled"
  `[from-comment: dotnet_src/Engine.cs:55-57]`.
- **A copy-paste bug in the SPI plan path.** `pldotnet_SPIExecutePlan` ends with
  `return SPI_tuptable;` twice (the second is dead code)
  `[verified-by-code: src/pldotnet_spi.c:125-126]` — cosmetic, harmless, but a
  marker of beta-grade polish.

## Links into corpus

- [[fmgr-and-spi]] — the PL handler trio (call/inline/validator),
  `PG_FUNCTION_INFO_V1`, SPI wrapping (§1, §2, §5).
- [[error-handling]] — PG_TRY/PG_CATCH, CopyErrorData/FlushErrorState, the
  one-directional bridge gap (§4, §5).
- [[memory-contexts]] — TopMemoryContext parking + the second (CLR GC) heap
  outside contexts (§6).
- [[extension-development]] — `.control`, install SQL, `_PG_init`, `CREATE
  LANGUAGE` registration.
- Sibling ideologies: [[pljava]] (JVM/JNI — the closest sibling; richer,
  bidirectional error bridge), [[plv8]] (V8 isolate — per-user runtime + memory
  cap), [[plsh]] (shell PL — the trivial-handler contrast), [[pgrx]] (Rust FFI
  boundary — `pg_guard_ffi_boundary`, the symmetric firewall pldotnet lacks).

> Corpus gap: there is no PL-handler *idiom* doc generalizing the
> call/inline/validator trio + foreign-runtime hosting pattern across
> plperl/plpython/pltcl/[[pljava]]/[[plv8]]/pldotnet. Three CLR/JVM/V8 siblings
> now exist as ideology notes but the shared structure (managed runtime in
> backend, longjmp containment at the SPI seam, two heaps) is undocumented as a
> reusable idiom — candidate: `idioms/foreign-runtime-pl.md` or
> `idioms/pl-handler-trio.md`.
> Corpus gap: no idiom doc on the managed/native FFI error-bridge spectrum
> (lossy integer-code return ↔ structured ErrorData round-trip ↔ symmetric
> longjmp/panic firewall) that [[pljava]], [[plv8]], [[pgrx]], and pldotnet each
> sit at different points on.

## Sources

All fetched 2026-06-27.

- `https://api.github.com/repos/Brick-Abode/pldotnet/git/trees/master?recursive=1`
  — HTTP 200 (tree listing, used for file discovery).
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/pldotnet.control`
  — HTTP 200, 6 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/pldotnet--0.9.sql`
  — HTTP 200, 37 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/src/pldotnet.c`
  — HTTP 200, 68 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/src/pldotnet_hostfxr.c`
  — HTTP 200, 174 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/src/pldotnet_hostfxr.h`
  — HTTP 200, 163 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/src/pldotnet_main.c`
  — HTTP 200, 1396 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/src/pldotnet_spi.c`
  — HTTP 200, 228 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/src/pldotnet_conversions.h`
  — HTTP 200, 31599 bytes (~860 lines).
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/dotnet_src/Engine.cs`
  — HTTP 200, 925 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/dotnet_src/DotNetProjectBuilder.cs`
  — HTTP 200, 286 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/dotnet_src/CodeGenerator.cs`
  — HTTP 200, 1569 lines (skimmed for UserHandler generation; cited via tree only).
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/dotnet_src/Common/Elog.cs`
  — HTTP 200, 83 lines.
- `https://raw.githubusercontent.com/Brick-Abode/pldotnet/master/README.md`
  — HTTP 200, 175 lines.

Skimmed but not fetched (identified via tree listing, not opened in depth):
`dotnet_src/TypeHandlers/*.cs` (per-type marshalling handlers — Integer, Float,
DateTime, Geometric, Range, Record, String, Uuid, Network, Json, Money, Bytea,
BitString, Bool, Array, Generic, Handler), `dotnet_src/Common/{OID,Enums,
NpgsqlHelper,TriggerData,ArrayManipulation}.cs`, `src/pldotnet_conversions.c`,
`src/pldotnet_main.h`, `src/pldotnet_spi.h`, `Makefile`, `tests/**`.
