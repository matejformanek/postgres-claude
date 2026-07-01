-- Reproducer for commit 5a2043bf713
-- "Fix transient memory leakage in jsonpath evaluation."
--
-- Tom Lane's commit-message reproducer:
--   SELECT jsonb_path_query((SELECT jsonb_agg(i) FROM generate_series(1,10000) i),
--                           '$[*] ? (@ < $)');
-- Pre-fix: ~6GB, quadratic memory in input array length.
-- Post-fix: static.
--
-- Scaled down to 2000 elements so we can finish in seconds and see the
-- pattern via pg_backend_memory_contexts sampling.

\set ON_ERROR_STOP on
\timing on

\echo === pre-query snapshot ===
\copy (SELECT name, ident, type, level, total_bytes FROM pg_backend_memory_contexts WHERE name LIKE 'Executor%' OR name LIKE 'Expr%' OR name = 'MessageContext' OR name = 'PortalContext' OR name = 'TopMemoryContext' OR name LIKE '%json%' OR name = 'JSON_PATH' OR name LIKE 'PortalHeapMem%' ORDER BY level, name) TO 'planning/memory-hunt/evidence/jsonpath/pre.csv' CSV HEADER

-- The reproducer — small enough that pre-fix is ~10-30s, post-fix is <1s.
SELECT count(*) FROM (
  SELECT jsonb_path_query(
    (SELECT jsonb_agg(i) FROM generate_series(1, 2000) i),
    '$[*] ? (@ < $)'
  )
) z;

\echo === post-query snapshot ===
\copy (SELECT name, ident, type, level, total_bytes FROM pg_backend_memory_contexts WHERE name LIKE 'Executor%' OR name LIKE 'Expr%' OR name = 'MessageContext' OR name = 'PortalContext' OR name = 'TopMemoryContext' OR name LIKE '%json%' OR name = 'JSON_PATH' OR name LIKE 'PortalHeapMem%' ORDER BY level, name) TO 'planning/memory-hunt/evidence/jsonpath/post.csv' CSV HEADER

-- ALL contexts (everything, for forensic post-mortem)
\copy (SELECT name, ident, type, level, total_bytes FROM pg_backend_memory_contexts ORDER BY total_bytes DESC) TO 'planning/memory-hunt/evidence/jsonpath/all.csv' CSV HEADER

\echo === backend RSS at end (via /proc/self/status approximation) ===
SELECT pg_backend_pid() AS backend_pid;
