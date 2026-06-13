---
path: src/interfaces/ecpg/ecpglib/connect.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 746
depth: deep
---

# `connect.c` — ecpglib connection lifecycle, the connection list, and thread-local "current connection"

## Purpose

This file implements the runtime connection machinery for ECPG (embedded SQL
in C) programs. It owns the global singly-linked list of open `struct
connection`s (`all_connections`), the notion of the "current"/"actual"
connection (both a process-global default and a per-thread thread-specific
value), and the pthread mutex that serialises list mutation. It exposes
`ECPGconnect`/`ECPGdisconnect`/`ECPGsetconn`/`ECPGsetcommit` (the symbols the
ECPG preprocessor emits calls to) plus internal accessors used across ecpglib.
`ECPGconnect` parses the various ECPG connection-target syntaxes (old-style
`dbname@host:port`, new-style `<tcp|unix>:postgresql://...`, INFORMIX
`PG_DBPATH`) into a libpq keyword/value array and calls `PQconnectdbParams`
(connect.c:649).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void ecpg_pthreads_init(void)` | connect.c:30 | One-time `pthread_once` init of the TSD key for the actual connection [verified-by-code connect.c:32]. |
| `struct connection *ecpg_get_connection(const char *connection_name)` | connect.c:76 | Public lookup. Locks `connections_mutex` only for the named-lookup path; the CURRENT/NULL path reads TSD + global lock-free (connect.c:80-102). |
| `bool ECPGsetcommit(int lineno, const char *mode, const char *connection_name)` | connect.c:158 | Toggles autocommit; issues `begin transaction`/`commit` via `PQexec` to match new state (connect.c:168-189). |
| `bool ECPGsetconn(int lineno, const char *connection_name)` | connect.c:195 | Sets the thread's current connection via `pthread_setspecific` (connect.c:202). |
| `bool ECPGconnect(...)` | connect.c:260 | The main entry: parses target, builds keyword/value arrays, `PQconnectdbParams`, links into list. |
| `bool ECPGdisconnect(int lineno, const char *connection_name)` | connect.c:693 | Closes one named connection or `ALL` under the mutex (connect.c:705-731). |
| `PGconn *ECPGget_PGconn(const char *connection_name)` | connect.c:737 | Returns the raw libpq `PGconn *` for a connection, or NULL. |
| `locale_t ecpg_clocale` | connect.c:14 | Global "C" locale (HAVE_USELOCALE only); lazily created under the mutex in `ECPGconnect` (connect.c:511-513). |

## Internal landmarks

- **Module statics (connect.c:17-21):** `connections_mutex`
  (`PTHREAD_MUTEX_INITIALIZER`), `actual_connection_key` (pthread TSD key),
  `actual_connection_key_once` (pthread_once guard), `actual_connection`
  (process-global default), `all_connections` (head of the singly-linked list).
- **Two-tier "current connection" model:** the CURRENT/NULL path reads the
  thread-specific `actual_connection_key`, and only if that is NULL falls back
  to the process-global `actual_connection` (connect.c:44-53, 84-93). The
  comment explicitly says the global-fallback case trusts the user to provide
  their own mutex (connect.c:46-50) [from-comment].
- **`ecpg_get_connection_nr` (connect.c:36):** the unlocked core lookup. Walks
  `all_connections` comparing `con->name`. Skips entries whose `name` is NULL
  (NULL-name connections, created when no dbname is given) (connect.c:66)
  [verified-by-code]. Callers must already hold `connections_mutex` for the
  named path — `ECPGdisconnect` calls it under the lock (connect.c:720),
  `ecpg_get_connection` takes the lock around it (connect.c:97-101).
- **`ecpg_finish` (connect.c:108):** the teardown helper. `PQfinish`es the
  libpq conn, unlinks `act` from `all_connections`, repoints both the TSD
  current and the global `actual_connection` to `all_connections` if they
  pointed at the victim (connect.c:135-138), frees the type cache, name, and
  the struct. When the last connection closes it also frees the global cursor
  variable list `ivlist` (connect.c:146-151). Comment states the caller always
  holds `connections_mutex` (connect.c:118-121) [from-comment].
- **`ECPGnoticeReceiver` (connect.c:208):** libpq notice hook installed at
  connect.c:687. Maps a handful of SQLSTATEs to legacy ECPG SQLCODE warnings
  and writes them into the thread's `sqlca` (connect.c:235-255).
- **`ECPGconnect` connection-target parsing (connect.c:331-447):** handles
  `tcp:`/`unix:` + `postgresql://` URL form and old-style
  `dbname@host:port`, incrementing `connect_params` per component so the
  keyword/value arrays can be sized (connect.c:468-469).
- **Options splitting (connect.c:604-643):** scribbles in-place on the
  `options` string to split `keyword=value&...` pairs into the libpq arrays.

## Invariants & gotchas

- **`connections_mutex` guards list mutation AND the lazy `ecpg_clocale`
  init.** `ECPGconnect` creates `ecpg_clocale` only while holding the mutex,
  relying on the lock to make it single-threaded (connect.c:507-513)
  [from-comment]. Don't move clocale init out of the locked region.
- **Lock discipline is caller-dependent and asymmetric.**
  `ecpg_get_connection_nr` and `ecpg_finish` assume the caller holds the mutex;
  `ecpg_get_connection`'s CURRENT/NULL branch deliberately runs lock-free. A
  future refactor that funnels everything through one locked path could
  deadlock (the mutex is non-recursive) — e.g. `ECPGconnect` calls
  `ecpg_get_connection` (connect.c:317) BEFORE taking the mutex (connect.c:504),
  and `ecpg_finish` (connect.c:670) is called WHILE holding it. Calling the
  public locking `ecpg_get_connection` from inside the locked region would
  self-deadlock [inferred].
- **`alloc_failed` accumulator pattern:** `ecpg_strdup` takes `&alloc_failed`
  and ORs in failures; the code defers the OOM check to batch points
  (connect.c:277, 481-501) rather than checking each strdup. Preserve this — a
  partial early return would leak the already-strdup'd fields.
- **`this->autocommit` is set AFTER the mutex is released** (connect.c:683-685),
  as is `PQsetNoticeReceiver` (connect.c:687). The connection is already linked
  and visible to other threads at that point; a concurrent thread selecting
  this connection by name could observe it before autocommit/notice-receiver
  are set [inferred].
- **`free(this)` vs `ecpg_free(this->name)`:** the struct itself is released
  with bare `free()` on the early-error paths (connect.c:404, 499, 535) while
  its fields use `ecpg_free`. Intentional (the struct came from `ecpg_alloc`
  but is freed before being fully owned) but easy to get wrong when editing.

## Cross-refs

- [[execute.c]] — statement execution against `struct connection`.
- [[misc.c]] — `ecpg_init`, `ecpg_log`, `ecpg_raise`, sqlca handling, `ivlist`.
- [[memory.c]] — `ecpg_alloc`/`ecpg_strdup`/`ecpg_free`/`ecpg_clear_auto_mem`.
- [[prepare.c]] — `prep_stmts` list per connection.
- [[descriptor.c]], [[data.c]] — type cache (`ECPGtype_information_cache`).
- `ecpglib_extern.h` — declares `struct connection`, `ivlist`,
  `ecpg_internal_regression_mode`.

## Potential issues

- **[ISSUE-question: list-walk on a possibly-empty list in `ecpg_finish`]**
  `connect.c:130` — `for (con = all_connections; con->next && con->next != act; ...)`
  dereferences `con->next` with `con` starting at `all_connections`. This is
  reached only in the `else` of `act == all_connections` (connect.c:124), so
  `all_connections != act`, and since `act` is on the list `all_connections` is
  non-NULL — safe in practice. But there is no explicit guard, so a future
  caller invoking `ecpg_finish` on a `struct connection` not actually on
  `all_connections` would walk to the tail and harmlessly fall through (the
  `if (con->next)` at connect.c:131 protects the unlink). Low severity; worth a
  comment. [inferred]

- **[ISSUE-undocumented-invariant: notice receiver set after unlock]**
  `connect.c:683-687` — `PQsetNoticeReceiver` and `this->autocommit =` run
  after `pthread_mutex_unlock`, while the connection is already linked and
  name-discoverable by other threads (linked at connect.c:549). No comment
  notes that callers must not concurrently use a just-returned-but-not-yet-
  finalized connection. ECPG's threading contract (one connection per thread
  unless the app self-synchronises) likely makes this benign, but the ordering
  is an unstated invariant. Low severity. [inferred]
