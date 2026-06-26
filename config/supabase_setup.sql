-- config/supabase_setup.sql
-- Run in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query -> Run).
-- Reproducible by design: it drops and recreates the vector stores, so the
-- schema is ALWAYS correct (avoids the "create if not exists keeps a stale
-- table" trap). This WIPES the embeddings - re-run the two loaders afterward.

-- 1. Enable pgvector (vector type + similarity operators).
create extension if not exists vector;


-- 2. SCHEMA STORE -------------------------------------------------------------
drop function if exists match_schema_chunks(vector, integer);
drop table if exists schema_chunks cascade;

create table schema_chunks (
    id          bigint generated always as identity primary key,
    table_name  text not null,
    chunk_text  text not null,
    embedding   vector(1536)          -- dims of text-embedding-3-small
);

create index schema_chunks_embedding_idx
    on schema_chunks using hnsw (embedding vector_cosine_ops);

create function match_schema_chunks(
    query_embedding vector(1536),
    match_count int default 5
)
returns table (table_name text, chunk_text text, similarity float)
language sql stable
as $$
    select
        sc.table_name,
        sc.chunk_text,
        1 - (sc.embedding <=> query_embedding) as similarity
    from schema_chunks sc
    order by sc.embedding <=> query_embedding
    limit match_count;
$$;


-- 3. GLOSSARY STORE -----------------------------------------------------------
drop function if exists match_glossary_chunks(vector, integer);
drop table if exists glossary_chunks cascade;

create table glossary_chunks (
    id          bigint generated always as identity primary key,
    term        text not null,
    sql_hint    text not null,
    chunk_text  text not null,
    embedding   vector(1536)
);

create index glossary_chunks_embedding_idx
    on glossary_chunks using hnsw (embedding vector_cosine_ops);

create function match_glossary_chunks(
    query_embedding vector(1536),
    match_count int default 5
)
returns table (term text, sql_hint text, chunk_text text, similarity float)
language sql stable
as $$
    select
        gc.term,
        gc.sql_hint,
        gc.chunk_text,
        1 - (gc.embedding <=> query_embedding) as similarity
    from glossary_chunks gc
    order by gc.embedding <=> query_embedding
    limit match_count;
$$;


-- =============================================================================
-- PHASE 3 additions: the query-history store (learned few-shot examples)
-- NOTE: drop-and-recreate is used here for a clean first setup. ONCE this store
-- is accumulating real history you care about, change the table to
-- `create table if not exists` so re-running setup does not erase it.
-- =============================================================================

do $$
declare fn record;
begin
  for fn in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where p.proname = 'match_query_history' and n.nspname = 'public'
  loop execute 'drop function if exists ' || fn.sig || ' cascade'; end loop;
end $$;

drop table if exists query_history cascade;

create table query_history (
    id          bigint generated always as identity primary key,
    question    text not null,
    sql_text    text not null,
    embedding   vector(1536)
);

create index query_history_embedding_idx
    on query_history using hnsw (embedding vector_cosine_ops);

create function match_query_history(
    query_embedding vector(1536),
    match_count int default 3
)
returns table (question text, sql_text text, similarity float)
language sql stable
as $$
    select qh.question, qh.sql_text,
           1 - (qh.embedding <=> query_embedding) as similarity
    from query_history qh
    order by qh.embedding <=> query_embedding
    limit match_count;
$$;