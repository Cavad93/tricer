-- Миграция для Этапа 4: Медицинский функционал
-- Добавляет поддержку хранения медицинской информации и анализов

-- 1. Добавляем медицинские поля в таблицу users
ALTER TABLE users ADD COLUMN chronic_conditions TEXT DEFAULT '[]';
ALTER TABLE users ADD COLUMN removed_organs TEXT DEFAULT '[]';
ALTER TABLE users ADD COLUMN medical_restrictions TEXT DEFAULT '{}';
ALTER TABLE users ADD COLUMN medical_notes TEXT;

-- 2. Создаем таблицу для хранения медицинских анализов
CREATE TABLE IF NOT EXISTS medical_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    analysis_type VARCHAR(100),
    analysis_date DATETIME,
    raw_data TEXT NOT NULL,  -- JSON с сырыми данными анализа
    file_url VARCHAR(500),
    ai_analysis TEXT,  -- JSON с результатом анализа от AI
    detected_deficiencies TEXT DEFAULT '[]',  -- JSON список дефицитов
    needs_doctor_consultation BOOLEAN DEFAULT 0,
    recommendations TEXT,
    user_notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_medical_analyses_user_id ON medical_analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_medical_analyses_created_at ON medical_analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_medical_analyses_analysis_date ON medical_analyses(analysis_date);
