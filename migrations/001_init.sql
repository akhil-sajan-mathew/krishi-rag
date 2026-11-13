CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  publisher     TEXT,
  url           TEXT,
  category      TEXT,
  page_count    INT,
  ingested_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id            BIGSERIAL PRIMARY KEY,
  document_id   TEXT REFERENCES documents(id) ON DELETE CASCADE,
  page_start    INT NOT NULL,
  page_end      INT NOT NULL,
  chunk_index   INT NOT NULL,
  text          TEXT NOT NULL,
  token_count   INT,
  embedding     vector(384),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  config        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_config_idx ON chunks (config);
