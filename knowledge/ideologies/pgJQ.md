# pgJQ — ideology / divergence-from-core notes

> Extension: `Florents-Tselai/pgJQ` @ `main` (control reports
> `default_version = '0.1.0'`, `relocatable = true`,
> `module_pathname = '$libdir/pgjq'`)
> `[verified-by-code: pgjq.control:2-4]`. 204★, C. One durable "how this
> diverges from core PG design" doc, produced by the
> `pg-extension-anthropologist` cloud routine. Files fetched 2026-07-14
> (`pgjq.c`, `pgjq.control`, `sql/pgjq--0.1.0.sql`, `Makefile`, `README.md`,
> `test/sql/basic.sql`; see Sources). All `file:line` cites point into the
> pgJQ tree, **NOT** into PG `source/`. Confidence tags:
> `[verified-by-code]` `[from-README]` `[from-comment]` `[inferred]`
> `[unverified]`.
> **Cluster.** This is the founding member of an **"embed a foreign query
> DSL + its bytecode VM in the backend"** axis — a sibling to the
> embedded-PL cluster ([[plv8]] V8, [[pljava]] JVM, [[pldotnet]] CLR,
> [[pglite-fusion]] SQLite) but narrower: pgJQ embeds a *data-query DSL over
> jsonb* (jq's `jv`/`jq_state` interpreter), not a general programming
> language, and — unlike those PLs, which cache compiled functions across
> calls — it recompiles the program every call and caches no VM state. It is
> also a member of the **"embed a foreign jsonb/vendored-C processor"**
> cluster: read against [[pg_jsonschema]] (validates jsonb via a vendored
> Rust crate — the other "embed a foreign jsonb processor"),
> [[pg_roaringbitmap]] and [[pguri]] (vendored-C-lib custom types with an
> allocator/error boundary), and [[zson]] (jsonb-adjacent type). The
> sharpest contrast is with pg_roaringbitmap: CRoaring there is pulled *into*
> the MemoryContext system via a global allocator hook, whereas pgJQ leaves
> libjq's own `jv` allocator entirely outside PG memory management and —
> uniquely — leaks libjq's CLI-era `stdout`/`stderr` side effects into a SQL
> function.

---

## Domain & purpose

pgJQ embeds the standard **jq** compiler (the `jqlang/jq` DSL) inside
PostgreSQL so that jq programs can be run against `jsonb` values from SQL.
It adds one custom type, `jqprog` (a jq program), and one workhorse
function `jq(jsonb, jqprog, jsonb DEFAULT '{}') RETURNS jsonb`, plus an
`@@` operator as sugar `[verified-by-code: sql/pgjq--0.1.0.sql:1-46;
from-README: README.md:11-15]`. The README's explicit design stance is
that pgJQ does **not** re-implement jq in PG — it links the real libjq and
delegates parsing + execution to it `[from-README: README.md:201-205]`.

The interesting anthropology is the **library boundary**. libjq was
written first and foremost as a command-line tool; its execution core
(`jq_process`) writes results to `FILE *stdout` and errors to `stderr`.
pgJQ does not have a clean library API to call, so the author *copied and
reverse-engineered* the relevant slice of `jq/src/main.c` into the
extension and adapted it to capture one result via an out-parameter — while
leaving the original `fwrite`/`fprintf`-to-stdout side effects in place
`[verified-by-code: pgjq.c:18-29 (banner comment), 72-160 (jq_process)]`.
Almost every divergence below flows from "the embedded engine is a CLI tool
wearing a thin library disguise."

---

## How it hooks into PG

- **`CREATE TYPE jqprog`** as a variable-length type
  (`INTERNALLENGTH = -1`) with only `INPUT = jqprog_in` /
  `OUTPUT = jqprog_out` — no recv/send, no analyze, no typmod
  `[verified-by-code: sql/pgjq--0.1.0.sql:1, 17-22]`. The type is forward
  declared (`CREATE TYPE jqprog;`) so the I/O functions can reference it,
  then fully defined — the standard shell-type two-step
  `[verified-by-code: sql/pgjq--0.1.0.sql:1-22]`.
- **`jqprog` is literally `text`.** In C: `typedef text jqprog;`
  `[verified-by-code: pgjq.c:167]`. `jqprog_in` just does
  `cstring_to_text(s)` and `jqprog_out` does `TextDatumGetCString`
  `[verified-by-code: pgjq.c:178-196]`. No compilation or validation
  happens at input time (see divergence #2).
- **Casts.** `jqprog AS text` and `text AS jqprog` both
  `WITH INOUT AS ASSIGNMENT` `[verified-by-code: sql/pgjq--0.1.0.sql:25-26]`
  — a round-trip through the I/O functions, since the storage *is* text.
- **The `jq` function** is `LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE`,
  three args (`jsonb` input, `jqprog` program, `jsonb` args, default `'{}'`)
  `[verified-by-code: sql/pgjq--0.1.0.sql:28-32]`. Its C body
  `[verified-by-code: pgjq.c:300-476]` does jsonb→cstring→jq→jsonb.
- **The `@@` operator** `jsonb @@ jqprog → jsonb` is backed by a *SQL*
  wrapper `__op_jq_jsonb_jqprog` that just calls `jq($1, $2)` (dropping the
  third args parameter) `[verified-by-code: sql/pgjq--0.1.0.sql:34-46]`.
  Note the token **collides in spelling with core's `jsonb @@ jsonpath →
  boolean`** jsonpath-match operator; pgJQ overloads `@@` on a different
  right-arg type (`jqprog`) and result (`jsonb`), which is exactly why the
  README insists on explicit `::jqprog` casts `[from-README:
  README.md:52,167-172]`. See [[jsonpath-and-jsonb]].
- **Load model.** Plain `PG_MODULE_MAGIC`, ordinary `CREATE EXTENSION`
  (no `shared_preload_libraries`, no `_PG_init` at all)
  `[verified-by-code: pgjq.c:13; grep of pgjq.c finds no _PG_init]`.
- **Build.** PGXS `MODULE_big`, linking `-ljq` against a libjq built into
  `$(JQ_PREFIX)` (default `./jq/build`) — libjq is an *external* dependency
  pointed at by include/lib flags, not amalgamated into the tree
  `[verified-by-code: Makefile:6-26]`. See [[catalog-conventions]],
  [[fmgr]].

---

## Where it diverges from core idioms

### 1. The execution core writes to the process's real `stdout`/`stderr` — CLI side effects leak into a SQL function

This is the central divergence and the lens for the rest. `jq_process` is
a near-verbatim copy of jq's CLI driver, and it still does what a CLI does:
on each produced value it calls `jq_priv_fwrite(... stdout ...)` (which
ultimately `fwrite`s to `stdout`) and appends a newline to `stdout`
`[verified-by-code: pgjq.c:60-113]`; on a jq runtime exception it
`fprintf(stderr, "jq: BOOOM error (at %s): %s\n", ...)`
`[verified-by-code: pgjq.c:140-153]`. The banner comment is explicit that
this slice was "copied & reverse-engineered from jq/src/main.c" and warns
against deleting the unused CLI machinery `[from-comment: pgjq.c:18-29]`.
The actual SQL return value is smuggled out through a single
`*out_result = jv_copy(result)` out-parameter on the non-raw branch
`[verified-by-code: pgjq.c:103]`, so the function returns one jsonb while
*also* emitting every jq result to the backend's stdout and errors to its
stderr. Core PG functions never write to `stdout`/`stderr` directly — user
feedback goes through `ereport`/`elog` so it lands in the log with the
right elevel and SQLSTATE, and result data goes through the tuple store,
never a file descriptor `[inferred from PG error-handling contract; see
[[error-handling]]]`. Writing to a forked backend's `stdout` is at best
invisible and at worst corrupts protocol/log streams. `[verified-by-code]`
for the writes; the *consequence* (where those bytes go in a forked
backend) is `[inferred]`.

### 2. `jqprog` does no validation at input time — it is `text` with a different name

A jq program is a compiled artifact, but `jqprog_in` stores the raw string
unchanged and the source even flags the gap: `/* TODO: validate here =
compile the expression */` `[verified-by-code: pgjq.c:183-186]`. So
`'gsdfgf'::jqprog` and `1345::jqprog` both succeed at cast time even though
neither is a valid jq program `[verified-by-code: test/sql/basic.sql:4-5]`;
the error only surfaces later inside `jq()` when `jq_compile_args` fails
`[verified-by-code: pgjq.c:445-449]`. This inverts the core type-I/O
contract, where `*_in` is the validation boundary: a malformed literal for
a core type (`'x'::int`, `'{'::jsonb`) is rejected at input. Because the
on-disk form is identical to `text`, the type buys no storage or semantic
benefit over `text` — it exists purely to give the `@@` operator and the
`jq()` signature a distinct argument type to dispatch on `[inferred from
the typedef text jqprog + the operator/function signatures]`.

### 3. libjq's `jv` allocator lives entirely outside the MemoryContext system

Unlike the sibling vendored-lib type [[pg_roaringbitmap]], which redirects
CRoaring's entire allocator into PG via `roaring_init_memory_hook`, pgJQ
installs **no** allocator hook for libjq. Every `jv_object()`, `jv_parse`,
`jq_init`, `jq_compile_args`, etc. uses libjq's own internal `malloc`-based
reference-counted `jv` allocator `[verified-by-code: pgjq.c:342-475 —
jv_*/jq_* calls with no memory hook anywhere; grep finds no
init_memory_hook]`. The code instead tries to balance this by hand with
explicit `jv_free`/`jq_teardown`/`jq_util_input_free` at the end of `jq()`
`[verified-by-code: pgjq.c:465-473]`. The hazard is the same one [[pguri]]
hits: any `ereport(ERROR)` between allocation and the manual free path —
e.g. the `ERRCODE_FEATURE_NOT_SUPPORTED` thrown mid-argument-loop
`[verified-by-code: pgjq.c:409-414]`, or the compile-failure `ereport`
`[verified-by-code: pgjq.c:447-449]` (the *expected* error path for bad
user input) — `longjmp`s past the cleanup block, leaking the in-flight
`jv` graph and the whole `jq_state` VM (libjq `malloc`, not palloc, so PG
context teardown can't reclaim it). The author flags awareness of leaks
with two `/* FIXME: ... memory leak ... */` comments in the jv→jsonb
converter `[from-comment: pgjq.c:223, 242-243]`. See [[memory-contexts]].

### 4. The jsonb is round-tripped to a C string and fed to jq as a `fmemopen` FILE stream

jq is stream-oriented, so pgJQ bridges PG's in-memory `jsonb` to a stdio
stream: it serializes the input jsonb to a `char *` with `JsonbToCString`
`[verified-by-code: pgjq.c:315]`, then `fmemopen`s that buffer into a
`FILE *file_json` to "make the input json char* act like a stream"
`[verified-by-code: pgjq.c:327-332; from-comment]`. Notably the parse the
function actually runs is `jv_parse(json_string)` on the string directly
`[verified-by-code: pgjq.c:459]` — the `fmemopen`'d FILE is opened and
`fclose`d `[verified-by-code: pgjq.c:473]` but the jq input-state parser is
initialized separately `[verified-by-code: pgjq.c:452-457]`, so the stream
plumbing is partly vestigial CLI scaffolding rather than the live data
path. Going jsonb → text → libjq's own JSON parser means the value is
parsed **twice** (once by PG to build the input `jsonb`, once by libjq) and
loses jsonb's binary-decoded numerics: numbers come back through
`jv_number_value` as IEEE `double` and are reconstituted via
`float8_numeric` `[verified-by-code: pgjq.c:202-206]`, and `--argjson`
numeric arguments go the same lossy way via `numeric_float8`
`[verified-by-code: pgjq.c:398-399]` — so integer precision beyond 2^53 and
exact decimal scale are not preserved. Core jsonb operators (`->`, `#>`,
jsonpath) walk the binary `Jsonb` directly and never serialize-then-reparse
`[see [[jsonpath-and-jsonb]]]`. `[verified-by-code]` for the double-parse;
the precision-loss consequence is `[inferred]` from the `double` round-trip.

### 5. Errors map to `ereport` inconsistently — some paths `ereport`, the hot path prints to stderr

pgJQ's error story is split. Argument-type rejection, compile failure, and
jv-kind-not-representable all go through proper `ereport(ERROR, ...)` with
real SQLSTATEs (`ERRCODE_FEATURE_NOT_SUPPORTED`, `ERRCODE_ASSERT_FAILURE`)
`[verified-by-code: pgjq.c:283-294, 409-414, 447-449]`. But the
*runtime-exception* path inside `jq_process` — a jq program that throws at
evaluation time — only `fprintf`s to stderr and returns a non-zero status
code that the caller ignores `[verified-by-code: pgjq.c:140-157, 460-463]`;
the one place a jq message becomes an `ereport` is the `halt_error`
non-string branch `[verified-by-code: pgjq.c:132-136]`. The jq
input-parser error callback is even stubbed out as `NULL` with `// XXX add
err_cb` `[from-comment: pgjq.c:452]`. So whether a jq error reaches the SQL
client as an `ERROR` or silently vanishes to the backend's stderr depends
on which jq internal path produced it. Core code routes *all* user-visible
failure through `ereport` with a SQLSTATE; pgJQ's copied-from-CLI core
breaks that uniformity. See [[error-handling]].

### 6. No GUCs, no opclass, no index support — and the `@@` operator drops a parameter

There is no `_PG_init` and therefore **no GUC surface**
`[verified-by-code: grep of pgjq.c finds neither _PG_init nor
DefineCustom*Variable]` — contrast pg_roaringbitmap's output-format GUC.
The install SQL defines **no `CREATE OPERATOR CLASS`** (no GIN/GiST/btree
support, no commutator/negator, no `RESTRICT`/`JOIN` selectivity)
`[verified-by-code: grep of sql/pgjq--0.1.0.sql finds no OPERATOR CLASS /
GIN / GIST / COMMUTATOR]`. The `@@` operator is also *lossy*: its backing
SQL function `__op_jq_jsonb_jqprog` calls `jq($1, $2)` with only two
arguments, so `@@` can never pass jq `$var` arguments — the third `jsonb`
parameter of `jq()` is unreachable through the operator
`[verified-by-code: sql/pgjq--0.1.0.sql:34-46]`. The README itself warns
operator use is an "obfuscated labyrinth" of overloaded `@@`/`-`/`@>`
needing explicit casts and parentheses `[from-README: README.md:149-172]`.
See [[guc-variables]] and [[catalog-conventions]].

### 7. The `slurp`-vs-`null` mode is decided by a heuristic the author admits is unprincipled

How jq consumes the input (`SLURP` an array vs `PROVIDE_NULL`) is chosen by
inspecting the top-level jsonb kind: arrays get `SLURP`, everything else
gets `PROVIDE_NULL` `[verified-by-code: pgjq.c:435-438]`. The surrounding
comment is candid: "this-combination-looks-like-it-works / Need to make
this more predictable" `[from-comment: pgjq.c:431-434]`. The README's
"Known issues" confirm the consequence: piped filters like `.[] | .name`
are "buggy and unpredictable" `[from-README: README.md:222]`. This is the
opposite of the core idiom where a function's evaluation semantics are
fully specified by its declared signature, not inferred from a runtime
shape sniff. `[verified-by-code]` for the heuristic; `[from-comment]` +
`[from-README]` for it being known-fragile.

---

## Notable design decisions (with cites)

- **Embed, don't reimplement.** The explicit philosophy is to link the real
  libjq and feed it jsonb, accepting that jq is "a 20-80 tool" and pgJQ is
  "TDDed against those 20%" `[from-README: README.md:201-218]` — a
  deliberately partial port, not a faithful one.
- **Recompile per call, cache nothing.** Each `jq()` invocation does a fresh
  `jq_init()` → `jq_compile_args()` → run → `jq_teardown()`
  `[verified-by-code: pgjq.c:424,445,469]`, with **no** `fn_extra` caching of
  the compiled `jq_state` across rows. A query applying one constant `jqprog`
  to a million rows recompiles a million times. This is the sharpest contrast
  with the embedded-PL cluster ([[plv8]], [[pljava]]), which cache compiled
  functions, and with the core [[fmgr]] `fn_extra` convention. `[inferred]`
  for the perf cost.
- **`jqprog` as a pure dispatch tag.** Making the type `typedef text`
  `[verified-by-code: pgjq.c:167]` with INOUT casts to/from `text`
  `[verified-by-code: sql/pgjq--0.1.0.sql:25-26]` means a jq program is
  storable, dumpable, and comparable exactly like `text`; the type's only
  job is to give `jq()` and `@@` a distinct argument type.
- **`IMMUTABLE STRICT PARALLEL SAFE` marking** on `jq()`
  `[verified-by-code: sql/pgjq--0.1.0.sql:30-32]` — reasonable for a pure
  transform (output is a function of the inputs; no GUC, no session state),
  but in tension with divergence #1 (a function that writes to `stdout` is
  arguably not side-effect-free). `[inferred]` tension.
- **jv→jsonb is a hand-written recursive walker** (`JvObject_to_JsonbValue`
  and friends) building a `Jsonb` via the `pushJsonbValue` /
  `JsonbParseState` builder API, with per-kind branches for null/bool/
  number/string/array/object `[verified-by-code: pgjq.c:198-298]`. Numbers
  always go through `float8_numeric` (lossy for big ints, see #4). See
  [[jsonpath-and-jsonb]].
- **`--argjson` via a jsonb third arg**, iterated with `JsonbIteratorNext`
  and injected as jq `$var`s through `jv_object_set` + `jq_compile_args`
  `[verified-by-code: pgjq.c:366-421, 445]`, limited to numeric/string/bool
  `[verified-by-code: pgjq.c:409-414]`, matching the README's stated
  limitation `[from-README: README.md:221]`.
- **Macro set is partly broken / dead.** `PG_GETARG_JQPROG_P` expands to
  `DatumGetJqP(...)` and `PG_GETARG_JQPROG_PP` to `DatumGetJqPP(...)` —
  but the defined macros are `DatumGetJqProgP` / `DatumGetJqProgPP`, so the
  GETARG macros reference undefined symbols and would not compile if used
  `[verified-by-code: pgjq.c:168-173]`. They are never invoked (the code
  uses `PG_GETARG_JSONB_P` / `PG_GETARG_TEXT_PP` / `PG_GETARG_CSTRING`
  directly), so this is dead, latent-broken scaffolding `[verified-by-code:
  pgjq.c:180, 306, 318]`.
- **Single-result truncation.** jq is a stream that can yield *many* values
  per input; `jq()` returns a single `jsonb`. `jq_process` keeps overwriting
  `*out_result` on each iteration `[verified-by-code: pgjq.c:103]`, so only
  the **last** non-raw result survives into the return value (earlier ones
  are written to stdout and dropped). This is a fundamental impedance
  mismatch between jq's stream model and a scalar-returning SQL function
  `[inferred from the overwrite + scalar return at pgjq.c:475]`.
- **libjq is an external lib, not vendored in-tree.** The Makefile points
  `-I`/`-L` at a separately-built `./jq/build` and links `-ljq`
  `[verified-by-code: Makefile:17-23]` — contrast pg_roaringbitmap's
  amalgamated CRoaring. So the jq ABI/version is whatever the builder
  supplies, not pinned by the repo.

---

## Links into corpus

- **Embedded-DSL / foreign-VM cluster (the defining axis, siblings with
  contrast):** [[plv8]] (V8), [[pljava]] (JVM), [[pldotnet]] (CLR),
  [[pglite-fusion]] (SQLite). pgJQ embeds a *data-query DSL VM* (jq's
  `jv`/`jq_state`) rather than a general PL, and unlike those it **caches no
  compiled state across calls** (recompiles per row) and bridges errors only
  partially (#1, #5).
- [[pg_jsonschema]] — the closest jsonb sibling: another "embed a foreign
  jsonb processor" extension (validates jsonb against a JSON Schema via a
  vendored crate). **Contrast:** pg_jsonschema's engine is library-shaped and
  side-effect-free; pgJQ's engine is a CLI driver that writes to
  stdout/stderr (#1).
- [[pg_roaringbitmap]] — vendored-C-lib custom type. **Contrast on the
  allocator boundary:** roaringbitmap redirects CRoaring's *entire* allocator
  into MemoryContext via `roaring_init_memory_hook`, so library allocations
  are context-reclaimed; pgJQ installs no hook and hand-frees libjq's `jv`
  objects, leaking on the `ereport` error path (#3).
- [[pguri]] — vendored-C-lib custom base type whose library `malloc`s outside
  any context and leaks on the error path — pgJQ's `jv`-allocator situation
  (#3) is the same family.
- [[zson]] — jsonb-adjacent custom type; structural contrast on the
  store-form decision (zson compresses; pgJQ's `jqprog` is bare text, #2).
- [[jsonpath-and-jsonb]] — the jsonb-side API pgJQ leans on (`JsonbToCString`,
  `JsonbToJsonbValue`, `JsonbIteratorNext`, the `pushJsonbValue` /
  `JsonbParseState` builder, `jbvNumeric`/`jbvString`/`jbvBool`/`jbvArray`);
  and the `@@`-token collision with core's jsonpath-match operator (#4, How
  it hooks in).
- [[fmgr]] — `PG_FUNCTION_INFO_V1`, `PG_GETARG_JSONB_P` / `PG_GETARG_TEXT_PP`
  / `PG_GETARG_CSTRING`, the shell-type forward-declare + I/O-function
  pattern, the **absent** `fn_extra` caching (Notable decisions), and the
  dead/broken GETARG macros.
- [[memory-contexts]] — the absence of an allocator hook for libjq and the
  longjmp-leak hazard on the manual `jv_free` path (#3).
- [[error-handling]] — the split between `ereport`-routed errors and
  stderr-printed jq runtime exceptions (#1, #5); the stubbed err_cb; the
  stdout/stderr-in-a-backend anti-pattern.
- [[catalog-conventions]] — `CREATE TYPE` (shell type + I/O), INOUT casts,
  the SQL-wrapper operator, and the **absent** opclass / GUC surface (#6).
- [[guc-variables]] — noted by its absence: pgJQ has no `_PG_init` and no
  GUCs (#6).
- Core analogs in prose: jsonb internals and the `pushJsonbValue` /
  `JsonbParseState` builder API in `src/backend/utils/adt/jsonb*.c` (the
  jv→jsonb walker, #4), and the type-I/O validation contract in
  `src/backend/utils/adt/` (the `jqprog_in` non-validation, #2).

---

## Sources

Fetched 2026-07-14 (branch `main`), all via `raw.githubusercontent.com`
(base `https://raw.githubusercontent.com/Florents-Tselai/pgJQ/main/`).

| URL | HTTP |
|---|---|
| `.../pgjq.control` | 200 |
| `.../sql/pgjq--0.1.0.sql` | 200 |
| `.../README.md` | 200 |
| `.../pgjq.c` | 200 |
| `.../Makefile` | 200 |
| `.../test/sql/basic.sql` | 200 |
| `.../test/expected/basic.out` | 200 (fetched, not line-cited) |
| `.../LICENSE` | 200 (MIT; not read in depth) |

**Probed and absent (HTTP 404):** `pgjq.h`, `META.json`, `src/pgjq.c`,
`docs/README.md`, `pgjq--0.1.0.sql` (root), `sql/pgjq.sql`,
`test/sql/pgjq.sql`, `Makefile.am`.

**Fetch notes / substitutions:**
- The prompt's manifest hint (`src/*.c`) was a guess; the real tree is
  **flat** — the main C file is `pgjq.c` at repo root (476 lines), **not**
  under `src/`; the install SQL is `sql/pgjq--0.1.0.sql` matching
  `default_version = '0.1.0'`; the control is a plain `pgjq.control` (no
  `.control.in`). No `src/` directory and no `pgjq.h` exist.
- `pgjq.control` has a duplicate `comment =` line (line 1 `'jq in Postgres'`
  then line 5 `'Use jq in Postgres'`); the last wins in PG's parser.
  `relocatable = true` and `module_pathname = '$libdir/pgjq'`
  `[verified-by-code: pgjq.control:3-4]`.
- libjq itself is **not** in the repo tree (no `jq/` sources, no `jq.h`, no
  amalgamation) — it is an external build dependency the Makefile links via
  `-ljq` against `$(JQ_PREFIX)`. So all claims about jq *internals*
  (`jq_process` semantics beyond the copied slice, the `jv` allocator, what
  `jq_init`/`jq_compile_args`/`jq_next`/`jv_parse`/`jq_teardown` do) rest on
  the code copied into `pgjq.c` plus the in-tree banner comment
  `[from-comment: pgjq.c:18-29]`, not on a read of libjq source. Claims about
  where stdout/stderr bytes land in a forked backend, the per-call-compile
  perf cost, the VM leak on the error path, and the numeric precision loss
  are `[inferred]`.
- `test/sql/basic.sql` was read to confirm the no-validation casts
  (`'gsdfgf'::jqprog`, `1345::jqprog` at lines 4-5); `test/expected/basic.out`
  was fetched for completeness but not line-cited. No 404s among the files
  actually cited; the whole repo fetched cleanly.
