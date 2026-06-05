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
[in-progress:cloud/pg-docs-miner/2026-06-04] gist https://www.postgresql.org/docs/current/gist.html
[done:19c6e24] gin https://www.postgresql.org/docs/current/gin.html
[done:19c6e24] brin https://www.postgresql.org/docs/current/brin.html
[in-progress:cloud/pg-docs-miner/2026-06-04] spgist https://www.postgresql.org/docs/current/spgist.html
[in-progress:cloud/pg-docs-miner/2026-06-04] runtime-config-wal https://www.postgresql.org/docs/current/runtime-config-wal.html
[in-progress:cloud/pg-docs-miner/2026-06-04] runtime-config-replication https://www.postgresql.org/docs/current/runtime-config-replication.html
[done:19c6e24] parallel-query https://www.postgresql.org/docs/current/parallel-query.html
[pending] planner-stats https://www.postgresql.org/docs/current/planner-stats.html
[pending] performance-tips https://www.postgresql.org/docs/current/performance-tips.html
[pending] xfunc-c https://www.postgresql.org/docs/current/xfunc-c.html
[done:19c6e24] bgworker https://www.postgresql.org/docs/current/bgworker.html
