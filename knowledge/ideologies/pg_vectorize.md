# pg_vectorize — a RAG/embedding orchestration platform that wires pgvector + pgmq + pg_cron together, generates DDL against user tables, and calls out to external LLM APIs from a bgworker — with the same logic runnable *outside* Postgres entirely

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tembo-io/pg_vectorize` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-07-18 (see Sources footer). Built on `[[pgvector]]`,
> `[[pgmq]]`, `[[pg_cron]]`, and `[[pgrx]]`; sibling to `[[pg_later]]` (same
> Tokio+sqlx bgworker substrate, same authors) but a distinct
> **AI-orchestration** axis.

## Domain & purpose

pg_vectorize automates "text → embeddings → vector/full-text/hybrid search" so
you can build RAG on Postgres: `select vectorize.table(...)` registers a job
that embeds a source table's columns and **continuously watches for updates**,
and `select vectorize.search(...)` runs semantic search
(`README.md`; `extension/src/api.rs:82,117`) `[verified-by-code]`. It "relies
heavily on pgvector for vector similarity search, pgmq for orchestration in
background workers, and SentenceTransformers" (`README.md:9`) `[from-README]`.

**The one thing that makes pg_vectorize structurally distinct.** Most extensions
in this corpus *add* one capability at the C boundary. pg_vectorize is an
**application platform** whose substrate is *other extensions wired together at
runtime*: it drives `[[pgvector]]` (the vector column + HNSW/diskann index),
`[[pgmq]]` (the `vectorize_jobs` queue), and `[[pg_cron]]` (the recurring
refresh schedule) by **generating and executing SQL/DDL** against them and
against the user's own tables — then a background worker calls **external LLM
HTTP APIs** (OpenAI, Cohere, Ollama, HuggingFace, Voyage, …) to produce the
embeddings. And the whole thing is factored so the same core logic runs *either*
embedded in a backend *or* as a standalone HTTP server that connects to Postgres
from outside (`README.md` "Modes at a glance") `[from-README]`. The extension is
one deployment of a database-external service, not a feature bolted to the
executor.

## How it hooks into PG

- **Three `extension_sql_file!` install scripts + a pile of `#[pg_extern]`
  functions** (`extension/src/lib.rs:18-21`; `api.rs` defines `table`, `search`,
  `transform_embeddings`, `encode`, `job_execute`, … at
  `api.rs:17,82,117,160,170,180,207,225,243,329`) `[verified-by-code]`.
- **A bgworker running Tokio + `sqlx`** (`extension/src/workers/mod.rs`,
  `workers/pg_bgw.rs`): the worker reads pgmq messages and runs jobs against a
  `sqlx::Pool<Postgres>` — a client connection back to the database, exactly like
  `[[pg_later]]` (`workers/mod.rs:18-24,91-105`) `[verified-by-code]`.
- **~20 string GUCs holding provider URLs and API keys**
  (`vectorize.openai_key`, `vectorize.openai_service_url`,
  `vectorize.cohere_api_key`, `vectorize.ollama_service_url`,
  `vectorize.embedding_service_api_key`, `vectorize.voyage_api_key`,
  `vectorize.portkey_api_key`, …) (`extension/src/guc.rs:12-160`)
  `[verified-by-code]`.
- **Requires `cron.database_name` set** — its own test config sets
  `cron.database_name='vectorize_test'` (`extension/src/lib.rs:33`), because
  scheduling goes through pg_cron `[verified-by-code]`.
- **A separate `vectorize_core` / `vectorize_worker` crate** — the PG extension
  imports `vectorize_core::{query,types,guc,transformers,errors}` and
  `vectorize_worker::ops` (`workers/mod.rs:9-16`, `init.rs:5-8`), i.e. the
  domain logic is a PG-agnostic library the extension merely adapts
  `[verified-by-code]`.

## Where it diverges from core idioms

### 1. An extension whose backing store is three other extensions, wired via generated SQL

Setup is a sequence of `format!`-built SQL statements executed through SPI:

- **pgmq**: `init_pgmq` checks `pgmq.meta` and runs `SELECT pgmq.create('vectorize_jobs')`
  (`init.rs:11-35`) `[verified-by-code]`.
- **pg_cron**: `init_cron` runs
  `SELECT cron.schedule('{job_name}','{cron}', $$select vectorize.job_execute('{job_name}')$$)`
  — the recurring embedding refresh is a pg_cron entry whose command re-enters
  pg_vectorize (`init.rs:37-53`) `[verified-by-code]`.
- **pgvector / pgvectorscale**: the embedding index is chosen per job
  (`pgv_hnsw_cosine` → `create_hnsw_cosine_index`, `vsc_diskann_cosine` →
  `CREATE INDEX … USING diskann (…)`, …) (`init.rs:83-96,140-146`)
  `[verified-by-code]`.

So pg_vectorize is glue: it does not implement vectors, a queue, or a scheduler —
it *composes* `[[pgvector]]` + `[[pgmq]]` + `[[pg_cron]]` into a workflow. The
divergence from core idioms is that the "feature" exists almost entirely as
**runtime-generated SQL against other extensions' APIs**, not as new C behavior.

### 2. Mutating the user's own tables — appending columns / creating shadow tables + views — via string-built DDL

A vectorize job rewrites the user's schema. In `append` mode it
`ALTER TABLE {schema}.{table} ADD COLUMN {job}_embeddings vector(N),
ADD COLUMN {job}_updated_at timestamptz` (guarded by an
`information_schema.columns` existence check inside a `DO $$…$$` block)
(`init.rs:148-169`) `[verified-by-code]`. In `join` mode it creates a separate
`_embeddings_{job}` table, an index, and a **project view** joining source +
embeddings (`init.rs:105-135`, `query::create_project_view`) `[verified-by-code]`.
The identifiers are interpolated straight into the SQL strings
(`{job_name}`, `{schema}`, `{table}`) with only a `check_input(job_name)` name
guard (`init.rs:61,149`) — the classic generate-DDL-by-`format!` pattern, a
divergence from core's parse-tree-driven DDL. The feature literally reshapes the
caller's tables as a side effect of `vectorize.table()`.

### 3. A bgworker that calls external LLM HTTP endpoints, tokenizes with tiktoken, and pushes embeddings back over sqlx

`execute_job` (`workers/mod.rs:91-192`) is the heart:
1. Read job metadata from `vectorize.job` via `sqlx::query_as!`
   (`workers/mod.rs:71-88`) — again, **sqlx client connection, not SPI**
   `[verified-by-code]`.
2. Pull the source rows (`SELECT {pk}::text, {cols} FROM {schema}.{relation}
   WHERE {pk} = ANY($1)`, string-built + `sqlx::query_as`,
   `workers/mod.rs:122-147`) `[verified-by-code]`.
3. Estimate tokens with **`tiktoken_rs::cl100k_base`** — OpenAI's tokenizer
   embedded in the worker (`workers/mod.rs:8,106,155`) `[verified-by-code]`.
4. Resolve the provider (`providers::get_provider(source, api_key, service_url,
   virtual_key)`) and `provider.generate_embedding(...).await` — an **outbound
   HTTP call to an external embedding service** (`workers/mod.rs:114-119,166`)
   `[verified-by-code]`.
5. Write embeddings back via `ops::update_embeddings` / `upsert_embedding_table`
   over the sqlx pool (`workers/mod.rs:170-190`) `[verified-by-code]`.

This is the `[[pg_net]]`/`[[pgsql-http]]` "reach out of the backend" theme, but
the outbound target is an LLM API and the round-trip is orchestrated on a Tokio
runtime inside the bgworker. API keys ride in from GUCs
(`guc::get_guc_configs(...).api_key`, `workers/mod.rs:108-112`) — secrets held in
`PGC_*` string GUCs and handed to an outbound HTTP client, a very different
secret-handling posture than `[[vault]]`'s SQL-inaccessible key.

### 4. pgmq visibility-timeout retry: a job dies after 3 reads

The worker reads with a 180-second visibility timeout
(`queue.read::<JobMessage>(queue_name, 180)`, `workers/mod.rs:24`) and deletes
the message only on success, **or** on failure once `read_ct > 2`
(`workers/mod.rs:42-64`) `[verified-by-code]`. So a persistently failing
embedding job is retried up to three times (leaning entirely on pgmq's
re-visibility semantics) then dropped — retry is a property of the queue, not of
bespoke bookkeeping. A vanished job (`RowNotFound`) is treated as success so the
message is reaped (`workers/mod.rs:93-102`) `[verified-by-code]`.

### 5. Same core logic runs outside Postgres — the extension is one deployment target

`vectorize_core` + `vectorize_worker` are separate crates the extension adapts;
the repo also ships an HTTP-server mode (`POST /api/v1/table`, `GET
/api/v1/search`) that connects to Postgres as a client and exposes the identical
workflow (`README.md` "HTTP server (recommended for managed DBs)")
`[from-README]`. The extension form requires filesystem access to the PG host;
the server form does not. This deliberate split — PG-agnostic core, thin pgrx
adapter, alternate standalone server — is the structural inverse of a
core-coupled extension: the backend is a *host*, not the *substrate*. It is why
the worker talks sqlx (works in either deployment) rather than SPI (backend-only).

## Notable design decisions

- **`vectorize.` schema + `vectorize.job` metadata table** — jobs are catalog-ish
  rows read back over sqlx (`workers/mod.rs:75-84`) `[verified-by-code]`.
- **append vs join `TableMethod`** — two strategies for where embeddings live
  (in-place columns vs a joined shadow table + view), chosen per job
  (`init.rs:67-137`) `[verified-by-code]`.
- **Provider abstraction** (`vectorize_core::transformers::providers`) — OpenAI /
  Cohere / Ollama / Voyage / Portkey / a generic embedding service, each a GUC
  cluster in `guc.rs:12-160` `[verified-by-code]`.
- **`extension_sql_file!("../sql/meta.sql")` + example dataset**
  (`lib.rs:18-21`) — bootstrap DDL shipped as SQL files `[verified-by-code]`.
- Supports PG 13–18 (`README.md` badge) `[from-README]`.

## Links into corpus

- Composes `[[pgvector]]` (vector type + HNSW/diskann index; cf. `[[pgvectorscale]]`
  diskann), `[[pgmq]]` (job queue + visibility-timeout retry), `[[pg_cron]]`
  (recurring `job_execute` schedule), and `[[pgrx]]` (the Rust substrate).
- Twin of `[[pg_later]]`: identical Tokio-runtime + sqlx-client-back-to-the-DB
  bgworker pattern, different payload (LLM embedding vs arbitrary deferred query).
  Both sidestep SPI for the real work.
- Outbound-HTTP-from-a-worker theme with `[[pg_net]]` (async curl multi) and
  `[[pgsql-http]]` (sync libcurl) — here the callee is an LLM API.
- Secrets-in-GUCs vs `[[vault]]`'s SQL-inaccessible key: two opposite postures on
  where credentials live. See `knowledge/idioms/gucs-config.md` (if present).
- Generate-DDL-against-user-tables echoes `[[temporal_tables]]` /
  `[[pg_ivm]]` / `[[hydra-columnar]]` (each reshaping or shadowing user
  relations); string-built SQL caveats connect to `[[pg_later]]` §3.

## Sources

- `extension/src/init.rs` → HTTP 200 (199 lines; `init_pgmq`, `init_cron`,
  `init_embedding_table_query` append/join DDL generation, index selection,
  `information_schema` column checks — deep-read).
- `extension/src/workers/mod.rs` → HTTP 200 (192 lines; `run_worker`,
  `get_vectorize_meta`, `execute_job` full external-embedding pipeline — deep-read).
- `extension/src/guc.rs` → HTTP 200 (266 lines; provider URL + API-key GUC
  cluster — cited regions read).
- `extension/src/lib.rs` → HTTP 200 (35 lines; module wiring,
  `extension_sql_file!`, `cron.database_name` test config).
- `extension/src/api.rs` → HTTP 200 (390 lines; `#[pg_extern]` surface —
  `table`/`search`/`transform_embeddings`/`encode`/`job_execute` signatures read).
- `extension/src/{executor,job,search,types,transformers/mod}.rs` → HTTP 200
  (fetched; skimmed for the orchestration story, not all cited).
- `README.md` → HTTP 200 (two-mode HTTP-server-vs-extension framing, pgvector/
  pgmq/SentenceTransformers dependency narrative, PG 13–18 support).

All cites `[verified-by-code]` against the fetched `.rs`/`lib.rs` except the
end-user RAG/two-mode workflow and the SentenceTransformers dependency
(`[from-README]`), and the "same core runs outside PG as an HTTP server" claim,
which is `[from-README]` corroborated by the `vectorize_core`/`vectorize_worker`
crate split visible in the imports (`workers/mod.rs:9-16`). The `core/` and
`server/` crates were probed (present) but not deep-read — the extension-side
adaptation is the in-scope divergence surface.
