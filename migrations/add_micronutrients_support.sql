-- Миграция для добавления поддержки микронутриентов
-- Дата: 2025-10-29
-- Этап 3: Продвинутые функции - мониторинг микроэлементов и витаминов

-- 1. Создание таблицы для хранения суточной статистики по микронутриентам
CREATE TABLE IF NOT EXISTS daily_micronutrients (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,

    -- Витамины
    vitamin_a REAL DEFAULT 0,
    beta_carotene REAL DEFAULT 0,
    vitamin_b1 REAL DEFAULT 0,
    vitamin_b2 REAL DEFAULT 0,
    vitamin_b3 REAL DEFAULT 0,
    vitamin_b5 REAL DEFAULT 0,
    vitamin_b6 REAL DEFAULT 0,
    vitamin_b7 REAL DEFAULT 0,
    vitamin_b9 REAL DEFAULT 0,
    vitamin_b12 REAL DEFAULT 0,
    vitamin_c REAL DEFAULT 0,
    vitamin_d REAL DEFAULT 0,
    vitamin_e REAL DEFAULT 0,
    vitamin_k REAL DEFAULT 0,
    choline REAL DEFAULT 0,

    -- Минералы
    calcium REAL DEFAULT 0,
    phosphorus REAL DEFAULT 0,
    magnesium REAL DEFAULT 0,
    potassium REAL DEFAULT 0,
    sodium REAL DEFAULT 0,
    chloride REAL DEFAULT 0,
    iron REAL DEFAULT 0,
    zinc REAL DEFAULT 0,
    iodine REAL DEFAULT 0,
    selenium REAL DEFAULT 0,
    copper REAL DEFAULT 0,
    manganese REAL DEFAULT 0,
    chromium REAL DEFAULT 0,
    fluoride REAL DEFAULT 0,
    cobalt REAL DEFAULT 0,
    silicon REAL DEFAULT 0,

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, date)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_daily_micronutrients_user_date ON daily_micronutrients(user_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_micronutrients_date ON daily_micronutrients(date);

-- 2. Добавление поля micronutrients в таблицу meal_foods (JSONB)
ALTER TABLE meal_foods ADD COLUMN IF NOT EXISTS micronutrients JSONB DEFAULT '{}'::jsonb;

-- 3. Добавление поля micronutrients в таблицу planned_meals (JSONB)
ALTER TABLE planned_meals ADD COLUMN IF NOT EXISTS micronutrients JSONB DEFAULT '{}'::jsonb;

-- Комментарии:
-- - daily_micronutrients хранит агрегированные данные за день для быстрого доступа
-- - meal_foods.micronutrients хранит микронутриенты конкретного блюда в JSON формате
-- - planned_meals.micronutrients хранит планируемые микронутриенты в JSON формате
-- - Все значения в соответствующих единицах измерения (мг, мкг)
