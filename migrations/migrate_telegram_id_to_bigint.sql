-- Миграция: Изменение типа telegram_id с INTEGER на BIGINT
-- Дата: 2025-11-04
-- Описание: Telegram ID может превышать максимальное значение INT32 (2,147,483,647)
--           Необходимо изменить тип на BIGINT для поддержки значений до 9,223,372,036,854,775,807

BEGIN;

-- Изменить тип telegram_id в таблице users с INTEGER на BIGINT
ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT;

-- Примечание: PostgreSQL автоматически обновит все индексы и ограничения

COMMIT;
