-- ============================================================================
-- Supabase Schema for Wikidata Medical Terms
-- ============================================================================
-- This schema stores medical terminology data from Wikidata including:
-- - Disease names
-- - Medications
-- - Symptoms
-- - Medical procedures
-- - External IDs (MeSH, ICD, SNOMED, UMLS)
-- ============================================================================

-- Drop existing table if needed (uncomment to recreate)
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
