# rw_redis_fdw — a read/WRITE FDW onto a key-value / data-structure store

- **Repo:** github.com/nahanni/rw_redis_fdw (branch `master`,
  default_version `1.0`, `redis_fdw.control:2`, `relocatable = true`
  `:4`). Written by Leon Dang / Nahanni Systems, BSD-style license
  (`redis_fdw.c:5`). The output module is named **redis_fdw** but is the
  read-*write* successor to the older read-only pg-redis-fdw, whose table
  schema it borrows but whose code it replaces (`README.md:5`).
- **Fetched:** `README.md` (339 lines), `redis_fdw.c` (~4940 lines — the
  whole extension is one C file), `redis_fdw.control`, `Makefile`,
  `redis_fdw--1.0.sql`.

## Domain & purpose

A Foreign Data Wrapper mapping **Redis** — an in-memory key-value /
data-structure server — to PostgreSQL foreign tables, with full
SELECT/INSERT/UPDATE/DELETE. Where the reference wrapper
[[knowledge/subsystems/contrib-postgres_fdw]] bridges SQL→SQL over libpq
and [[knowledge/ideologies/mongo_fdw]] bridges SQL→BSON documents,
`redis_fdw` bridges SQL rows ⇆ **Redis native data structures** (string,
hash, list, set, sorted-set, plus pseudo-types ttl/len/keys/publish) over
the `hiredis` C client (`redis_fdw.c:40`, `Makefile:8`). Its defining
constraint: Redis has no query language and no relational schema, so a
foreign table declares *which Redis structure it targets* and the FDW
translates each SQL operation into the one or two Redis commands that
structure supports (`README.md:3`, `README.md:88-104`). It is the
key-value / data-structure-store point on the FDW map, and — because
Redis has no transactions in the PG sense — the *non-transactional writes*
point as well.

## How it hooks into PG

Standard FDW plumbing: `redis_fdw_handler` fills an `FdwRoutine`
(`redis_fdw.c:1086-1113`) with the scan callbacks `GetForeignRelSize` /
`GetForeignPaths` / `GetForeignPlan` / `BeginForeignScan` /
`IterateForeignScan` / `ReScanForeignScan` / `EndForeignScan`, and — gated
behind the `-DWRITE_API` compile flag (`Makefile:10`) — the write
callbacks `AddForeignUpdateTargets` / `PlanForeignModify` /
`BeginForeignModify` / `ExecForeignInsert` / `ExecForeignUpdate` /
`ExecForeignDelete` / `EndForeignModify` / `IsForeignRelUpdatable`
(`:1097-1110`). This is the callback set documented in
[[knowledge/idioms/fdw-routine-callbacks]]; the scan loop is the classic
[[knowledge/idioms/fdw-iterate-scan]] shape, materialising one slot per
`redisIterateForeignScan` call (`redis_fdw.c:2508`). The SQL wiring is a
two-function install script (`redis_fdw--1.0.sql:1-13`).

**Connection bootstrap.** There is no library-global init (`_PG_init` is
absent) and no connection cache. `redis_do_connect` opens a *fresh*
`redisContext` on demand via `redisConnectUnixWithTimeout` (host starting
`/` → unix socket) or `redisConnectWithTimeout` (`redis_fdw.c:2108-2112`),
then issues `AUTH <password>` (`:2124`) and `SELECT <database>` (`:2136`)
inline. Foreign-table options are validated per catalog by
`redis_is_valid_opt` against a static `valid_options[]` table
(`:242-264`): `host`/`port`/`timeout` on the SERVER, `password` on the
USER MAPPING, `database`/`key`/`channel`/`keyprefix`/`tabletype`/`readonly`
on the FOREIGN TABLE, and the per-column `redis` remap option on the
ATTRIBUTE. `tabletype` is mandatory and selects one of the ten
`enum redis_data_type` values (`:270-283`).

## Where it diverges from core idioms

- **THE LOAD-BEARING STORY: the table's row shape must match the declared
  Redis structure.** A foreign table is not a generic key-value view — its
  columns are positionally meaningful and `validate_redis_opts`
  (`redis_fdw.c:1510-1602`) rejects any table whose columns don't match its
  `tabletype`: a `string` table needs a `value` column (`:1530`); `hash`
  needs `field`+`value` (`:1538`); `list` needs `value`+`index` (`:1553`);
  `set` needs `member` (`:1561`); `zset` needs `score`+`member`+`index`
  (`:1575`); `ttl` needs `expiry` (`:1582`); `publish` needs `message`
  (`:1590`). Column *identity* is by name (`FIELD_NAMES[]`, `:324-345`),
  remappable per-column with `OPTIONS (redis 'value')` when the SQL name
  differs (`README.md:57-67`). Columns are resolved to fixed slots in
  `struct redis_table` (`:419-438`), which holds an integer index per role
  (`key`, `field`, `member`, `score`, `index`, `expiry`, …). This
  structure-per-table discipline has no analogue in postgres_fdw, where any
  table shape maps to a remote SQL relation, and is a *sharper* constraint
  than mongo_fdw's schemaless flattening — here the row shape is dictated by
  the remote's data-structure algebra, not merely reconciled against it.

- **SQL rows map to individual Redis commands, not a query string.** There
  is no deparse of SQL; each operation emits one hiredis command chosen by a
  `switch (rctx->table_type)`. Reads (`redisIterateForeignScan`,
  `:2707-2913`): string→`GET`; hash→`HGETALL` or `HGET key field`;
  list→`LINDEX`/`LRANGE`/`LLEN`; set→`SMEMBERS` or `SISMEMBER`;
  zset→`ZRANK` or `ZRANGE`/`ZRANGEBYSCORE … WITHSCORES`; ttl→`TTL`;
  publish→`PUBSUB NUMSUB`; keys→`KEYS *` (`:2914`). Writes: INSERT →
  `SET`/`HSET`/`RPUSH`/`SADD`/`ZADD`/`EXPIRE`/`PUBLISH`
  (`:3909-4020`); DELETE → `DEL`/`HDEL`/`LREM`/`LPOP`/… (`:4696-4759`).
  Contrast postgres_fdw's `deparse.c`, which emits remote SQL text.

- **Writes are non-transactional side effects that do NOT roll back with
  the PG xact.** The source registers *no* `RegisterXactCallback` and has no
  commit/abort hook `[verified-by-code — grep of the whole file finds no
  XactCallback registration]`. Each `ExecForeignInsert`/`Update`/`Delete`
  fires its Redis command immediately and frees the reply
  (`redis_fdw.c:4030`); `EndForeignModify` only `redisFree`s the connection
  (`:4873-4892`). A `ROLLBACK` in the surrounding PG transaction leaves
  every already-issued `SET`/`SADD`/`DEL` permanently applied in Redis.
  This is the categorical break from every SQL-source FDW, where the remote
  participates in (at least local) transaction semantics. It is inherent:
  Redis MULTI/EXEC is not wired up here at all.

- **No general qual pushdown — only key / index / score filtering.**
  `redisGetForeignPaths` still carries the comment *"we don't support any
  push-down feature"* (`redis_fdw.c:2277`), but `redisGetForeignRelSize`
  does parse a narrow class of WHERE clauses via `redis_parse_where` into
  `pushdown_conds` (`:2245-2259`): text equality on `key`/`field`/`member`,
  integer comparison (`< <= = >= >`) on `index`/`score`, and array-contains
  `@>` (`README.md:265-279`, `redis_op` enum `:356-365`). Anything else
  stays a local recheck: `redisGetForeignPlan` keeps every non-pushed clause
  in `keep_clauses` for PostgreSQL to re-evaluate (`:2349-2363`). Crucially
  the `key` (or `channel`) must be supplied as a constant/parameter or the
  scan errors out — `redisGetForeignRelSize` raises
  `ERRCODE_FDW_DYNAMIC_PARAMETER_VALUE_NEEDED` if `PARAM_KEY` is unset
  (`:2261-2267`) — because without a key there is no Redis command to issue
  (a full keyspace scan is only offered by the explicit `keys` tabletype).

- **The list-DELETE-by-index "rename magic" hack.** Redis has no
  delete-by-list-index primitive, so deleting `WHERE index = N` (N≠0) is
  done by `LSET`-ing that element to a sentinel string
  `":::redis-fdw-marked-for-deletion:::"` and then `LREM`-ing that sentinel
  (`redis_fdw.c:4740-4757`); index 0 uses `LPOP` (`:4727-4730`), and
  delete-by-value uses `LREM key 1 value` (`:4718-4722`). This
  read-modify-write dance to emulate a relational DELETE against a structure
  that only supports value/position removal is the impedance mismatch made
  visible (`README.md:169-172`).

## Notable design decisions

- **RETURNING values are fabricated, not read back.** After a write the FDW
  does not re-fetch from Redis; it builds the returned tuple from the values
  it just sent, filling counters like `scard`/`zcard` with a literal `"0"`
  (`redis_fdw.c:4103-4107`) and echoing the supplied key/field/value
  (`:4060-4119`). RETURNING is a synthetic echo, not a server round-trip.

- **Row-count estimation probes Redis at plan time.**
  `redisGetForeignRelSize` opens a throwaway connection and issues
  `HLEN`/`LLEN`/`SCARD`/`ZCARD` on the keyed structure (or `DBSIZE` when no
  key is bound) to set `baserel->rows` (`redis_fdw.c:2193-2243`), then
  `redisFree`s it (`:2269`) — the scan later reconnects. Startup cost is a
  three-way host heuristic: unix socket = 2, localhost = 10, remote = 25
  (`:2295-2303`).

- **Updatability is gated by option, tabletype, and command.**
  `redisIsForeignRelUpdatable` returns 0 (read-only) when the `readonly`
  option is set or the tabletype is `len`/`hmset`/`mhash`/`keys`, else the
  full `INSERT|UPDATE|DELETE` mask (`redis_fdw.c:4896-4919`). Separately,
  `redisAddForeignUpdateTargets` hard-rejects UPDATE/DELETE on `keys`
  (read-only) and on `publish` (INSERT-only, since it maps to `PUBLISH`)
  (`:3320-3327`). `mhash`/`hmset` (multi-field hash read) is likewise
  read-only (`README.md:141-143`).

- **UPDATE/DELETE identity travels as resjunk columns, not ctid.**
  `redisBeginForeignModify` locates junk attributes named
  `key`/`field`/`index`/`member`/`value` in the subplan tlist via
  `ExecFindJunkAttributeInTlist` (`redis_fdw.c:3757-3766`) — the wrapper
  reconstructs the Redis addressing tuple from these rather than using the
  heap ctid/system-column machinery, since a Redis element has no TID.

- **`expiry` is a universal optional column.** Any table may carry an
  `expiry INT` column; when present, reads prefetch the key's `TTL`
  (`redis_fdw.c:2687-2704`) and writes append an `EXPIRE` after the mutation
  (`:4032-4051`). The dedicated `ttl` tabletype exposes only key+expiry and
  maps INSERT→`EXPIRE`/`PERSIST`, DELETE→`DEL` (`README.md:202-217`).

- **JOINs fail unless the key is a constant/parameter.** Because the planner
  will not hand `redis_fdw` a join qual like `r.key = u.key` as a usable
  key, such joins error; the documented workaround is a scalar subquery
  `WHERE r.key = (SELECT …)` (`README.md:281-303`). This is a direct
  consequence of the "key required to issue any command" rule above.

## Links into corpus

- [[knowledge/subsystems/contrib-postgres_fdw]] — the reference SQL→SQL
  wrapper; the transactional, full-pushdown baseline every divergence above
  is measured against.
- [[knowledge/subsystems/foreign]] — the core SQL/MED / `FdwRoutine`
  infrastructure.
- [[knowledge/idioms/fdw-routine-callbacks]] — the callback set
  `redis_fdw_handler` populates.
- [[knowledge/idioms/fdw-iterate-scan]] — the per-tuple scan-loop shape.
- [[knowledge/subsystems/contrib-file_fdw]] — the read-only, no-pushdown end
  of the FDW spectrum.
- Sibling non-SQL-source FDWs in this corpus:
  [[knowledge/ideologies/mongo_fdw]] (document store — the closest cousin;
  same "non-relational impedance mismatch is the whole game" thesis, but
  documents instead of data-structures and with real connection pooling),
  [[knowledge/ideologies/pgrocks-fdw]] (RocksDB LSM key-value store — the
  other KV point, but embedded rather than networked),
  [[knowledge/ideologies/ogr_fdw]], [[knowledge/ideologies/parquet_s3_fdw]].
  `redis_fdw` is the **key-value / data-structure store, non-transactional
  writes** point on that map.

## Sources

- `https://raw.githubusercontent.com/nahanni/rw_redis_fdw/master/README.md` (200)
- `https://raw.githubusercontent.com/nahanni/rw_redis_fdw/master/redis_fdw.c` (200)
- `https://raw.githubusercontent.com/nahanni/rw_redis_fdw/master/redis_fdw.control` (200)
- `https://raw.githubusercontent.com/nahanni/rw_redis_fdw/master/Makefile` (200)
- `https://raw.githubusercontent.com/nahanni/rw_redis_fdw/master/redis_fdw--1.0.sql` (200)
- No 404s: every probed path (including the Makefile and the `--1.0.sql`
  install file) returned 200.

Confidence: `[verified-by-code]` for the FdwRoutine wiring
(`redis_fdw.c:1086-1113`), the row-shape/tabletype validation
(`:1510-1602`), the per-command read/write dispatch, the per-scan fresh
connection with no cache (`:2101-2151`, `:3250-3269`, `:4873-4892`), the
list-delete rename hack (`:4740-4757`), fabricated RETURNING (`:4060-4119`),
and the updatability gates (`:4896-4919`). The **non-transactional writes**
claim is `[verified-by-code]` by the *absence* of any `RegisterXactCallback`
/ commit hook plus the immediate command-issue-and-free pattern — a
negative finding, so tagged explicitly. Pushdown scope and the JOIN
limitation are `[from-README]` corroborated by the `redis_parse_where`
call-site (`:2245-2259`); the exact set of qual shapes `redis_parse_where`
accepts beyond the cited operator enum was not read line-by-line and its
finer edge cases are `[inferred]`.
