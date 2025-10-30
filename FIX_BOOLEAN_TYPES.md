# Исправление типов Boolean колонок в PostgreSQL

## Проблема

При миграции с SQLite на PostgreSQL некоторые колонки остались типа `INTEGER` вместо `BOOLEAN`, так как SQLite не имеет настоящего типа BOOLEAN и использует 0/1.

PostgreSQL не может автоматически сравнивать `INTEGER` с `true/false`, что вызывает ошибку:
```
оператор не существует: integer = boolean
```

## Проверка

### Способ 1: Используя Python скрипт (рекомендуется)

```bash
python check_db_types.py
```

Скрипт покажет все boolean-подобные колонки и выделит проблемные.

### Способ 2: Используя SQL напрямую

```bash
psql -U nutriai -d nutriai -f check_boolean_columns.sql
```

## Исправление

Если найдены проблемы с колонкой `is_active` в таблице `meal_plans`:

```bash
psql -U nutriai -d nutriai -f fix_is_active_column.sql
```

**Ожидаемый вывод:**
```
BEGIN
ALTER TABLE
ALTER TABLE
COMMIT

 column_name | data_type | column_default
-------------+-----------+----------------
 is_active   | boolean   | true
```

## Проверка после исправления

1. Запустите скрипт проверки снова:
   ```bash
   python check_db_types.py
   ```

2. Должно вывести:
   ```
   ✅ Все boolean-подобные колонки имеют правильный тип данных!
   ```

3. Перезапустите бота:
   ```bash
   python -m app.bot.main
   ```

4. Проверьте функциональность (отправьте фото еды боту)

## Затронутые таблицы и колонки

### Исправлено:
- ✅ `meal_plans.is_active` - изменена с INTEGER на BOOLEAN

### Уже правильные (BOOLEAN):
- ✅ `users.is_active`
- ✅ `users.is_blocked`
- ✅ `users.reminders_enabled`
- ✅ `users.diary_check_enabled`
- ✅ `users.trial_used`
- ✅ `users.onboarding_completed`
- ✅ `user_consents.medical_disclaimer_accepted`
- ✅ `medical_analyses.needs_doctor_consultation`

## Примечания

- Колонки `times_used`, `tokens_used` - это счетчики (INTEGER), не boolean значения
- Все изменения выполняются в транзакции и могут быть откатаны при ошибке
- После миграции старые значения конвертируются: `0 → false`, `1 → true`
