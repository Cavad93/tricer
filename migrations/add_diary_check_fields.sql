-- Миграция: Добавление полей для проверки дневника питания
-- Добавляет поля для времени проверки дневника и включения/отключения этой функции

-- Добавляем поля для проверки дневника
ALTER TABLE users ADD COLUMN IF NOT EXISTS diary_check_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS diary_check_time VARCHAR(5);  -- Формат HH:MM
