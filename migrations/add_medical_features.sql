-- Миграция для Этапа 4: Медицинский функционал
-- Добавляет поддержку хранения медицинской информации и анализов

-- 1. Добавляем медицинские поля в таблицу users
ALTER TABLE users ADD COLUMN IF NOT EXISTS chronic_conditions JSONB DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS removed_organs JSONB DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS medical_restrictions JSONB DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS medical_notes TEXT;

-- 2. Создаем таблицу для хранения медицинских анализов
CREATE TABLE IF NOT EXISTS medical_analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    analysis_type VARCHAR(100),
    analysis_date TIMESTAMP,
    raw_data JSONB NOT NULL,  -- JSON с сырыми данными анализа
    file_url VARCHAR(500),
    ai_analysis JSONB,  -- JSON с результатом анализа от AI
    detected_deficiencies JSONB DEFAULT '[]'::jsonb,  -- JSON список дефицитов
    needs_doctor_consultation BOOLEAN DEFAULT FALSE,
    recommendations TEXT,
    user_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_medical_analyses_user_id ON medical_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_medical_analyses_created_at ON medical_analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_medical_analyses_analysis_date ON medical_analyses(analysis_date);
