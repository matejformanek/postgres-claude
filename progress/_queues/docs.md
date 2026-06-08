# Queue: pg-docs-miner — official-docs side

Format: `[status] <chapter-slug> <chapter-url>`
Refill rule: re-walk `https://www.postgresql.org/docs/current/index.html`
table of contents, exclude chapters whose slug already exists under
`knowledge/docs-distilled/`.

## Entries (internals-heavy chapters first)

[done:a49dd51] storage https://www.postgresql.org/docs/current/storage.html
[done:c34e6da] mvcc https://www.postgresql.org/docs/current/mvcc.html
[done:19c6e24] wal https://www.postgresql.org/docs/current/wal.html
[done:19c6e24] indexes-types https://www.postgresql.org/docs/current/indexes-types.html
[done:1aa5183] gist https://www.postgresql.org/docs/current/gist.html
[done:19c6e24] gin https://www.postgresql.org/docs/current/gin.html
[done:19c6e24] brin https://www.postgresql.org/docs/current/brin.html
[done:1aa5183] spgist https://www.postgresql.org/docs/current/spgist.html
[done:1aa5183] runtime-config-wal https://www.postgresql.org/docs/current/runtime-config-wal.html
[done:1aa5183] runtime-config-replication https://www.postgresql.org/docs/current/runtime-config-replication.html
[done:19c6e24] parallel-query https://www.postgresql.org/docs/current/parallel-query.html
[done:f53b7bf] planner-stats https://www.postgresql.org/docs/current/planner-stats.html
[done:f53b7bf] performance-tips https://www.postgresql.org/docs/current/performance-tips.html
[done:f53b7bf] xfunc-c https://www.postgresql.org/docs/current/xfunc-c.html
[done:19c6e24] bgworker https://www.postgresql.org/docs/current/bgworker.html

## Refill 2026-06-06 (re-walk of internals.html ToC — Part VII chapters without a docs-distilled/<slug>.md; per-catalog/per-view reference pages excluded as reference, not internals prose)

[done:a9c263b] overview https://www.postgresql.org/docs/current/overview.html
[done:a9c263b] tableam https://www.postgresql.org/docs/current/tableam.html
[done:a9c263b] indexam https://www.postgresql.org/docs/current/indexam.html
[done:a9c263b] bki https://www.postgresql.org/docs/current/bki.html
[done:a9c263b] transactions https://www.postgresql.org/docs/current/transactions.html
[done:a9c263b] protocol-flow https://www.postgresql.org/docs/current/protocol-flow.html
[done:b91492b] custom-scan https://www.postgresql.org/docs/current/custom-scan.html
[done:b91492b] geqo https://www.postgresql.org/docs/current/geqo.html
[done:b91492b] fdwhandler https://www.postgresql.org/docs/current/fdwhandler.html
[done:b91492b] tablesample-method https://www.postgresql.org/docs/current/tablesample-method.html
[done:b91492b] plhandler https://www.postgresql.org/docs/current/plhandler.html
[done:b91492b] source https://www.postgresql.org/docs/current/source.html
[done:b91492b] storage-toast https://www.postgresql.org/docs/current/storage-toast.html
[done:b91492b] storage-vm https://www.postgresql.org/docs/current/storage-vm.html
[done:b91492b] storage-hot https://www.postgresql.org/docs/current/storage-hot.html
[done:b91492b] wal-for-extensions https://www.postgresql.org/docs/current/wal-for-extensions.html
[pending] hash-index https://www.postgresql.org/docs/current/hash-index.html
[pending] planner-stats-details https://www.postgresql.org/docs/current/planner-stats-details.html
