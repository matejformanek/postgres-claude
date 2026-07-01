-- Workload 4: exercise multiple historically-leaky subsystems in ONE backend
-- session so `leaks <backend_pid>` against the debug build can probe.
-- Subsystems hit: parser, planner, executor, catalog cache, JSONPath, regex,
-- PL/pgSQL, plan cache, expression eval, sort, aggregation, hash join.
--
-- Run: psql -h /tmp -d postgres -X -f diverse-subsystems.sql

\set ON_ERROR_STOP off

-- Pre snapshot
\copy (SELECT name, ident, type, level, total_bytes, total_nblocks, used_bytes, free_bytes, free_chunks FROM pg_backend_memory_contexts ORDER BY name, level) TO 'planning/memory-hunt/evidence/wl4-pre.csv' CSV HEADER

\copy (SELECT pg_backend_pid()) TO 'planning/memory-hunt/evidence/wl4-pid.txt'

-- ===== JSONPath stress =====
DO $$
DECLARE i int; b boolean; r jsonb;
BEGIN
  FOR i IN 1..1000 LOOP
    SELECT '{"a":[1,2,3,{"b":"deep","c":[10,20,30]}],"x":"hello"}'::jsonb @? '$.a[*].c ? (@ > 15)' INTO b;
    SELECT jsonb_path_query_array('{"a":[1,2,3,{"b":"deep","c":[10,20,30]}]}'::jsonb, '$.a[*] ? (@.type() == "number")') INTO r;
    SELECT jsonb_path_exists('{"x":[{"y":1},{"y":2}]}'::jsonb, '$.x[*].y ? (@ > 0)') INTO b;
  END LOOP;
END $$;

-- ===== Regex stress =====
DO $$
DECLARE i int; t text;
BEGIN
  FOR i IN 1..1000 LOOP
    SELECT regexp_replace('the quick brown fox jumps over the lazy dog', '\m(quick|brown|fox)\M', '[\1]', 'g') INTO t;
    SELECT (regexp_matches('hello-world-foo-bar-baz', '(\w+)-(\w+)-(\w+)', 'g'))[1] INTO t;
    SELECT regexp_split_to_array('one,two;three:four|five', '[,;:|]') INTO t;
  END LOOP;
END $$;

-- ===== PL/pgSQL nested / EXCEPTION stress =====
DO $$
DECLARE i int; sum int := 0;
BEGIN
  FOR i IN 1..500 LOOP
    BEGIN
      sum := sum + i;
      IF i % 17 = 0 THEN
        RAISE EXCEPTION 'sample %', i;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      sum := sum - 1;
    END;
  END LOOP;
END $$;

-- ===== Plan cache stress (prepared statements with parameters) =====
PREPARE pq1(int) AS SELECT count(*) FROM pg_class WHERE oid::int < $1;
DO $$
DECLARE i int; n bigint;
BEGIN
  FOR i IN 1..1000 LOOP
    EXECUTE format('EXECUTE pq1(%s)', 100000 + i) INTO n;
  END LOOP;
END $$;
DEALLOCATE pq1;

-- ===== CTE + window + aggregate =====
WITH src AS (
  SELECT g AS x, g % 7 AS bucket FROM generate_series(1, 10000) g
), agg AS (
  SELECT bucket, sum(x), avg(x), (array_agg(x ORDER BY x DESC))[1:5] AS top5 FROM src GROUP BY bucket
)
SELECT bucket, sum, row_number() OVER (ORDER BY sum) FROM agg;

-- ===== Sort / hash join (force off-disk) =====
SET work_mem = '64kB';
SELECT count(*) FROM (
  SELECT a.g AS x, b.g AS y
  FROM generate_series(1, 5000) a(g) JOIN generate_series(1, 5000) b(g) ON a.g = b.g
) z;
SELECT count(*) FROM (
  SELECT g, md5(g::text), generate_series(1, 3) AS k FROM generate_series(1, 1000) g
  ORDER BY md5(g::text)
) z;
RESET work_mem;

-- ===== XML (if compiled) =====
DO $$ BEGIN
  PERFORM xpath('/r/a/text()', '<r><a>1</a><a>2</a><a>3</a></r>'::xml);
EXCEPTION WHEN feature_not_supported THEN NULL;
END $$;

-- ===== Post snapshot =====
\copy (SELECT name, ident, type, level, total_bytes, total_nblocks, used_bytes, free_bytes, free_chunks FROM pg_backend_memory_contexts ORDER BY name, level) TO 'planning/memory-hunt/evidence/wl4-post.csv' CSV HEADER

\echo === workload complete; sleeping 25s for leaks probe ===
SELECT pg_sleep(25);
