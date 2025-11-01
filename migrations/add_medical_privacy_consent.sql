-- Migration: Add medical privacy consent fields to user_consents
-- Description: Adds fields for tracking user consent on medical data processing without storage
-- Date: 2025-11-01

ALTER TABLE user_consents
ADD COLUMN IF NOT EXISTS medical_privacy_consent BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS medical_privacy_consent_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS medical_privacy_version VARCHAR(20) DEFAULT '1.0' NOT NULL;

-- Update existing records to have default values
UPDATE user_consents
SET medical_privacy_consent = FALSE
WHERE medical_privacy_consent IS NULL;
