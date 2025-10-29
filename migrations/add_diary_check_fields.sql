-- Миграция: Добавление полей для проверки дневника питания
-- Добавляет поля для времени проверки дневника и включения/отключения этой функции

-- Добавляем поля для проверки дневника
ALTER TABLE users ADD COLUMN diary_check_enabled BOOLEAN DEFAULT 1;
ALTER TABLE users ADD COLUMN diary_check_time VARCHAR(5);  -- Формат HH:MM
