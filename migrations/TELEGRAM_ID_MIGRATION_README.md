# Миграция telegram_id: INTEGER → BIGINT

## Проблема

Telegram использует 64-битные целые числа (int64) для идентификаторов пользователей. Telegram ID может достигать значений больше 2,147,483,647 (максимум для int32).

### Примеры реальных Telegram ID:
- 6,401,854,279 ❌ Превышает int32
- 5,666,608,489 ❌ Превышает int32

### Ошибка в логах:
```
asyncpg.exceptions.DataError: invalid input for query argument $1: 6401854279 (value out of int32 range)
```

## Решение

Изменить тип поля `telegram_id` в таблице `users` с `INTEGER` (int32) на `BIGINT` (int64).

## Диапазоны типов

| Тип | Минимум | Максимум |
|-----|---------|----------|
| INTEGER (int32) | -2,147,483,648 | 2,147,483,647 |
| BIGINT (int64) | -9,223,372,036,854,775,808 | 9,223,372,036,854,775,807 |

## Изменения в коде

### 1. Модель User (`app/models/user.py`)
```python
# Было:
telegram_id = Column(Integer, unique=True, nullable=False, index=True)

# Стало:
telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
```

### 2. Исправлены вызовы сервисов
В `app/bot/handlers/meal_plan.py` исправлены вызовы, где передавался `user.telegram_id` вместо `user.id`:

```python
# Было:
await MealPlanService.get_active_meal_plan(session, user.telegram_id)

# Стало:
await MealPlanService.get_active_meal_plan(session, user.id)
```

**Важно:**
- `user.id` - это автоинкрементный ID из таблицы users (остаётся INTEGER)
- `user.telegram_id` - это реальный ID пользователя в Telegram (изменён на BIGINT)

## Применение миграции

### Способ 1: SQL-скрипт (вручную)
```bash
psql -U your_user -d your_database -f migrations/migrate_telegram_id_to_bigint.sql
```

### Способ 2: Python-скрипт (рекомендуется)
```bash
python migrations/apply_telegram_id_bigint_migration.py
```

Python-скрипт:
- Проверяет текущий тип поля
- Выполняет миграцию только если требуется
- Показывает прогресс выполнения
- Обрабатывает ошибки

## Проверка миграции

После применения миграции проверьте тип поля:

```sql
SELECT data_type
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name = 'telegram_id';
```

Должно вернуть: `bigint`

## Безопасность

- Миграция выполняется в транзакции
- При ошибке откатывается автоматически
- PostgreSQL автоматически обновляет все индексы и ограничения
- Не требуется остановка приложения (но рекомендуется)

## Рекомендации

1. Сделайте бэкап базы данных перед миграцией
2. Выполните миграцию в период низкой нагрузки
3. После миграции перезапустите приложение
4. Проверьте работу бота с пользователями у которых большие telegram_id

## Примечания

Модель `UserConsent` уже использовала `BigInteger` для `telegram_id`, поэтому миграция для неё не требуется.
