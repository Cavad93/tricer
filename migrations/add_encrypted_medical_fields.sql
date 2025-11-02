-- Миграция: Добавление зашифрованных медицинских полей (152-ФЗ)
-- Дата: 2025-11-02
-- Описание: Добавляет новые зашифрованные поля для медицинских данных

-- Добавляем новые зашифрованные поля для медицинских данных
ALTER TABLE users ADD COLUMN IF NOT EXISTS _chronic_conditions_encrypted BYTEA;
ALTER TABLE users ADD COLUMN IF NOT EXISTS _removed_organs_encrypted BYTEA;
ALTER TABLE users ADD COLUMN IF NOT EXISTS _medical_restrictions_encrypted BYTEA;

-- Комментарии для документации
COMMENT ON COLUMN users._chronic_conditions_encrypted IS 'Зашифрованный список хронических заболеваний (152-ФЗ)';
COMMENT ON COLUMN users._removed_organs_encrypted IS 'Зашифрованный список удаленных органов (152-ФЗ)';
COMMENT ON COLUMN users._medical_restrictions_encrypted IS 'Зашифрованные медицинские ограничения по питанию (152-ФЗ)';

-- ВАЖНО: Старые поля (chronic_conditions, removed_organs, medical_restrictions)
-- оставлены для обратной совместимости. Они будут удалены после полной миграции данных.

-- После применения этой миграции необходимо запустить Python скрипт
-- для переноса существующих данных в зашифрованные поля:
-- python migrate_encrypt_medical_data.py
