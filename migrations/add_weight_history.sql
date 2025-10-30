-- Миграция: Добавление истории изменений веса
-- Создает таблицу для отслеживания изменений веса пользователя

-- Создаем таблицу для хранения истории веса
CREATE TABLE IF NOT EXISTS weight_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    weight REAL NOT NULL,
    measured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_weight_history_user_id ON weight_history(user_id);
CREATE INDEX IF NOT EXISTS idx_weight_history_measured_at ON weight_history(measured_at);
CREATE INDEX IF NOT EXISTS idx_weight_history_user_measured ON weight_history(user_id, measured_at DESC);
