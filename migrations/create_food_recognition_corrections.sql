-- Migration: Create food_recognition_corrections table for storing user corrections

CREATE TABLE IF NOT EXISTS food_recognition_corrections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    photo_hash VARCHAR(255) NOT NULL,
    original_recognition JSONB NOT NULL,
    corrected_data JSONB NOT NULL,
    user_clarification TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    times_used INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_food_corrections_user_id ON food_recognition_corrections(user_id);
CREATE INDEX IF NOT EXISTS idx_food_corrections_photo_hash ON food_recognition_corrections(photo_hash);
CREATE INDEX IF NOT EXISTS idx_user_photo_hash ON food_recognition_corrections(user_id, photo_hash);
