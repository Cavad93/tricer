-- Migration: Add meal reminder fields to users table

ALTER TABLE users ADD COLUMN IF NOT EXISTS reminders_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS breakfast_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS lunch_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS dinner_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS snack_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS reminder_timezone VARCHAR(50) DEFAULT 'UTC';
