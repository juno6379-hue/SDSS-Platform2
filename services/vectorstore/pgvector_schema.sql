CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS climate_documents (
    document_id text PRIMARY KEY,
    source_id text NOT NULL,
    dataset_id text NOT NULL,
    version text NOT NULL,
    source_uri text NOT NULL,
    sha256 char(64) NOT NULL,
    authority text NOT NULL,
    license text NOT NULL,
    access text NOT NULL CHECK (access IN ('public', 'restricted', 'private')),
    allowed_roles text[] NOT NULL DEFAULT '{}',
    valid_from date NOT NULL,
    valid_until date,
    acquired_at timestamptz NOT NULL,
    UNIQUE (source_id, dataset_id, version, sha256)
);

CREATE TABLE IF NOT EXISTS climate_chunks (
    chunk_id text PRIMARY KEY,
    document_id text NOT NULL REFERENCES climate_documents(document_id),
    language text NOT NULL CHECK (language IN ('ko', 'id', 'en')),
    text text NOT NULL,
    source_start integer NOT NULL,
    source_end integer NOT NULL CHECK (source_end > source_start),
    geography_ids text[] NOT NULL DEFAULT '{}',
    spatial_coverage geometry(Geometry, 4326),
    start_year integer,
    end_year integer,
    variable text,
    scenario text,
    climate_model text,
    claim_authority text NOT NULL,
    embedding_model text NOT NULL,
    embedding vector(768) NOT NULL,
    metadata jsonb NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);

CREATE INDEX IF NOT EXISTS idx_climate_chunks_embedding
    ON climate_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_climate_chunks_tsv ON climate_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_climate_chunks_geometry ON climate_chunks USING gist (spatial_coverage);
CREATE INDEX IF NOT EXISTS idx_climate_chunks_filters
    ON climate_chunks (variable, scenario, climate_model, start_year, end_year);
