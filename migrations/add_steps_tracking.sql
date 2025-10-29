-- Добавление поля timezone для пользователей
ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC';

-- Создание таблицы для учета шагов пользователей
CREATE TABLE IF NOT EXISTS user_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    steps INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, date)
);

-- Индекс для быстрого поиска по пользователю и дате
CREATE INDEX IF NOT EXISTS idx_user_steps_user_date ON user_steps(user_id, date);
