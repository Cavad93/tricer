-- Migration: Remove raw medical data fields from medical_analyses
-- Description: Removes raw_data and file_url fields to ensure medical privacy
--              We only store AI assessment results, NOT actual medical data
-- Date: 2025-11-01
--
-- IMPORTANT: This migration removes sensitive medical data from database.
-- After this migration, only AI assessment results (deficiencies, recommendations) will be stored.
-- The actual medical analysis documents and raw data will not be preserved.

-- Optional: Create a backup table before dropping columns (uncomment if needed)
-- CREATE TABLE medical_analyses_backup AS SELECT * FROM medical_analyses;

-- Drop the raw_data and file_url columns
ALTER TABLE medical_analyses
DROP COLUMN IF EXISTS raw_data,
DROP COLUMN IF EXISTS file_url;

-- Add a comment to the table explaining the privacy-focused approach
COMMENT ON TABLE medical_analyses IS 'Stores ONLY AI assessment results of medical analyses, NOT the actual medical data. This ensures medical privacy - we store conclusions (deficiencies, recommendations) but not raw medical documents or specific indicators.';
