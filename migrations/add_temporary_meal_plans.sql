-- Создание таблицы для временных рационов на день
CREATE TABLE IF NOT EXISTS temporary_meal_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    meal_plan_data TEXT NOT NULL,  -- JSON с рекомендациями на день
    total_calories INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,  -- Истекает в 00:00 следующего дня
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, date)
);

-- Индекс для быстрого поиска по пользователю и дате
CREATE INDEX IF NOT EXISTS idx_temp_meal_plans_user_date ON temporary_meal_plans(user_id, date);

-- Индекс для очистки истекших записей
CREATE INDEX IF NOT EXISTS idx_temp_meal_plans_expires ON temporary_meal_plans(expires_at);
