-- Migration: Add meal reminder fields to users table

ALTER TABLE users ADD COLUMN reminders_enabled BOOLEAN DEFAULT 1;
ALTER TABLE users ADD COLUMN breakfast_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN lunch_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN dinner_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN snack_reminder_time VARCHAR(5) NULL;
ALTER TABLE users ADD COLUMN reminder_timezone VARCHAR(50) DEFAULT 'UTC';
