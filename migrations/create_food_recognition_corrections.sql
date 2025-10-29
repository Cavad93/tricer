-- Migration: Create food_recognition_corrections table for storing user corrections

CREATE TABLE food_recognition_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    photo_hash VARCHAR NOT NULL,
    original_recognition JSON NOT NULL,
    corrected_data JSON NOT NULL,
    user_clarification VARCHAR NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    times_used INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for fast lookup
CREATE INDEX idx_food_corrections_user_id ON food_recognition_corrections(user_id);
CREATE INDEX idx_food_corrections_photo_hash ON food_recognition_corrections(photo_hash);
CREATE INDEX idx_user_photo_hash ON food_recognition_corrections(user_id, photo_hash);
