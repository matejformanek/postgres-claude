---
source_url: https://www.postgresql.org/docs/current/jit-extensibility.html
chapter: "32.4 Extensibility"
fetched_at: 2026-07-09
anchor_sha: d92e98340fcb
---

# JIT extensibility — pluggable providers + bitcode inlining — §32.4

Two extension surfaces: (1) the **pluggable JIT provider** — the LLVM backend
is loaded through a swappable interface, chosen by `jit_provider`; and (2)
**bitcode inlining for extensions** — any `C`/`internal` function whose LLVM
bitcode is installed under `$pkglibdir/bitcode/` can be inlined into JIT'd
expressions, and PGXS builds/installs that bitcode automatically.

## Non-obvious claims

- **The JIT provider is a dynamically-loaded shared library, not a compiled-in
  choice.** "The interface to the JIT provider is pluggable and the provider
  can be changed without recompiling … The active provider is chosen via the
  setting `jit_provider`." [from-docs §32.4] The load is by *name*: the server
  builds the path `<pkglibdir>/<jit_provider><DLSUFFIX>` and `dlopen`s it.
  [verified-by-code — `snprintf(path, MAXPGPATH, "%s/%s%s", pkglib_path,
  jit_provider, DLSUFFIX)` at `source/src/backend/jit/jit.c:91`]
- **The provider must export `_PG_jit_provider_init`.** After loading, the
  core calls `load_external_function(path, "_PG_jit_provider_init", …)` and
  invokes it to populate a callbacks struct. [verified-by-code
  `source/src/backend/jit/jit.c:112`; signature
  `extern PGDLLEXPORT void _PG_jit_provider_init(JitProviderCallbacks *cb)` at
  `source/src/include/jit/jit.h:67`]
- **`JitProviderCallbacks` has exactly three function pointers, in this
  order**: `reset_after_error`, `release_context`, `compile_expr`.
  [verified-by-code `source/src/include/jit/jit.h:74-79`]
  - `compile_expr` (`JitProviderCompileExprCB`) takes an `ExprState *` and
    returns `bool` — it is the core operation, dispatched from
    `jit_compile_expr` → `provider.compile_expr(state)`. [verified-by-code
    `jit.h:72`, `jit.c:152,175-176`]
  - `release_context` frees a `JitContext` [`jit.h:70`, `jit.c:141`];
    `reset_after_error` recovers provider state after a longjmp
    [`jit.h:69`, `jit.c:131`].
- **`provider_init()` is lazy and gated on `jit_enabled`** — the provider
  library is not loaded until the first query actually needs JIT *and*
  `jit_enabled` is true. [verified-by-code `source/src/backend/jit/jit.c:68,74`
  — `if (!jit_enabled)` early-out]. So a `--with-llvm` build with `jit=off`
  never pays the LLVM `dlopen` cost.
- **`JitContext` is deliberately provider-agnostic**: it carries only
  `int flags` (the `PGJIT_*` bits) and a `JitInstrumentation instr`; all
  LLVM-specific state hangs off the provider's own subtype (e.g.
  `LLVMJitContext` extends it). [verified-by-code
  `source/src/include/jit/jit.h:57-63`]
- **Inlining works by shipping LLVM bitcode for inlinable functions.** "JIT
  implementation can inline the bodies of functions of types `C` and
  `internal`, as well as operators based on such functions." The bitcode is
  discovered at `$pkglibdir/bitcode/$extension/` (per-object `.bc` files) with
  a summary index `$pkglibdir/bitcode/$extension.index.bc`; core PG's own
  bitcode lives at `$pkglibdir/bitcode/postgres`. [from-docs §32.4;
  path construction `%s/bitcode/%s` and `.index.bc` suffix verified at
  `source/src/backend/jit/llvm/llvmjit_inline.cpp:492,811-812`]
- **PGXS automates it.** Building an extension with PGXS against an
  LLVM-enabled PostgreSQL builds and installs the bitcode files automatically
  — the extension author writes no extra rules to become inlinable.
  [from-docs §32.4]
- **The pluggability is partly aspirational**: "currently, the build process
  only provides inlining support data for LLVM" — a hypothetical non-LLVM
  provider would get codegen but no bitcode-inlining infrastructure without
  new build support. [from-docs §32.4]

## Links into corpus

- Why inlining matters (fmgr dispatch overhead):
  [[knowledge/docs-distilled/jit-reason.md]] (§32.1).
- Provider default + `PGC_POSTMASTER` context:
  [[knowledge/docs-distilled/jit-configuration.md]] (§32.3).
- The `ExprState` that `compile_expr` consumes:
  [[knowledge/files/src/backend/executor/execExpr.c.md]] +
  [[knowledge/files/src/backend/executor/execExprInterp.c.md]].
- Extension packaging / PGXS: [[knowledge/docs-distilled/extend-pgxs.md]] +
  [[knowledge/docs-distilled/extend-extensions.md]].
- Dynamic-load mechanism reused here (`load_external_function`):
  [[knowledge/docs-distilled/xfunc-c.md]].

## Caveats / verification

- All struct/symbol/path claims are `[verified-by-code]` at anchor
  `d92e98340fcb`: `JitProviderCallbacks` + `_PG_jit_provider_init` +
  `JitContext` + `PGJIT_*` in `source/src/include/jit/jit.h:19-24,57-79`;
  provider load + lazy `provider_init` + `compile_expr` dispatch in
  `source/src/backend/jit/jit.c:68,91,112,131,141,152,175-176`; the
  `$pkglibdir/bitcode/…` / `.index.bc` layout in
  `source/src/backend/jit/llvm/llvmjit_inline.cpp:492,811-812`. The
  `C`/`internal`-only inlining rule, PGXS automation, and the
  "LLVM-only build support" limitation are `[from-docs §32.4]`.
