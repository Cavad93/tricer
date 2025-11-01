-- Migration: Add tracking fields to insight_facts table
-- Description: Adds first_detected, last_validated, and updated_at fields for fact history tracking
-- Date: 2025-11-01

-- Add new tracking columns to insight_facts table
ALTER TABLE insight_facts
ADD COLUMN IF NOT EXISTS first_detected TIMESTAMP,
ADD COLUMN IF NOT EXISTS last_validated TIMESTAMP,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Set first_detected to first_observed for existing records where it's NULL
UPDATE insight_facts
SET first_detected = first_observed
WHERE first_detected IS NULL;

-- Set last_validated to last_updated for existing records where it's NULL
UPDATE insight_facts
SET last_validated = last_updated
WHERE last_validated IS NULL;

-- Set updated_at to created_at for existing records where it's NULL
UPDATE insight_facts
SET updated_at = created_at
WHERE updated_at IS NULL;

-- Add a trigger to auto-update updated_at on record changes
CREATE OR REPLACE FUNCTION update_insight_facts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS insight_facts_updated_at_trigger ON insight_facts;

CREATE TRIGGER insight_facts_updated_at_trigger
    BEFORE UPDATE ON insight_facts
    FOR EACH ROW
    EXECUTE FUNCTION update_insight_facts_updated_at();
