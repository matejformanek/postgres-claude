# morphingdb — libtorch deep-learning inference and a native vector type living *inside* the PG backend

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `MorphingDB/MorphingDB` @ branch `master` (63★). All `file:line` cites
> below point into that repo (**not** `source/`), since this doc characterizes
> an *external* extension's divergence from core idioms.
>
> Provenance: fetched 2026-07-03. **Only `raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>`
> returns 200** — the GitHub tree API, codeload tarballs, and github.com HTML
> all 403, so the `src/` directory could not be listed. Instead the root
> `CMakeLists.txt` (a `FILE(GLOB "./src/pgdl/*.cpp" "./src/external_process/*.cpp")`)
> was fetched to resolve the layout, and the four real translation units it
> globs were fetched by exact path. This doc is **code-backed** for the vector
> type + inference core (`interface.cpp`, `vector.h`, `model_manager.cpp/.h`)
> but has a **code gap** for `src/external_process/*` (the user-supplied
> pre/post-processing handlers), whose filenames could not be enumerated —
> every probe 404'd. Claims about that layer are `[from-README]` / `[inferred]`.
> The extension's SQL name is **`pgdl`** (the repo is "MorphingDB"; the module,
> control file, and `CREATE EXTENSION` target are all `pgdl`).

## Domain & purpose

MorphingDB is "a PostgreSQL extension for supporting deep learning model
inference within the database and vector storage" (`README.md:2`)
`[from-README]`. The thesis: **run PyTorch/libtorch models from SQL** — import
a TorchScript `.pt` model into a catalog table, then call
`SELECT predict_float(model, 'cpu', col) FROM t` to score rows *inside the
backend process*, with no external model-serving hop. Its second leg is a
native **`mvec`** vector type that stores dimensioned tensors in-table so
libtorch can consume them directly, letting users pre-materialize vectors to
skip preprocessing at inference time (`README.md:6`, `README.md:110-145`)
`[from-README]`. It is the "co-processing runtime linked into the backend"
member of the analytics-in-PG family alongside [[pg-strom]] (GPU offload) and
the vector-search extensions [[pgvector]] / [[pgvectorscale]] / [[lantern]] —
but where those do *similarity search*, MorphingDB does *model inference*:
libtorch's `forward()` is invoked from a `Datum foo(PG_FUNCTION_ARGS)` entry
point.

## How it hooks into PG

Everything is ordinary loadable-extension surface — SQL-callable C++ compiled
to a single `pgdl.so`, wired through a `CREATE EXTENSION` install script. There
is **no bgworker and no `_PG_init`** in the fetched code (no `_PG_init` symbol
appears in `interface.cpp`) `[verified-by-code]`; the extension is passive UDFs
plus catalog tables, not a daemon.

- **`PG_MODULE_MAGIC` + a flat wall of `PG_FUNCTION_INFO_V1`** in
  `src/pgdl/interface.cpp:33-86` `[verified-by-code]`: the inference UDFs
  (`create_model`, `modify_model`, `drop_model`, `predict_float`,
  `predict_text`, `register_process`, `load_base_model`, `image_classification`,
  `api_load_model`, `api_predict`), the `mvec` type I/O
  (`mvec_input`/`mvec_output`/`mvec_receive`/`mvec_send`), the vector
  operators (`mvec_add`/`mvec_sub`/`mvec_equal`, `array_to_mvec`,
  `text_to_mvec`, `mvec_to_float_array`, `get_mvec_data`, `get_mvec_shape`),
  and an **access-method handler** `mvec_am_handler` (`interface.cpp:66`)
  `[verified-by-code]`.

- **Model registry as a catalog table, not a system catalog.** The install
  script creates `model_info(model_name pk, model_path, create_time,
  update_time, md5, upload_by, discription)` (`sql/pgdl--1.0.0.sql:6`) and, in
  a later migration, an `ai_operator` reference table
  (`sql/pgdl--1.2.0--1.3.0.sql`) `[verified-by-code]`. `create_model` inserts a
  row and side-loads the TorchScript file from `model_path`; inference UDFs
  resolve `model_name → model_path` via `model_manager.GetModelPath()`
  (`interface.cpp:271`) `[verified-by-code]`. Models live on the **server
  filesystem**, referenced by path — not stored as bytea in the catalog.

- **The `mvec` type is a real varlena.** `src/pgdl/vector.h:24-87` defines a
  `union MVec` with a `SET_VARSIZE` header, a `dim`, a `shape[10]` array, and a
  flexible `float data[]` payload; `DatumGetMVec` is `PG_DETOAST_DATUM`
  (`vector.h:86`), and the header comment notes it can be TOAST-compressed to
  `varattrib_1b` for small vectors and must be detoasted on read
  (`vector.h:81-87`) `[verified-by-code]`. Text form is
  `'[1.0,2.2,3.123,4.2]{4}'` — bracketed data plus a `{shape}` suffix parsed by
  `mvec_input` (`interface.cpp:490-528`) `[verified-by-code]`.

- **A `ref` variant for out-of-line vectors.** The `MVec` union has a second
  arm `MVecRef{ is_ref_tag, row_id }` (`vector.h:26-38`): a vector datum can be
  a *reference* carrying a `RowId` instead of inline float data, tagged by
  `is_ref_tag` (`vector.h:55-71`) `[verified-by-code]`. Combined with
  `mvec_am_handler`, this signals a design for storing large vectors out of the
  main tuple and dereferencing by id — an access-method-shaped storage story
  `[inferred]` (the AM handler body was beyond the fetched region; see code
  gap). See [[access-method-apis]].

- **Config via UDFs, not GUCs.** Batch timing is toggled by a
  `enable_print_batch_time(bool)` **procedure** and a `print_cost` UDF
  (`sql/pgdl--1.0.0.sql:53`, `interface.cpp:78`), and there is
  `CLOCK_START()/CLOCK_END()` instrumentation around load/preprocess/infer/post
  stages (`interface.cpp:273-357`) `[verified-by-code]`. No
  `DefineCustom*Variable` call appears in the fetched code `[verified-by-code]`
  — so model paths / device selection are per-call arguments, not GUCs (cf.
  [[gucs-config]], which this extension notably does *not* use).

- **Batch inference as a moving-aggregate.** `predict_batch_float8` /
  `predict_batch_text` are `CREATE AGGREGATE`s with `MSFUNC`/`MINVFUNC`/
  `MFINALFUNC` set (`sql/pgdl--1.0.0.sql:37-52`), invoked as window functions
  (`... OVER (ROWS BETWEEN CURRENT ROW AND N FOLLOWING)`) to amortize a model
  call across a window (`README.md:78-92`) `[verified-by-code]` `[from-README]`.

## Where it diverges from core idioms

This is the crux: MorphingDB statically links a multi-hundred-MB C++ ML runtime
(libtorch + OpenCV + ONNX Runtime + SentencePiece) into every backend and runs
tensor math on the executor's own thread.

- **A huge C++ runtime linked into the backend.** `CMakeLists.txt:16-20`
  `find_package`s `Torch`, `OpenCV`, `SentencePiece`, and `onnxruntime` and
  links them all into `pgdl.so` `[verified-by-code]`. Because PG uses a
  per-connection **fork** model, every `psql` connect maps this entire runtime
  into a fresh backend's address space. There is no shared model server — the
  divergence from [[pg-strom]] is stark: pg-strom centralizes CUDA in one
  bgworker daemon; MorphingDB puts the whole runtime in-process, per backend.

- **The model cache is per-backend, in the C++ heap, never shared.**
  `ModelManager model_manager;` is a **global C++ object** instantiated at
  `.so` load time (`interface.cpp:31`) `[verified-by-code]`. Its handles live
  in `std::unordered_map<std::string, torch::jit::script::Module>`
  (`model_manager.h:209-213`) `[verified-by-code]`, populated lazily on first
  `predict` via `torch::jit::load(model_path)` (`model_manager.cpp:246`,
  `model_manager.cpp:266`) `[verified-by-code]`. Consequence: **each backend
  loads and JIT-caches its own copy of every model it touches** — no
  `shared_buffers`-style sharing, no cross-backend reuse. A connection-pooled
  workload re-pays `torch::jit::load` per backend `[inferred]`. This is the
  mirror image of core's shared-memory-everything discipline; the cache is
  invisible to `pg_backend_memory_contexts`.

- **Tensors are libtorch-managed, not `palloc`/MemoryContext.** The inference
  pipeline lives in `std::vector<torch::jit::IValue>` and `torch::Tensor`
  (`interface.cpp:318-357`, `vector.h:102-103` `tensor_to_vector` /
  `vector_to_tensor`) `[verified-by-code]`. libtorch owns that memory via its
  own allocator/refcounting; PG's MemoryContext machinery has no visibility and
  cannot reset it on error. Only the thin glue (`Args* args =
  palloc(...)` at `interface.cpp:251`, the `MVec` datum, result `Datum`) is
  `palloc`ed. So one UDF call straddles two allocators with different lifetime
  rules (cf. [[memory-contexts]]).

- **The C++-exception ↔ `ereport`/longjmp bridge is manual and lossy.** Each
  stage is wrapped `try { ... } catch (const std::exception& e){
  ereport(ERROR, (errmsg("... %s", e.what()))); }`
  (`interface.cpp:320-355`) `[verified-by-code]` — a libtorch C++ exception is
  caught and *re-raised* as a PG `ERROR`. But `ereport(ERROR)` `longjmp`s to the
  nearest `PG_CATCH`/`sigsetjmp`, and the many *non*-`try`-wrapped `ereport`s in
  the same function (e.g. `interface.cpp:271,277,311`) `longjmp` straight
  **through** live C++ frames — the local `std::string model_path`,
  `std::vector<IValue>`, and any libtorch temporaries on the stack are **not
  destructed**, leaking their heap/GPU memory for the life of the backend
  `[inferred]`. This is the classic C++/PG impedance mismatch (cf.
  [[error-handling]]'s `PG_TRY` longjmp-safety contract): the two unwinding
  models — C++ stack unwinding vs. PG `longjmp` — are not reconciled here.

- **Heavy compute inside the row-at-a-time executor.** `predict_float`
  (`interface.cpp:242-360`) runs, per row: `LoadModel` (cache lookup) →
  optional `SetCuda` (`.to(at::kCUDA)`, `model_manager.cpp:343-345`) →
  gather args → `PreProcess` callback → `model.forward(input)`
  (`model_manager.cpp:639`) → `OutputProcess` callback `[verified-by-code]`.
  A full neural-net forward pass — possibly on GPU — executes synchronously on
  the backend's single thread inside `ExecInterpExpr`'s function call. Core PG
  is rigorously one-thread-per-backend; libtorch may spin its own intra-op
  thread pool underneath, invisibly. The moving-aggregate batch path exists
  precisely to amortize this cost over a window `[from-README]`.

- **GPU device selection is a per-call string argument.** `predict_float(model,
  'cpu'|'gpu', ...)` — `pg_strcasecmp(cuda, "gpu")` then
  `model_manager.SetCuda()` migrates the cached module to CUDA
  (`interface.cpp:283-286`, `model_manager.cpp:338-345`) `[verified-by-code]`.
  There is no planner cost integration for CPU-vs-GPU (contrast [[pg-strom]]'s
  cost-model GUCs); the SQL author picks the device inline.

- **An alarming input allocation.** `mvec_input` does
  `float *x = (float*)palloc(sizeof(float) * MAX_VECTOR_DIM)` with
  `MAX_VECTOR_DIM = 102400000` (`interface.cpp:494`, `vector.h:18`) — a ~400 MB
  scratch `palloc` on **every** vector literal parse, `pfree`d at the end
  (`interface.cpp:527`) `[verified-by-code]`. It stays within the MemoryContext
  contract (so no leak), but the sizing is a smell: a single-row insert of a
  4-element vector transiently reserves 400 MB.

## Notable design decisions

- **`mvec` as a first-class varlena carrying `{shape}`** — not just a float
  array but a dimensioned tensor (dim + `shape[10]`), so a stored vector
  round-trips to a libtorch tensor with its shape intact
  (`vector.h:39-46`, `vector.h:102-103`) `[verified-by-code]`. This is what
  lets "pre-materialized vectors skip preprocessing" (`README.md:6`)
  `[from-README]`.

- **Reference (out-of-line) vectors via a tagged union + AM handler** —
  `MVecRef{row_id}` vs inline `MVecEntry` (`vector.h:24-48`) plus
  `mvec_am_handler` (`interface.cpp:66`) `[verified-by-code]`; the design
  anticipates large vectors stored outside the heap tuple and fetched by id.
  Body of the AM handler is in the unfetched tail — **code gap**.

- **Models on the filesystem, referenced by path in a user table** —
  `model_info.model_path` (`sql/pgdl--1.0.0.sql:6`); `torch::jit::load` reads
  the file (`model_manager.cpp:246`) `[verified-by-code]`. Simpler than storing
  weights in-catalog, but couples correctness to server-local paths and an MD5
  column for change detection (`model_manager.h:107`) `[verified-by-code]`.

- **Registered pre/post-processing callbacks compiled into the `.so`** —
  `register_process()` calls `register_callback()` (`interface.cpp:483-487`)
  which populates `ModelManager`'s
  `module_preprocess_functions_` / `module_outputprocess_functions_{float,text}_`
  maps, keyed by model with a `"common"` fallback
  (`model_manager.cpp:368-410`, `model_manager.h:177-198`) `[verified-by-code]`.
  The README instructs users to *write handlers in `src/external_process` and
  rebuild* (`README.md:60-66`) `[from-README]` — i.e. preprocessing logic is
  C++ recompiled into the extension, not SQL/data. That directory's files are
  the **code gap** (all filename probes 404'd; only the `CMakeLists` glob
  confirms it exists, `CMakeLists.txt:22`).

- **Base-model pre-loading at startup of the manager** — `InitBaseModel()`
  eagerly `torch::jit::load`s registered base models into `base_module_handle_`
  and reports the count via `ereport(INFO)` (`model_manager.cpp:37-47`)
  `[verified-by-code]`; fine-tuned models can then reuse a base module's
  structure (`interface.cpp:138-167`) `[verified-by-code]`.

- **Task-centric UDFs layered over model-centric ones** —
  `image_classification(col)` and the `api_*` functions (`interface.cpp:81-86`,
  `sql/pgdl--1.2.0--1.3.0.sql`) wrap the raw predict path in named tasks
  (`README.md:94-99`) `[from-README]` `[verified-by-code]`.

## Links into corpus

- [[pg-strom]] — the other "co-processor runtime in PG" ideology; instructive
  contrast: centralized GPU-service bgworker + cost-model GUCs vs. MorphingDB's
  per-backend in-process libtorch with inline device choice.
- [[pgvector]], [[pgvectorscale]], [[lantern]], [[onesparse]] — vector / linear-
  algebra siblings; MorphingDB's `mvec` is a dimensioned-tensor cousin, but its
  purpose is model *inference*, not similarity search.
- [[fmgr]] — the `PG_FUNCTION_INFO_V1` / `PG_GETARG_*` / `PG_RETURN_*` surface
  every MorphingDB UDF rides on (and `get_fn_expr_argtype` for its `VARIADIC
  "any"` dispatch, `interface.cpp:290`).
- [[memory-contexts]] — the palloc/MemoryContext model that libtorch's tensor
  allocator sits entirely outside of.
- [[error-handling]] — the `ereport`/`longjmp` contract the manual C++
  `try/catch → ereport(ERROR)` bridge only partially honors.
- [[catalog-conventions]] — contrast: MorphingDB keeps its model registry as an
  ordinary user table, not a system catalog.

## Sources

Fetched 2026-07-03. Fetch constraint: only
`raw.githubusercontent.com/MorphingDB/MorphingDB/master/<path>` returns 200; the
tree API / codeload / HTML endpoints all 403, so `src/` could not be listed.
Layout was resolved from the root `CMakeLists.txt` glob, then each globbed
translation unit fetched by exact path.

- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/README.md` — HTTP 200.
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/CMakeLists.txt` — HTTP 200 (resolved `src/pgdl/*.cpp` + `src/external_process/*.cpp` layout; names libtorch/OpenCV/ONNX/SentencePiece deps).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/pgdl.control` — HTTP 200 (`default_version = '1.3.0'`, `module_pathname = '$libdir/pgdl'`, `relocatable = true`).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/sql/pgdl--1.0.0.sql` — HTTP 200.
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/sql/pgdl--1.2.0--1.3.0.sql` — HTTP 200.
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/src/pgdl/interface.cpp` — HTTP 200 (1120 lines; UDF layer, `PG_MODULE_MAGIC`, predict pipeline, mvec I/O).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/src/pgdl/vector.h` — HTTP 200 (`MVec` varlena union, macros).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/src/pgdl/vector.cpp` — HTTP 200 (393 lines; not fully quoted here).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/src/pgdl/model_manager.cpp` — HTTP 200 (645 lines; libtorch model cache + load/predict).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/src/pgdl/model_manager.h` — HTTP 200 (`ModelManager` class, unordered_map caches).
- `https://raw.githubusercontent.com/MorphingDB/MorphingDB/master/src/pgdl/env.h` — HTTP 200 (torch/OpenCV includes + `extern "C"` postgres.h wrapper).
- Probed but **HTTP 404** (wrong-name guesses; not part of the tree): `morphingdb.control`, `src/morphingdb.control`, `control`, `src/CMakeLists.txt`, `src/Makefile`, `Makefile`, `src/pgdl/{mvec,model,predict,pgdl,inference,model_operate,torch_operate,...}.cpp`, and all probed `src/external_process/*` filenames.
- **Code gap:** `src/external_process/*` (user pre/post-processing handlers, per `README.md:60-66` and `CMakeLists.txt:22`) could not be enumerated — every filename probe 404'd. Claims about that layer are `[from-README]` / `[inferred]`.
