# contrib-dblink (cross-database SQL calls)

- **Source path:** `source/contrib/dblink/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `dblink.control`)
- **Trusted:** no (network access required)

## 1. Purpose

Execute SQL queries against a remote PostgreSQL database from
within a backend. Predates `postgres_fdw` and is now mostly
superseded by it, BUT remains relevant for:

- **One-shot remote query** without setting up a FOREIGN
  TABLE.
- **Asynchronous-style** patterns (`dblink_send_query` +
  `dblink_get_result`).
- **Legacy schemas** built before `postgres_fdw` (PG 9.3+).

Single 3272-LOC file [verified-by-code `wc -l
source/contrib/dblink/dblink.c`].

## 2. The connection model

Two connection styles:

- **Named, persistent**:
  ```sql
  SELECT dblink_connect('myconn', 'dbname=remote host=otherhost');
  SELECT * FROM dblink('myconn', 'SELECT * FROM t')
                 AS x(a int, b text);
  SELECT dblink_disconnect('myconn');
  ```
- **Anonymous, per-call** (no name):
  ```sql
  SELECT * FROM dblink('dbname=remote host=otherhost',
                       'SELECT * FROM t')
                 AS x(a int, b text);
  ```

Named connections are reused across function calls (within a
backend's lifetime). Anonymous connections incur the connect
overhead per call.

## 3. Core entry points

[verified-by-code `dblink.c:283-1279`]

| Function | Purpose |
|---|---|
| `dblink_connect(name, connstr)` | Open connection |
| `dblink_disconnect(name)` | Close connection |
| `dblink(connstr, sql)` | Synchronous query, returns SETOF record |
| `dblink_exec(connstr, sql)` | Execute non-result SQL |
| `dblink_open(name, cursorname, sql)` | Open server-side cursor |
| `dblink_fetch(name, cursorname, count)` | Fetch from cursor |
| `dblink_close(name, cursorname)` | Close cursor |
| `dblink_send_query(name, sql)` | Start async query |
| `dblink_get_result(name)` | Block on async result |
| `dblink_get_connections()` | List active named connections |

The cursor variants let large result sets stream rather than
materialize.

## 4. The async pattern

```sql
SELECT dblink_send_query('conn', 'SELECT slow_query()');
-- ... do other work ...
SELECT * FROM dblink_get_result('conn') AS r(...);
```

The query runs on the remote while the local backend
continues. `dblink_get_result` blocks until the remote
finishes. Useful for fan-out queries (start N remote
queries, collect them all).

## 5. The record-type problem

dblink queries return `SETOF record`. The caller MUST supply
an explicit column list:

```sql
SELECT * FROM dblink('...', 'SELECT id, name FROM t')
              AS x(id int, name text);
```

The `AS x(...)` is **required** — PG can't infer the column
types from the dynamic SQL. If the actual result doesn't match
the declared types, you get a runtime error.

## 6. Permission model

- **`USAGE on FOREIGN SERVER`** required for declared servers
  (rare with dblink; usual with postgres_fdw).
- For ad-hoc connstrings, the **dblink role membership**
  controls access. The `pg_read_server_files` consideration
  doesn't apply (no filesystem); but the connstring may
  expose remote credentials, so dblink is a network-security
  concern.

## 7. Transaction semantics

- **Each dblink query runs in its OWN transaction** on the
  remote. There's no two-phase commit by default.
- **`dblink_exec` followed by a local rollback** does NOT
  roll back the remote — the remote has already committed.
- For consistent cross-database semantics, layer on top with
  prepared-transaction protocols.

## 8. dblink vs postgres_fdw

| Concern | dblink | postgres_fdw |
|---|---|---|
| Setup | Per-call connstring | One-time FOREIGN SERVER |
| Query syntax | Function call returning record | Standard SELECT against foreign table |
| Type inference | Manual `AS x(...)` | From FOREIGN TABLE definition |
| Pushdown | No | Yes (WHERE, JOIN, aggregates) |
| Async | Yes (dblink_send_query) | No |
| Performance | Lower (more setup per call) | Higher (declared connection pool) |

Modern use: postgres_fdw for declared cross-database access;
dblink for one-shot or async patterns.

## 9. Production-use guidance

- **Use named connections** for repeated access in the same
  backend session.
- **Use postgres_fdw** for permanent cross-database
  schemas.
- **Use dblink_send/get_result** when fanning out to many
  remote queries in parallel.
- **Be aware of the 1-xact-per-call rule.** dblink can't
  participate in the caller's transaction.

## 10. Invariants

- **[INV-1]** Each dblink query runs in its own remote
  transaction; no cross-database 2PC by default.
- **[INV-2]** Result-set caller must supply column types.
- **[INV-3]** Named connections survive function-call
  boundaries (backend-local).
- **[INV-4]** Async = `dblink_send_query` + `dblink_get_result`.
- **[INV-5]** dblink is the function-call sibling of
  postgres_fdw's foreign-table sibling.

## 11. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/dblink/dblink.c | head -25`
- Connection management:
  `grep -n 'getConnectionByName\|StoreNewConnection' source/contrib/dblink/dblink.c | head -10`
- Async path:
  `grep -n 'dblink_send_query\|dblink_get_result\|PQsendQuery' source/contrib/dblink/dblink.c | head -10`

## 12. Cross-references

- `knowledge/subsystems/contrib-postgres_fdw.md` — modern
  alternative for permanent foreign-database access.
- `knowledge/subsystems/foreign.md` — FDW subsystem at
  large.
- `knowledge/subsystems/libpq-backend.md` — the libpq
  client library dblink uses internally.
- `.claude/skills/fmgr-and-spi.md` — dblink uses SPI patterns
  internally to expose remote results as record sets.
- `source/contrib/dblink/dblink.c` — implementation.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/dblink/dblink.c`](../files/contrib/dblink/dblink.c.md) |

<!-- /files-owned:auto -->
