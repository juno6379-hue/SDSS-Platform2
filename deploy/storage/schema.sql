CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA sdss_storage;
REVOKE ALL ON SCHEMA sdss_storage FROM PUBLIC;

CREATE TABLE sdss_storage.lineage_node (
    institution text NOT NULL CHECK (institution ~ '^[a-z][a-z0-9-]{0,62}$'),
    kind text NOT NULL CHECK (kind IN ('dataset', 'model', 'job', 'result')),
    node_key text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    coverage public.geometry(Geometry, 4326)
        CHECK (coverage IS NULL OR (public.ST_IsValid(coverage) AND NOT public.ST_IsEmpty(coverage)
            AND public.ST_CoveredBy(coverage, public.ST_MakeEnvelope(-180, -90, 180, 90, 4326)))),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (institution, kind, node_key)
);
CREATE INDEX lineage_coverage ON sdss_storage.lineage_node USING gist (coverage);

CREATE TABLE sdss_storage.lineage_edge (
    institution text NOT NULL,
    source_kind text NOT NULL,
    source_key text NOT NULL,
    target_kind text NOT NULL,
    target_key text NOT NULL,
    PRIMARY KEY (institution, source_kind, source_key, target_kind, target_key),
    FOREIGN KEY (institution, source_kind, source_key)
        REFERENCES sdss_storage.lineage_node (institution, kind, node_key),
    FOREIGN KEY (institution, target_kind, target_key)
        REFERENCES sdss_storage.lineage_node (institution, kind, node_key),
    CHECK ((source_kind = 'dataset' AND target_kind IN ('model', 'job'))
        OR (source_kind = 'model' AND target_kind = 'job')
        OR (source_kind = 'job' AND target_kind = 'result'))
);
CREATE INDEX lineage_by_target ON sdss_storage.lineage_edge (institution, target_kind, target_key);

CREATE TABLE sdss_storage.asset_object (
    institution text NOT NULL CHECK (institution ~ '^[a-z][a-z0-9-]{0,62}$'),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_count bigint NOT NULL CHECK (byte_count >= 0),
    PRIMARY KEY (institution, sha256)
);

CREATE TABLE sdss_storage.asset_binding (
    institution text NOT NULL,
    kind text NOT NULL,
    node_key text NOT NULL,
    purpose text NOT NULL CHECK (purpose ~ '^[a-z][a-z0-9_-]{0,127}$'),
    sha256 text NOT NULL,
    PRIMARY KEY (institution, kind, node_key, purpose),
    FOREIGN KEY (institution, kind, node_key)
        REFERENCES sdss_storage.lineage_node (institution, kind, node_key),
    FOREIGN KEY (institution, sha256) REFERENCES sdss_storage.asset_object (institution, sha256)
);

CREATE TABLE sdss_storage.document_vector (
    institution text NOT NULL,
    kind text NOT NULL DEFAULT 'dataset' CHECK (kind = 'dataset'),
    node_key text NOT NULL,
    chunk_key text NOT NULL,
    embedding_model text NOT NULL,
    embedding public.vector(768) NOT NULL CHECK (public.vector_norm(embedding) > 0),
    PRIMARY KEY (institution, node_key, chunk_key, embedding_model),
    FOREIGN KEY (institution, kind, node_key)
        REFERENCES sdss_storage.lineage_node (institution, kind, node_key)
);
CREATE INDEX document_vector_institution_model ON sdss_storage.document_vector
    (institution, embedding_model);
-- Use exact search over an institution/model filter. A shared ANN index can
-- otherwise under-fill small institutional result sets.

DO $policies$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['lineage_node', 'lineage_edge', 'asset_object',
                                      'asset_binding', 'document_vector'] LOOP
        EXECUTE format('ALTER TABLE sdss_storage.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE sdss_storage.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY institution_scope ON sdss_storage.%I
             USING (institution = current_setting(''sdss_storage.institution'', true))
             WITH CHECK (institution = current_setting(''sdss_storage.institution'', true))', table_name);
    END LOOP;
END;
$policies$;
