-- ============================================================================
-- Supabase Schema for Wikidata Medical Terms
-- ============================================================================
-- This schema stores medical terminology data from Wikidata including:
-- - Disease names
-- - Medications
-- - Symptoms
-- - Medical procedures
-- - External IDs (MeSH, ICD, SNOMED, UMLS)
-- - Change audit logs
-- - Sync execution history
-- ============================================================================

-- Drop existing tables if needed (uncomment to recreate)
-- DROP TABLE IF EXISTS audit_log CASCADE;
-- DROP TABLE IF EXISTS sync_history CASCADE;
-- DROP TABLE IF EXISTS medical_terms CASCADE;

-- Create medical_terms table
CREATE TABLE IF NOT EXISTS medical_terms (
    -- Primary key
    qid TEXT PRIMARY KEY,  -- Wikidata QID (e.g., Q12136)

    -- Labels (multi-language)
    en_label TEXT,         -- English label
    ja_label TEXT,         -- Japanese label

    -- Descriptions (multi-language)
    en_description TEXT,   -- English description
    ja_description TEXT,   -- Japanese description

    -- Categories
    category_en TEXT,      -- English category name (e.g., "disease", "medication")
    category_ja TEXT,      -- Japanese category name (e.g., "病気", "医薬品")

    -- External medical IDs
    mesh_id TEXT,          -- Medical Subject Headings ID
    icd10 TEXT,            -- ICD-10 code
    icd11 TEXT,            -- ICD-11 code
    icd9 TEXT,             -- ICD-9 code
    snomed_id TEXT,        -- SNOMED CT identifier
    umls_id TEXT,          -- UMLS Concept Unique Identifier

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Indexes for performance
-- ============================================================================

-- Full-text search index for English labels
CREATE INDEX IF NOT EXISTS idx_medical_terms_en_label
    ON medical_terms USING gin(to_tsvector('english', en_label));

-- Full-text search index for Japanese labels
CREATE INDEX IF NOT EXISTS idx_medical_terms_ja_label
    ON medical_terms USING gin(to_tsvector('simple', ja_label));

-- Full-text search index for English descriptions
CREATE INDEX IF NOT EXISTS idx_medical_terms_en_description
    ON medical_terms USING gin(to_tsvector('english', en_description));

-- Category indexes for filtering
CREATE INDEX IF NOT EXISTS idx_medical_terms_category_en
    ON medical_terms(category_en);

CREATE INDEX IF NOT EXISTS idx_medical_terms_category_ja
    ON medical_terms(category_ja);

-- External ID indexes for lookups
CREATE INDEX IF NOT EXISTS idx_medical_terms_mesh_id
    ON medical_terms(mesh_id) WHERE mesh_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_medical_terms_icd10
    ON medical_terms(icd10) WHERE icd10 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_medical_terms_icd11
    ON medical_terms(icd11) WHERE icd11 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_medical_terms_snomed_id
    ON medical_terms(snomed_id) WHERE snomed_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_medical_terms_umls_id
    ON medical_terms(umls_id) WHERE umls_id IS NOT NULL;

-- Timestamp indexes for tracking updates
CREATE INDEX IF NOT EXISTS idx_medical_terms_updated_at
    ON medical_terms(updated_at DESC);

-- ============================================================================
-- Triggers for automatic updated_at
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_medical_terms_updated_at ON medical_terms;
CREATE TRIGGER update_medical_terms_updated_at
    BEFORE UPDATE ON medical_terms
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Row Level Security (RLS) - Optional
-- ============================================================================
-- Uncomment if you want to enable RLS for access control

-- Enable RLS
-- ALTER TABLE medical_terms ENABLE ROW LEVEL SECURITY;

-- Policy: Allow public read access
-- CREATE POLICY "Allow public read access"
--     ON medical_terms FOR SELECT
--     USING (true);

-- Policy: Allow authenticated users to insert/update
-- CREATE POLICY "Allow authenticated users to modify"
--     ON medical_terms FOR ALL
--     USING (auth.role() = 'authenticated');

-- ============================================================================
-- Useful queries
-- ============================================================================

-- Search by English label
-- SELECT * FROM medical_terms
-- WHERE to_tsvector('english', en_label) @@ to_tsquery('english', 'diabetes');

-- Search by category
-- SELECT * FROM medical_terms
-- WHERE category_en = 'disease';

-- Find terms with MeSH ID
-- SELECT qid, en_label, mesh_id
-- FROM medical_terms
-- WHERE mesh_id IS NOT NULL;

-- Get recently updated terms
-- SELECT qid, en_label, updated_at
-- FROM medical_terms
-- ORDER BY updated_at DESC
-- LIMIT 100;

-- Count terms by category
-- SELECT category_en, COUNT(*)
-- FROM medical_terms
-- GROUP BY category_en
-- ORDER BY COUNT(*) DESC;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE medical_terms IS 'Medical terminology data from Wikidata including diseases, medications, symptoms, and procedures with multi-language support';
COMMENT ON COLUMN medical_terms.qid IS 'Wikidata QID (unique identifier)';
COMMENT ON COLUMN medical_terms.en_label IS 'English label/name';
COMMENT ON COLUMN medical_terms.ja_label IS 'Japanese label/name';
COMMENT ON COLUMN medical_terms.mesh_id IS 'Medical Subject Headings ID (NLM)';
COMMENT ON COLUMN medical_terms.icd10 IS 'ICD-10 classification code (WHO)';
COMMENT ON COLUMN medical_terms.icd11 IS 'ICD-11 classification code (WHO)';
COMMENT ON COLUMN medical_terms.snomed_id IS 'SNOMED CT identifier';
COMMENT ON COLUMN medical_terms.umls_id IS 'UMLS Concept Unique Identifier (NLM)';

-- ============================================================================
-- SYNC HISTORY TABLE - Track synchronization executions
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_history (
    id BIGSERIAL PRIMARY KEY,

    -- Sync metadata
    sync_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed

    -- Sync details
    dataset_size TEXT,                -- small, medium, large
    source_file TEXT,                 -- CSV/JSON filename

    -- Statistics
    total_records INTEGER,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,

    -- Execution environment
    execution_environment TEXT,       -- github_actions, local, manual
    github_run_id TEXT,              -- GitHub Actions run ID
    github_actor TEXT,               -- User who triggered the workflow

    -- Error tracking
    error_message TEXT,
    error_details JSONB,

    -- Additional metadata
    metadata JSONB
);

-- Index for querying sync history
CREATE INDEX IF NOT EXISTS idx_sync_history_started_at
    ON sync_history(sync_started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sync_history_status
    ON sync_history(status);

COMMENT ON TABLE sync_history IS 'Track each synchronization execution from Wikidata to Supabase';

-- ============================================================================
-- AUDIT LOG TABLE - Track all changes to medical_terms
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,

    -- Record identification
    qid TEXT NOT NULL,               -- QID of the changed record

    -- Change metadata
    operation TEXT NOT NULL,         -- INSERT, UPDATE, DELETE
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Change details
    changed_fields TEXT[],           -- Array of field names that changed
    old_values JSONB,                -- Previous values (for UPDATE/DELETE)
    new_values JSONB,                -- New values (for INSERT/UPDATE)

    -- Context
    sync_history_id BIGINT,          -- Link to sync_history if part of a sync
    changed_by TEXT,                 -- User/system that made the change

    -- Constraints
    CONSTRAINT fk_sync_history
        FOREIGN KEY(sync_history_id)
        REFERENCES sync_history(id)
        ON DELETE SET NULL
);

-- Indexes for audit log queries
CREATE INDEX IF NOT EXISTS idx_audit_log_qid
    ON audit_log(qid);

CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at
    ON audit_log(changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_operation
    ON audit_log(operation);

CREATE INDEX IF NOT EXISTS idx_audit_log_sync_history_id
    ON audit_log(sync_history_id);

COMMENT ON TABLE audit_log IS 'Audit trail of all changes to medical_terms table';

-- ============================================================================
-- TRIGGER FUNCTION - Automatically log changes to medical_terms
-- ============================================================================

CREATE OR REPLACE FUNCTION log_medical_terms_changes()
RETURNS TRIGGER AS $$
DECLARE
    changed_fields TEXT[] := ARRAY[]::TEXT[];
    old_vals JSONB;
    new_vals JSONB;
BEGIN
    -- Determine operation type
    IF (TG_OP = 'INSERT') THEN
        -- For inserts, log all new values
        new_vals := to_jsonb(NEW);

        INSERT INTO audit_log (qid, operation, new_values)
        VALUES (NEW.qid, 'INSERT', new_vals);

        RETURN NEW;

    ELSIF (TG_OP = 'UPDATE') THEN
        -- For updates, track which fields changed
        old_vals := jsonb_build_object();
        new_vals := jsonb_build_object();

        -- Check each field for changes
        IF OLD.en_label IS DISTINCT FROM NEW.en_label THEN
            changed_fields := array_append(changed_fields, 'en_label');
            old_vals := old_vals || jsonb_build_object('en_label', OLD.en_label);
            new_vals := new_vals || jsonb_build_object('en_label', NEW.en_label);
        END IF;

        IF OLD.ja_label IS DISTINCT FROM NEW.ja_label THEN
            changed_fields := array_append(changed_fields, 'ja_label');
            old_vals := old_vals || jsonb_build_object('ja_label', OLD.ja_label);
            new_vals := new_vals || jsonb_build_object('ja_label', NEW.ja_label);
        END IF;

        IF OLD.en_description IS DISTINCT FROM NEW.en_description THEN
            changed_fields := array_append(changed_fields, 'en_description');
            old_vals := old_vals || jsonb_build_object('en_description', OLD.en_description);
            new_vals := new_vals || jsonb_build_object('en_description', NEW.en_description);
        END IF;

        IF OLD.ja_description IS DISTINCT FROM NEW.ja_description THEN
            changed_fields := array_append(changed_fields, 'ja_description');
            old_vals := old_vals || jsonb_build_object('ja_description', OLD.ja_description);
            new_vals := new_vals || jsonb_build_object('ja_description', NEW.ja_description);
        END IF;

        IF OLD.category_en IS DISTINCT FROM NEW.category_en THEN
            changed_fields := array_append(changed_fields, 'category_en');
            old_vals := old_vals || jsonb_build_object('category_en', OLD.category_en);
            new_vals := new_vals || jsonb_build_object('category_en', NEW.category_en);
        END IF;

        IF OLD.category_ja IS DISTINCT FROM NEW.category_ja THEN
            changed_fields := array_append(changed_fields, 'category_ja');
            old_vals := old_vals || jsonb_build_object('category_ja', OLD.category_ja);
            new_vals := new_vals || jsonb_build_object('category_ja', NEW.category_ja);
        END IF;

        IF OLD.mesh_id IS DISTINCT FROM NEW.mesh_id THEN
            changed_fields := array_append(changed_fields, 'mesh_id');
            old_vals := old_vals || jsonb_build_object('mesh_id', OLD.mesh_id);
            new_vals := new_vals || jsonb_build_object('mesh_id', NEW.mesh_id);
        END IF;

        IF OLD.icd10 IS DISTINCT FROM NEW.icd10 THEN
            changed_fields := array_append(changed_fields, 'icd10');
            old_vals := old_vals || jsonb_build_object('icd10', OLD.icd10);
            new_vals := new_vals || jsonb_build_object('icd10', NEW.icd10);
        END IF;

        IF OLD.icd11 IS DISTINCT FROM NEW.icd11 THEN
            changed_fields := array_append(changed_fields, 'icd11');
            old_vals := old_vals || jsonb_build_object('icd11', OLD.icd11);
            new_vals := new_vals || jsonb_build_object('icd11', NEW.icd11);
        END IF;

        IF OLD.icd9 IS DISTINCT FROM NEW.icd9 THEN
            changed_fields := array_append(changed_fields, 'icd9');
            old_vals := old_vals || jsonb_build_object('icd9', OLD.icd9);
            new_vals := new_vals || jsonb_build_object('icd9', NEW.icd9);
        END IF;

        IF OLD.snomed_id IS DISTINCT FROM NEW.snomed_id THEN
            changed_fields := array_append(changed_fields, 'snomed_id');
            old_vals := old_vals || jsonb_build_object('snomed_id', OLD.snomed_id);
            new_vals := new_vals || jsonb_build_object('snomed_id', NEW.snomed_id);
        END IF;

        IF OLD.umls_id IS DISTINCT FROM NEW.umls_id THEN
            changed_fields := array_append(changed_fields, 'umls_id');
            old_vals := old_vals || jsonb_build_object('umls_id', OLD.umls_id);
            new_vals := new_vals || jsonb_build_object('umls_id', NEW.umls_id);
        END IF;

        -- Only log if something actually changed
        IF array_length(changed_fields, 1) > 0 THEN
            INSERT INTO audit_log (qid, operation, changed_fields, old_values, new_values)
            VALUES (NEW.qid, 'UPDATE', changed_fields, old_vals, new_vals);
        END IF;

        RETURN NEW;

    ELSIF (TG_OP = 'DELETE') THEN
        -- For deletes, log all old values
        old_vals := to_jsonb(OLD);

        INSERT INTO audit_log (qid, operation, old_values)
        VALUES (OLD.qid, 'DELETE', old_vals);

        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS medical_terms_audit_trigger ON medical_terms;
CREATE TRIGGER medical_terms_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON medical_terms
    FOR EACH ROW EXECUTE FUNCTION log_medical_terms_changes();

COMMENT ON FUNCTION log_medical_terms_changes() IS 'Automatically log all changes to medical_terms table';

-- ============================================================================
-- USEFUL AUDIT QUERIES
-- ============================================================================

-- View recent changes
-- SELECT a.qid, a.operation, a.changed_at, a.changed_fields,
--        m.en_label, m.category_en
-- FROM audit_log a
-- LEFT JOIN medical_terms m ON a.qid = m.qid
-- ORDER BY a.changed_at DESC
-- LIMIT 100;

-- View changes for a specific QID
-- SELECT operation, changed_at, changed_fields, old_values, new_values
-- FROM audit_log
-- WHERE qid = 'Q12136'
-- ORDER BY changed_at DESC;

-- View sync history
-- SELECT id, sync_started_at, sync_completed_at, status,
--        total_records, records_inserted, records_updated, records_failed
-- FROM sync_history
-- ORDER BY sync_started_at DESC;

-- View changes from a specific sync
-- SELECT a.qid, a.operation, a.changed_fields, m.en_label
-- FROM audit_log a
-- LEFT JOIN medical_terms m ON a.qid = m.qid
-- WHERE a.sync_history_id = 1
-- ORDER BY a.changed_at;

-- Count changes by operation type
-- SELECT operation, COUNT(*) as count
-- FROM audit_log
-- GROUP BY operation;

-- Find records with most updates
-- SELECT qid, COUNT(*) as update_count
-- FROM audit_log
-- WHERE operation = 'UPDATE'
-- GROUP BY qid
-- ORDER BY update_count DESC
-- LIMIT 20;
