-- Миграция для добавления системы кэширования планов питания
-- Для экономии токенов AI

-- Создание enum для статуса кэшированного плана
CREATE TYPE cached_meal_plan_status AS ENUM ('active', 'outdated', 'archived');

-- Таблица категорий пользователей
CREATE TABLE user_categories (
    id SERIAL PRIMARY KEY,

    -- Хэш параметров для быстрого поиска
    params_hash VARCHAR(64) UNIQUE NOT NULL,

    -- Параметры категории
    target_calories INTEGER NOT NULL,
    target_proteins INTEGER NOT NULL,
    target_fats INTEGER NOT NULL,
    target_carbs INTEGER NOT NULL,
    diet_type VARCHAR(20) NOT NULL,
    budget_category VARCHAR(20) NOT NULL,
    allergies JSONB DEFAULT '[]',

    -- Статистика
    users_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица кэшированных планов питания
CREATE TABLE cached_meal_plans (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES user_categories(id) ON DELETE CASCADE,

    -- Период плана
    period_type VARCHAR(20) NOT NULL, -- day/week/month

    -- Данные плана (JSON)
    plan_data JSONB NOT NULL,

    -- Статус
    status cached_meal_plan_status DEFAULT 'active',

    -- Метрики использования
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,

    -- Обратная связь
    positive_feedback_count INTEGER DEFAULT 0,
    negative_feedback_count INTEGER DEFAULT 0,

    -- Временные метки
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для оптимизации
CREATE INDEX idx_user_categories_hash ON user_categories(params_hash);
CREATE INDEX idx_cached_plans_category ON cached_meal_plans(category_id);
CREATE INDEX idx_cached_plans_status ON cached_meal_plans(status);
CREATE INDEX idx_cached_plans_category_period_status ON cached_meal_plans(category_id, period_type, status);

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_user_categories_updated_at
    BEFORE UPDATE ON user_categories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cached_meal_plans_updated_at
    BEFORE UPDATE ON cached_meal_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Комментарии к таблицам
COMMENT ON TABLE user_categories IS 'Категории пользователей для кэширования планов питания';
COMMENT ON TABLE cached_meal_plans IS 'Кэшированные планы питания для экономии токенов AI';
COMMENT ON COLUMN user_categories.params_hash IS 'SHA256 хэш параметров пользователя';
COMMENT ON COLUMN cached_meal_plans.plan_data IS 'JSON данные плана в формате ответа AI';
COMMENT ON COLUMN cached_meal_plans.usage_count IS 'Количество использований плана';
