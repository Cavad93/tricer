-- ================================================
-- Проверка всех INTEGER колонок, которые должны быть BOOLEAN
-- ================================================

-- Проверка типов данных для всех boolean-подобных колонок
SELECT
    table_name,
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
      column_name LIKE '%_active%'
      OR column_name LIKE '%_enabled%'
      OR column_name LIKE '%_blocked%'
      OR column_name LIKE '%_completed%'
      OR column_name LIKE '%_used%' AND column_name NOT LIKE 'times_%' AND column_name NOT LIKE 'tokens_%'
  )
ORDER BY table_name, column_name;

-- Специфическая проверка проблемной таблицы meal_plans
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'meal_plans'
  AND column_name = 'is_active';
