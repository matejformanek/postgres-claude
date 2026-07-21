# postgresml — training and serving ML models inside the backend

- **Repo:** github.com/postgresml/postgresml (branch `master`). The backend
  half is the Rust/pgrx extension under `pgml-extension/`
  (`pgml-extension/Cargo.toml:2`, crate `pgml` v2.10.0). Built on **pgrx**
  `=0.12.9` (`pgml-extension/Cargo.toml:46`).
- **Fetched:** `README.md` (240 lines), `pgml-extension/Cargo.toml`,
  `src/lib.rs`, `src/api.rs` (1740 lines), `src/bindings/mod.rs`,
  `src/bindings/python/mod.rs`, `src/bindings/sklearn/mod.rs`,
  `src/bindings/xgboost.rs`, `src/bindings/lightgbm.rs`,
  `src/bindings/transformers/mod.rs`, `src/orm/mod.rs`, `src/orm/model.rs`
  (1188 lines), `src/orm/snapshot.rs` (1404 lines), `src/orm/project.rs`.
  Not fetched: `sql/schema.sql`, the `*.py` sidecar files
  (`sklearn.py`, `transformers.py`, `python.py`), `src/orm/dataset.rs`,
  `src/config.rs`, `src/bindings/linfa.rs`, `src/bindings/transformers/transform.rs`.

## Domain & purpose

PostgresML is a pgrx extension that **trains AND serves machine-learning
models from within the PostgreSQL backend process** — classical ML
(regression / classification / clustering via scikit-learn, XGBoost,
LightGBM, linfa) and LLM inference (Hugging Face `transformers`:
embeddings, text generation, reranking, fine-tuning). Its founding
ideology, stated in the README, is to **move models to the data** rather
than move data to the models: *"It's more efficient, manageable and
reliable to move models to the database, rather than constantly moving data
to the models"* (`README.md:20`, `[from-README]`). The user-facing surface
is a set of `pgml.*` SQL functions — `pgml.train`, `pgml.predict`,
`pgml.embed`, `pgml.transform` — so an application does inference in a
`SELECT` next to the rows it is scoring (`README.md:154-229`,
`[from-README]`).

## How it hooks into PG

Entirely through **pgrx `#[pg_extern]` SQL-callable functions** plus a
catalog of ordinary `pgml.*` tables. There is **no custom table/index AM,
no FDW, and no `ProcessUtility`/planner hook**; the one shared-memory
structure is a deployment cache (below), and there is no bgworker in the
fetched sources (`[verified-by-code]` for the absence in the read files;
`[inferred]` for the extension as a whole — the monorepo is large and only
`pgml-extension/src/` was read).

- **Load path.** `_PG_init` runs three steps: server-param init, Python
  venv activation, and shared-memory init for the deployment map
  (`src/lib.rs:26-30`). `pg_module_magic!()` (`src/lib.rs:20`) and
  `extension_sql_file!("../sql/schema.sql", … finalize)` (`src/lib.rs:22`)
  wire the catalog DDL — the `pgml.projects`, `pgml.models`,
  `pgml.snapshots`, `pgml.deployments`, `pgml.files`, `pgml.logs` tables are
  referenced throughout the ORM but live in the un-fetched `schema.sql`
  (`[verified-by-code]` the tables are referenced, e.g. `src/orm/model.rs:96`,
  `src/orm/project.rs:155`; `[inferred]` their exact DDL).

- **Entry points.** `train` / `train_joint` (`src/api.rs:91,137`), the
  `predict` family overloaded per input type
  (`predict_f32`/`_f64`/`_i16`/`_i32`/`_i64`/`_bool`, `src/api.rs:439-466`),
  `predict` by model id and by whole row (`src/api.rs:523-540`),
  `predict_proba` / `predict_joint` / `predict_batch`
  (`src/api.rs:507-521`), `embed` / `embed_batch` / `rank`
  (`src/api.rs:591-614`), the overloaded `transform` set
  (`src/api.rs:671-708`) and streaming/conversational variants
  (`src/api.rs:756-820`), plus `snapshot`, `load_dataset`, `deploy`, and
  `dump_all`/`load_all` (`src/api.rs:332-563,1028-1051`).

- **Inference functions are `immutable, parallel_safe, strict`**
  (`src/api.rs:439,523,671`). Marking a function that runs an embedded
  Python interpreter or a native gradient-boosting predictor `immutable` and
  `parallel_safe` is a deliberate promise to the planner that these calls
  can be folded, cached, and run in parallel workers — a strong claim for a
  body that touches so much external runtime state (`[verified-by-code]`).

- **Everything talks to the catalog through SPI.** The ORM layer uses
  `Spi::get_one_with_args` / `Spi::connect` for every read and write
  (`src/orm/project.rs:122-167`, `src/orm/model.rs:335-360`), so model
  metadata, deployments, and serialized model bytes are all ordinary rows —
  queryable, dumpable, and replicated like any table.

## Where it diverges from core idioms

The load-bearing divergence: **PostgresML runs the ML runtime *inside* the
backend, and that runtime's memory, threads, and object graphs live entirely
outside PostgreSQL's `MemoryContext` discipline.** Two mechanisms:

### 1. An embedded CPython interpreter per backend (pyo3)

The `python`, `sklearn`, and `transformers` bindings are compiled only with
the `python` feature (default-on, `Cargo.toml:14,23`) and reach scikit-learn
and Hugging Face through **pyo3** with `auto-initialize`
(`Cargo.toml:48`). Each binding embeds a `.py` sidecar as a string at compile
time and instantiates it as a `PyModule` once per process via
`Python::with_gil` + `PyModule::from_code`
(`src/bindings/mod.rs:39-53`; e.g. `src/bindings/sklearn/mod.rs:24`,
`src/bindings/transformers/mod.rs:23`). Every ML call acquires the GIL
(`Python::with_gil`) for the duration — `src/bindings/sklearn/mod.rs:121,175`,
`src/bindings/python/mod.rs:16`, `src/bindings/transformers/mod.rs:79-99`
(`[verified-by-code]`).

- **GIL management is per-backend, not per-cluster.** Because PG's
  per-connection *fork* model gives every backend its own address space,
  each backend that touches Python spins up its **own** interpreter (pyo3
  `auto-initialize`) with its **own** GIL. There is therefore no
  cross-backend GIL contention — the GIL only serializes *within* one
  backend, which is already single-threaded at the SQL level. `_PG_init`
  activates the configured virtualenv at load
  (`src/lib.rs:28` → `src/bindings/python/mod.rs:15-29`), and
  `validate_dependencies` imports `xgboost`/`lightgbm`/`numpy`/`sklearn` from
  that interpreter (`src/bindings/python/mod.rs:42-56`) (`[verified-by-code]`
  for the with-gil/auto-initialize wiring; `[inferred]` for the
  one-interpreter-per-forked-backend consequence).

- **numpy arrays, Python objects, and the Python heap are invisible to
  `palloc`.** A fitted sklearn model is held as an opaque `Py<PyAny>` inside
  a Rust `Estimator` struct that the code force-marks `Send + Sync`
  (`src/bindings/sklearn/mod.rs:157-164`). Its lifetime is Rust/Python
  reference-counted, not tied to any `MemoryContext` or transaction —
  contrast [[knowledge/idioms/memory-contexts]], where backend allocations
  are supposed to hang off a context that gets reset at statement/transaction
  end. Training data crosses the boundary as flat `&[f32]` slices
  (`src/bindings/sklearn/mod.rs:135,174`), i.e. copied out of PG datums into
  numpy, doubling the working set.

### 2. Native ML libraries linked as Rust crates

XGBoost, LightGBM, and linfa are ordinary Cargo dependencies — several
pinned to PostgresML's own forks (`Cargo.toml:36-40,55`), with OpenBLAS
linked as a system lib (`Cargo.toml:42`, `openblas-src`). These run as
**native C/C++/Rust code in the backend with no Python involved**:

- XGBoost uses its own `DMatrix`/`Booster` and `DMatrix::from_dense`
  (`src/bindings/xgboost.rs:194-302`); LightGBM wraps `lightgbm::Booster`
  (`src/bindings/lightgbm.rs:11-13`). Their model heaps and worker threads
  are managed by the native libraries, again outside PG's memory and process
  model.
- **Thread count is pulled from a GUC and pushed into the native library.**
  On deserialize, XGBoost reads `pgml.predict_concurrency` via SPI and sets
  the booster's `nthread` (`src/bindings/xgboost.rs:370-381`); the test
  harness pins `pgml.omp_num_threads = '1'` (`src/lib.rs:57`). So a single
  `SELECT pgml.predict(...)` can spawn an OpenMP thread pool inside a
  backend that PostgreSQL believes is single-threaded (`[verified-by-code]`).

### 3. Model (de)serialization: bytes in a catalog table, scratch on `/tmp`

Models are **not** serialized through PG's type system or TOAST directly as
a first-class type; instead each model's artifact files are chunked into
`bytea` rows of `pgml.files`:

- Rust estimators serialize to a single `estimator.rmp` (rmp-serde) row
  (`src/orm/model.rs:960`); HF/checkpoint models are read from a directory
  and split into **100 MB `bytea` chunks** keyed by `(model_id, path, part)`
  (`src/orm/model.rs:288-312`, note `bytes.chunks(100_000_000)` at `:296`).
- `Model::find` reads those bytes back and reconstructs the estimator via the
  `Bindings::from_bytes` trait method, dispatching on runtime+algorithm
  (`src/orm/model.rs:353-393`).
- **XGBoost round-trips through the filesystem**, not memory: `to_bytes`
  writes to a random `/tmp/pgml_*.bin`, reads it back, and deletes it
  (`src/bindings/xgboost.rs:347-354`) — the native lib only offers
  file-based save. HF `generate` similarly *dumps* model parts from
  `pgml.files` to `/tmp/postgresml/models/<id>` on a cache miss
  (`MissingModelError`) before loading them into the Python process
  (`src/bindings/transformers/mod.rs:260-320`). The extension leans on the
  local filesystem as a staging area — a dependency core PG code paths avoid
  (`[verified-by-code]`).
- The `Bindings` trait deliberately eschews Serde: *"scikit-learn estimators
  were originally serialized in pure Python as pickled objects, and neither
  xgboost nor linfa estimators completely implement serde"*
  (`src/bindings/mod.rs:93-112`). sklearn's `to_bytes` therefore calls a
  Python `save` (pickle) inside the GIL (`src/bindings/sklearn/mod.rs:188-192`).
  So a Postgres row may contain a **Python pickle** as its payload
  (`[verified-by-code]` the call; `[inferred]` that the format is pickle,
  from the sidecar's name/comment).

### 4. Training is a synchronous, minutes-long SQL statement

`pgml.train` does the whole pipeline in one call on the calling backend:
create/find the project, **snapshot the training table**, fit the model,
compute metrics, compare against the currently deployed model, and
auto-deploy if better (`src/api.rs:163-322`). There is no job queue and no
bgworker offload in the read code — a `SELECT pgml.train(...)` holds the
backend (and its transaction) for the entire fit
(`[verified-by-code]`). Metric comparison and `automatic_deploy` gate the
deploy inline (`src/api.rs:270-322`).

### 5. Snapshots materialize (or re-sample) the training set

`Snapshot::create` introspects the source relation via
`information_schema.columns` (`src/orm/snapshot.rs:515`) and, when
`materialized = true`, runs `CREATE TABLE "pgml"."snapshot_<id>" AS
<sampled_query>` (`src/orm/snapshot.rs:620-624`) — a physical copy of the
training data so a model is reproducible against a frozen input. When not
materialized, the sampling query is re-run at read time
(`src/orm/snapshot.rs:749-764`). On top of that sits a full preprocessing
layer computed in Rust over the training data — per-column `Statistics`
(min/max/mean/median/mode/variance/histogram/ventiles/categories,
`src/orm/snapshot.rs:31-46`) and `Encode` / `Impute` / `Scale` strategies
(`src/orm/snapshot.rs:70-109`), producing a `numeric_encoded_dataset`
(`src/orm/snapshot.rs:1168`). This reimplements, in-process, the
feature-engineering a Python ML pipeline would normally own.

## Notable design decisions

- **A two-tier deployment cache: per-backend heap + cross-backend shared
  memory.** Deserialized live models are cached per backend in a
  `Lazy<Mutex<HashMap<i64, Arc<Model>>>>` (`DEPLOYED_MODELS_BY_ID`,
  `src/orm/model.rs:24`), populated on the first `find_cached`
  (`src/orm/model.rs:435-448`) so each backend pays the deserialize cost
  once. The *deployment routing* — which model id is live for a project — is
  kept in genuine PG shared memory: `ProjectDeploymentMap` wraps a
  `PgLwLock<ProjectIdMap>` over a fixed-capacity `heapless::IndexMap` of 1024
  entries (`src/orm/project.rs:15-95`), initialized with `pg_shmem_init!` in
  `project::init` (`src/orm/project.rs:93-95`) and updated under
  `.exclusive()` on `deploy` (`src/orm/project.rs:152-168`). At capacity it
  logs a warning and clears (`src/orm/project.rs:141-143,163-166`). This is a
  rare case of an extension using core's LWLock + shmem primitives directly
  through pgrx (`[verified-by-code]`).

- **`panic = "unwind"` in every profile** (`Cargo.toml:64-71`). PG's
  `ereport(ERROR)` uses `setjmp`/`longjmp`; pgrx converts Rust panics into
  PG errors and vice-versa, which requires unwinding rather than `abort`.
  Making the ML crates and pyo3 unwind-compatible is a hard constraint the
  extension bakes into its build (`[verified-by-code]` the setting;
  `[inferred]` the setjmp/longjmp rationale — see [[knowledge/ideologies/pgrx]]).

- **The Python↔Postgres value bridge is hand-rolled.** A `Json` newtype
  implements `FromPyObject`, walking Python dict/bool/int/float/str/list/None
  into `serde_json::Value` (`src/bindings/transformers/mod.rs:34-76`), and a
  reverse `r_insert_logs` / `r_log` pair are exported as `#[pyfunction]`s so
  the *Python* side can call back into PG via SPI and `ereport`
  (`src/bindings/mod.rs:10-35`) — a bidirectional FFI bridge between the two
  runtimes inside one process.

- **Runtime is selectable per model** (`Runtime::rust` vs `Runtime::python`),
  and the same algorithm (e.g. XGBoost, LightGBM) exists in both a native-Rust
  and a Python-sklearn implementation, chosen at `Model::create`
  (`src/api.rs:240-249`, `src/orm/model.rs:365-393`); `Runtime::openai` is
  rejected for train/inference (`src/orm/model.rs:366-368`). The test suite
  benchmarks the two runtimes head-to-head (`src/bindings/mod.rs:135-230`).

- **HF task whitelist.** `transform` verifies the requested task against a
  whitelist before dispatching (`src/api.rs:679`,
  `crate::bindings::transformers::whitelist::verify_task`) — a guard against
  arbitrary model/pipeline loading from a SQL argument (`[verified-by-code]`
  the call; whitelist contents in the un-fetched `whitelist` module,
  `[inferred]`).

- **`load_dataset` writes external data straight into the catalog.** Hugging
  Face datasets are pulled in Python, typed-mapped to PG types, and inserted
  row-by-row into a generated `pgml.<name>` table via SPI
  (`src/bindings/transformers/mod.rs:322-470`) — the extension both consumes
  and produces ordinary tables.

## Links into corpus

- [[knowledge/ideologies/pg_onnx]] — the narrower sibling: ONNX *inference
  only*, no training and no Python interpreter. PostgresML is the maximal end
  of the "ML in the backend" spectrum; pg_onnx is the minimal.
- [[knowledge/ideologies/pg_vectorize]] — contrast in architecture:
  pg_vectorize *orchestrates external* LLMs over HTTP, keeping the model out
  of process; PostgresML runs the model **in-process** (pyo3 + native crates).
  Same problem space (embeddings/RAG in SQL), opposite placement of the model.
- [[knowledge/ideologies/pgrx]] — the Rust framework everything here is built
  on: `#[pg_extern]`, `Spi`, `PgLwLock`/`pg_shmem_init!`, `JsonB`, and the
  panic-unwind ↔ ereport bridge.
- In-core analogue for Python-in-backend: PL/Python
  ([[knowledge/files/src/pl/plpython/plpy_main]],
  [[knowledge/docs-distilled/plpython-database]]). No
  `knowledge/ideologies/plpython.md` exists yet. PL/Python is the *supported*
  way to run Python in a backend (an untrusted PL with its own interpreter and
  SPI bridge); PostgresML reaches the interpreter through pyo3 from Rust
  instead of through the PL handler, but faces the same GIL / non-MemoryContext
  memory story.
- [[knowledge/idioms/memory-contexts]] — the discipline the ML runtime memory
  (numpy, Python GC, native booster heaps, `/tmp` scratch files) sits
  *outside* of; the central reason this extension's memory behavior differs
  from core code.

## Sources

- `https://raw.githubusercontent.com/postgresml/postgresml/master/README.md`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/Cargo.toml`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/lib.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/api.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/bindings/mod.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/bindings/python/mod.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/bindings/sklearn/mod.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/bindings/xgboost.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/bindings/lightgbm.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/bindings/transformers/mod.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/orm/mod.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/orm/model.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/orm/snapshot.rs`
- `https://raw.githubusercontent.com/postgresml/postgresml/master/pgml-extension/src/orm/project.rs`
- All 14 URLs returned HTTP 200. No 404s. (An unrelated `README.md` name
  collision in the scratch dir was re-fetched to confirm the postgresml
  README content; the 14 canonical URLs above are authoritative.)

Confidence: `[verified-by-code]` for the pgrx entry points and their
volatility markings, the pyo3/`Python::with_gil` embedding, the native
XGBoost/LightGBM/linfa crate linkage, model bytes stored in `pgml.files`
(100 MB chunks) with `/tmp` staging, the `Bindings` trait and its
no-Serde/pickle note, the two-tier deployment cache (per-backend `Arc<Model>`
map + `PgLwLock` shmem `ProjectDeploymentMap`), synchronous in-backend
training, and snapshot materialization + preprocessing. `[from-README]` for
the "move models to the data" ideology and the user-facing SQL examples.
`[inferred]` for: one-CPython-interpreter-per-forked-backend and the
resulting GIL isolation; the exact `sql/schema.sql` catalog DDL (referenced,
not read); the pickle serialization *format*; the `panic=unwind`↔setjmp/longjmp
rationale; and the whitelist contents. Only `pgml-extension/src/` was read —
the wider monorepo (SDKs, dashboard, `pgcat`) was not, so claims are scoped to
the extension.
