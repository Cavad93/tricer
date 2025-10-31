-- Migration: Add pantry tables for tracking products at home
-- Created: 2025-10-31

-- Create user_pantry table
CREATE TABLE IF NOT EXISTS user_pantry (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,

    -- Product information
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),

    -- Quantity
    quantity FLOAT NOT NULL,
    unit VARCHAR(50) NOT NULL DEFAULT 'г',

    -- Nutritional value per 100g
    calories_per_100g INTEGER,
    proteins_per_100g FLOAT,
    fats_per_100g FLOAT,
    carbs_per_100g FLOAT,

    -- Tracking
    initial_quantity FLOAT,
    last_used_date TIMESTAMP,
    times_used INTEGER DEFAULT 0,

    -- Expiration
    expiration_date TIMESTAMP,
    is_perishable BOOLEAN DEFAULT FALSE,

    -- Metadata
    added_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Source
    source VARCHAR(50),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_pantry_user_id ON user_pantry(user_id);

-- Create pantry_usage_log table
CREATE TABLE IF NOT EXISTS pantry_usage_log (
    id SERIAL PRIMARY KEY,
    pantry_item_id INTEGER NOT NULL REFERENCES user_pantry(id) ON DELETE CASCADE,

    -- Link to meals
    meal_id INTEGER REFERENCES meals(id) ON DELETE SET NULL,
    planned_meal_id INTEGER REFERENCES planned_meals(id) ON DELETE SET NULL,

    -- Quantity used
    quantity_used FLOAT NOT NULL,
    unit VARCHAR(50) NOT NULL,

    -- Usage type
    usage_type VARCHAR(50) NOT NULL,

    -- Metadata
    used_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_pantry_usage_log_pantry_item_id ON pantry_usage_log(pantry_item_id);
CREATE INDEX IF NOT EXISTS idx_pantry_usage_log_meal_id ON pantry_usage_log(meal_id);
CREATE INDEX IF NOT EXISTS idx_pantry_usage_log_planned_meal_id ON pantry_usage_log(planned_meal_id);

-- Add trigger to update updated_at on user_pantry
CREATE OR REPLACE FUNCTION update_user_pantry_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_pantry_updated_at_trigger
BEFORE UPDATE ON user_pantry
FOR EACH ROW
EXECUTE FUNCTION update_user_pantry_updated_at();
