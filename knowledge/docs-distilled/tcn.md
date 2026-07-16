---
source_url: https://www.postgresql.org/docs/current/tcn.html
fetched_at: 2026-07-16
anchor_sha: 572c3b2ddf8c
module: contrib/tcn
---

# tcn — Triggered Change Notification

A one-function contrib module: a generic `AFTER … FOR EACH ROW` trigger that
emits a `NOTIFY` carrying the operation type + primary-key of the changed row,
so a `LISTEN`ing client can invalidate a cache without polling. Trusted
extension (installable by a non-superuser holding `CREATE` on the database).

## Non-obvious claims

- The trigger function is `triggered_change_notification()`; it **must** be an
  `AFTER` trigger, `FOR EACH ROW`, and the table **must have a primary key** —
  all three are hard `errmsg` checks, not documentation-only advice.
  `[verified-by-code source/contrib/tcn/tcn.c:80,86,92,181]`
- The channel name is the trigger's single optional argument; with zero
  arguments it defaults to the literal `"tcn"`. More than one argument is a
  hard error. `[verified-by-code source/contrib/tcn/tcn.c:111,114,116]`
- Operation is encoded as one letter: `I` / `U` / `D` for
  INSERT/UPDATE/DELETE; any other trigger op is `elog(ERROR)` (with a
  `'X'` assignment purely to silence the compiler). This means tcn is
  meaningless on TRUNCATE (statement-level) — it only ever fires per-row.
  `[verified-by-code source/contrib/tcn/tcn.c:95-103]`
- Payload grammar is: `"<tablename>",<op>,"<pkcol>"='<pkval>'[,…]` — table
  and column **names** are double-quoted, **values** are single-quoted, and
  embedded quote characters are **doubled** by the local `strcpy_quoted`
  helper (`appendStringInfoCharMacro(r,q)` on match). This is the same
  doubling convention SQL uses for quoted identifiers/literals.
  `[verified-by-code source/contrib/tcn/tcn.c:36-46,153-165]`
- Example emitted payload (composite PK `(a int, b date)`):
  `"tcndata",I,"a"='1',"b"='2012-12-22'` — one `col='val'` pair **per PK
  column**, in PK-index attribute order (the code walks the primary-key
  index's `indnatts`, not the table's column order).
  `[from-README][verified-by-code source/contrib/tcn/tcn.c:153-165]`
- Delivery is via `Async_Notify(channel, payload.data)` — i.e. it rides the
  standard LISTEN/NOTIFY async-notification queue, so it is **transactional**:
  the notify is only delivered if the enclosing transaction commits, and
  duplicate identical (channel,payload) notifies in one transaction collapse
  per normal NOTIFY dedup rules. `[verified-by-code source/contrib/tcn/tcn.c:168]`
- Only the **primary key** is sent, never the changed non-key columns — the
  design assumes the listener re-reads the row by PK. This keeps the payload
  small and within the 8000-byte NOTIFY payload limit for wide rows.
  `[inferred][from-README]`

## Worked example (from the docs page)

```sql
CREATE TABLE tcndata (a int NOT NULL, b date NOT NULL, c text,
                      PRIMARY KEY (a, b));
CREATE TRIGGER tcndata_tcn_trigger
  AFTER INSERT OR UPDATE OR DELETE ON tcndata
  FOR EACH ROW EXECUTE FUNCTION triggered_change_notification();
LISTEN tcn;
INSERT INTO tcndata VALUES (1, date '2012-12-22', 'one');
-- Asynchronous notification "tcn" with payload
--   "tcndata",I,"a"='1',"b"='2012-12-22'
```

## Links into corpus

- LISTEN/NOTIFY async-notification machinery (`Async_Notify`, commit-time
  delivery, dedup): the async queue lives in `src/backend/commands/async.c`.
  See `[[knowledge/subsystems/…]]` if/when an async-notify subsystem doc
  exists; currently uncited in corpus.
- Trigger-firing model + `TriggerData` / `TRIGGER_FIRED_BY_*` macros used by
  the op-letter branch: `[[knowledge/docs-distilled/trigger-interface.md]]`,
  `[[knowledge/docs-distilled/trigger-definition.md]]`.
- SPI accessors (`SPI_getvalue`, `NameStr(attr->attname)`) used to extract PK
  values: `[[knowledge/docs-distilled/spi.md]]`.
