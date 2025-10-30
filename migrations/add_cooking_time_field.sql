-- Migration: Add preferred_cooking_time_minutes field to users table
-- Date: 2025-10-29
-- Description: Adds field to store user's preferred cooking time for meal planning

-- PostgreSQL syntax
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_cooking_time_minutes INTEGER NULL;

-- Note: This field will be automatically created on next bot start via create_all()
-- This migration is for reference and manual application if needed
