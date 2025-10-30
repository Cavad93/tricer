-- ================================================
-- Миграция: исправление типа колонки is_active
-- ================================================
-- Проблема: колонка is_active в meal_plans имеет тип INTEGER (из SQLite),
-- но код использует Boolean значения (true/false)
--
-- Решение: изменить тип колонки на BOOLEAN и конвертировать данные

BEGIN;

-- Изменить тип колонки is_active с INTEGER на BOOLEAN
-- PostgreSQL автоматически конвертирует: 0 -> false, 1 -> true, NULL -> NULL
ALTER TABLE meal_plans
    ALTER COLUMN is_active TYPE BOOLEAN
    USING CASE
        WHEN is_active = 0 THEN FALSE
        WHEN is_active = 1 THEN TRUE
        ELSE TRUE  -- По умолчанию true для любых других значений
    END;

-- Установить значение по умолчанию
ALTER TABLE meal_plans
    ALTER COLUMN is_active SET DEFAULT TRUE;

COMMIT;

-- Проверка результата
SELECT
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name = 'meal_plans' AND column_name = 'is_active';
