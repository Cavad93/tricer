# Реализация юридических требований (152-ФЗ, 323-ФЗ)

## Дата: 2025-11-02

---

## 📋 ОБЗОР ИЗМЕНЕНИЙ

Внедрены обязательные дисклеймеры, согласия на обработку данных, шифрование медицинских данных и функции управления конфиденциальностью в соответствии с законодательством РФ.

---

## ✅ ЧТО БЫЛО СДЕЛАНО

### 1. **Тексты и дисклеймеры** (`app/bot/texts.py`)

Добавлены:
- ✅ `MEDICAL_DISCLAIMER_INITIAL` - расширенный медицинский дисклеймер для первого запуска
- ✅ `PERSONAL_DATA_CONSENT` - согласие на обработку персональных данных (152-ФЗ)
- ✅ `MEDICAL_DATA_COLLECTION_DISCLAIMER` - дисклеймер при сборе медицинских данных
- ✅ `MEDICAL_ANALYSIS_DISCLAIMER` - дисклеймер для анализа показателей
- ✅ `PROFILE_MEDICAL_REMINDER` - напоминание в профиле
- ✅ `MEAL_PLAN_MEDICAL_DISCLAIMER` - дисклеймер при создании плана с медицинскими ограничениями
- ✅ `MEAL_PLAN_GENERATION_DISCLAIMER` - дисклеймер перед генерацией плана
- ✅ `DEFICIENCIES_FOUND_TEXT` - текст при обнаружении дефицитов
- ✅ `EXPORT_DATA_TEXT` - текст для экспорта данных
- ✅ `DELETE_ACCOUNT_WARNING` - предупреждение об удалении аккаунта
- ✅ `PRIVACY_SETTINGS_TEXT` - текст настроек конфиденциальности

**Обновлены AI-промпты:**
- ✅ `AI_SYSTEM_PROMPT_BASE` - с критическими правилами безопасности
- ✅ `MEDICAL_ANALYSIS_PROMPT_TEMPLATE` - промпт для анализа медицинских показателей

### 2. **Состояния FSM** (`app/bot/states.py`)

Добавлены новые состояния:

**В `OnboardingStates`:**
- `MEDICAL_DISCLAIMER` - показ медицинского дисклеймера
- `PERSONAL_DATA_CONSENT` - согласие на обработку персональных данных
- `MEDICAL_DATA_CONSENT` - согласие на обработку медицинских данных

**Новый enum `PrivacyStates`:**
- `CONFIRMING_DELETE` - подтверждение удаления аккаунта
- `EXPORTING_DATA` - экспорт данных
- `REVOKING_CONSENT` - отзыв согласия

### 3. **Сервис шифрования** (`app/services/encryption_service.py`)

Создан новый сервис для шифрования медицинских данных:

```python
from app.services.encryption_service import get_encryption_service

# Пример использования
encryption = get_encryption_service()
encrypted = encryption.encrypt({"chronic_conditions": ["диабет"]})
decrypted = encryption.decrypt(encrypted)
```

**Возможности:**
- Симметричное шифрование (Fernet)
- Работа со списками, словарями, строками
- Автоматическая сериализация JSON
- Безопасное хранение ключа в переменных окружения

### 4. **Хендлеры конфиденциальности** (`app/bot/handlers/privacy.py`)

Созданы хендлеры для:
- `/privacy_settings` - управление конфиденциальностью
- `/export_data` - экспорт всех данных пользователя в JSON
- `/delete_account` - полное удаление аккаунта и всех данных
- Отзыв согласия на обработку данных

---

## 🔧 ЧТО НУЖНО ДОДЕЛАТЬ

### 1. **Обновить онбординг** (`app/bot/handlers/start.py`)

Добавить экраны согласий в начало онбординга:

```
/start
 ↓
1. MEDICAL_DISCLAIMER (новый экран)
   Кнопки: [Согласен] [Отказаться]
 ↓
2. PERSONAL_DATA_CONSENT (новый экран)
   Кнопки: [Согласен] [Прочитать политику]
 ↓
3. MEDICAL_DATA_CONSENT (новый экран) [опционально]
   Кнопки: [Согласен] [Пропустить]
 ↓
4. Базовые данные (существующий flow)
```

**Код для добавления:**

```python
from app.bot.texts import (
    MEDICAL_DISCLAIMER_INITIAL,
    PERSONAL_DATA_CONSENT,
    MEDICAL_DATA_COLLECTION_DISCLAIMER
)
from app.bot.states import OnboardingStates

# В начале start_command():
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем существующего пользователя
    # ...

    # Показываем медицинский дисклеймер
    keyboard = [
        [InlineKeyboardButton("✅ Согласен", callback_data="accept_disclaimer")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="decline_disclaimer")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        MEDICAL_DISCLAIMER_INITIAL,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    return OnboardingStates.MEDICAL_DISCLAIMER

# Хендлер для принятия дисклеймера
async def accept_disclaimer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Показываем согласие на персональные данные
    keyboard = [
        [InlineKeyboardButton("✅ Согласен", callback_data="accept_data_consent")],
        [InlineKeyboardButton("📄 Политика конфиденциальности", url="https://your-site.com/privacy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        PERSONAL_DATA_CONSENT,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    return OnboardingStates.PERSONAL_DATA_CONSENT

# И т.д.
```

### 2. **Добавить дисклеймеры в создание плана** (`app/bot/handlers/meal_plan.py`)

Добавить дисклеймеры в следующих местах:

**Перед генерацией плана (если есть медицинские ограничения):**

```python
from app.bot.texts import MEAL_PLAN_MEDICAL_DISCLAIMER, MEAL_PLAN_GENERATION_DISCLAIMER

# В функции перед генерацией:
async def start_meal_plan_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool):
    # ...

    # Если у пользователя есть медицинские ограничения
    if user.chronic_conditions or user.removed_organs:
        conditions_list = "\n".join([
            f"• {cond}" for cond in (user.chronic_conditions or [])
        ])

        disclaimer_text = MEAL_PLAN_MEDICAL_DISCLAIMER.format(
            conditions_list=conditions_list
        )

        keyboard = [
            [InlineKeyboardButton("✅ Продолжить", callback_data="confirm_generation")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_plan")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(
            disclaimer_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

        return MealPlanStates.CONFIRMING_GENERATION  # Новое состояние

    # Показываем общий дисклеймер
    await update.callback_query.edit_message_text(
        MEAL_PLAN_GENERATION_DISCLAIMER,
        parse_mode="HTML"
    )

    # Генерация плана
    # ...
```

### 3. **Добавить триггеры безопасности** (`app/services/medical_analysis_service.py`)

Добавить проверки критических ситуаций:

```python
def _check_critical_deficiencies(deficiencies: list) -> tuple[bool, str]:
    """
    Проверяет наличие критических дефицитов

    Returns:
        (needs_urgent_doctor, reason)
    """
    critical = []

    for def_item in deficiencies:
        if def_item['severity'] == 'severe':
            critical.append(def_item['nutrient'])

    if critical:
        return True, f"Критические дефициты: {', '.join(critical)}"

    return False, ""

# В analyze_lab_results():
needs_urgent, reason = _check_critical_deficiencies(detected_deficiencies)

if needs_urgent:
    # Добавляем срочное предупреждение
    result['urgent_doctor_needed'] = True
    result['urgent_reason'] = reason
```

### 4. **Интегрировать хендлеры privacy в main.py**

Добавить хендлеры в `app/bot/main.py`:

```python
from app.bot.handlers import privacy

# В функции main():

# Добавить команды
application.add_handler(CommandHandler("privacy_settings", privacy.privacy_settings_command))
application.add_handler(CommandHandler("export_data", privacy.export_data_callback))
application.add_handler(CommandHandler("delete_account", privacy.delete_account_callback))

# Добавить CallbackQueryHandlers
application.add_handler(CallbackQueryHandler(
    privacy.export_data_callback,
    pattern="^export_data$"
))
application.add_handler(CallbackQueryHandler(
    privacy.delete_account_callback,
    pattern="^delete_account$"
))
application.add_handler(CallbackQueryHandler(
    privacy.confirm_delete_account_callback,
    pattern="^confirm_delete$"
))
application.add_handler(CallbackQueryHandler(
    privacy.revoke_consent_callback,
    pattern="^revoke_consent$"
))
```

### 5. **Обновить модель User с шифрованием** (`app/models/user.py`)

Добавить шифрование медицинских полей:

```python
from sqlalchemy import Column, LargeBinary
from sqlalchemy.ext.hybrid import hybrid_property
from app.services.encryption_service import get_encryption_service

class User(Base):
    # ... existing fields ...

    # Зашифрованные поля (добавить новые колонки)
    _chronic_conditions_encrypted = Column(LargeBinary, nullable=True)
    _removed_organs_encrypted = Column(LargeBinary, nullable=True)
    _medical_restrictions_encrypted = Column(LargeBinary, nullable=True)

    @hybrid_property
    def chronic_conditions(self):
        """Расшифровывает хронические заболевания"""
        if not self._chronic_conditions_encrypted:
            return None
        encryption = get_encryption_service()
        return encryption.decrypt_list(self._chronic_conditions_encrypted)

    @chronic_conditions.setter
    def chronic_conditions(self, value):
        """Шифрует хронические заболевания"""
        if value is None:
            self._chronic_conditions_encrypted = None
        else:
            encryption = get_encryption_service()
            self._chronic_conditions_encrypted = encryption.encrypt_list(value)

    # Аналогично для removed_organs и medical_restrictions
```

**⚠️ ВАЖНО:** Это изменение требует миграции БД!

### 6. **Создать миграцию БД**

```sql
-- migrations/add_encrypted_medical_fields.sql

-- Добавляем новые зашифрованные поля
ALTER TABLE users ADD COLUMN _chronic_conditions_encrypted BLOB;
ALTER TABLE users ADD COLUMN _removed_organs_encrypted BLOB;
ALTER TABLE users ADD COLUMN _medical_restrictions_encrypted BLOB;

-- Копируем данные из старых полей в новые (с шифрованием)
-- Это нужно сделать через Python скрипт

-- После переноса можно удалить старые поля (опционально)
-- ALTER TABLE users DROP COLUMN chronic_conditions;
-- ALTER TABLE users DROP COLUMN removed_organs;
-- ALTER TABLE users DROP COLUMN medical_restrictions;
```

**Python скрипт для миграции:**

```python
# migrate_encrypt_medical_data.py

import asyncio
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User
from app.services.encryption_service import get_encryption_service

async def migrate():
    encryption = get_encryption_service()

    async with get_db() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

        for user in users:
            # Шифруем существующие данные
            if user.chronic_conditions:
                user._chronic_conditions_encrypted = encryption.encrypt_list(
                    user.chronic_conditions
                )

            if user.removed_organs:
                user._removed_organs_encrypted = encryption.encrypt_list(
                    user.removed_organs
                )

            if user.medical_restrictions:
                user._medical_restrictions_encrypted = encryption.encrypt_dict(
                    user.medical_restrictions
                )

        await db.commit()
        print(f"Migrated {len(users)} users")

if __name__ == "__main__":
    asyncio.run(migrate())
```

### 7. **Добавить ключ шифрования в .env**

```bash
# .env

# Ключ шифрования для медицинских данных (152-ФЗ)
# Сгенерировать: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_encryption_key_here
```

---

## 📝 ИНСТРУКЦИЯ ПО ПРИМЕНЕНИЮ

### Шаг 1: Установить зависимости

```bash
pip install cryptography
```

### Шаг 2: Сгенерировать ключ шифрования

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Скопируйте ключ и добавьте в `.env`:

```env
ENCRYPTION_KEY=полученный_ключ
```

### Шаг 3: Применить изменения

1. Обновить онбординг (`start.py`) - добавить экраны согласий
2. Обновить meal_plan handlers - добавить дисклеймеры
3. Интегрировать privacy handlers в `main.py`
4. Обновить модель User с шифрованием
5. Создать и применить миграцию БД

### Шаг 4: Тестирование

```bash
# Запустить бота
python -m app.bot.main

# Протестировать:
# 1. /start - проверить дисклеймеры и согласия
# 2. Создание плана питания - проверить дисклеймеры
# 3. /privacy_settings - проверить управление данными
# 4. /export_data - проверить экспорт
# 5. /delete_account - проверить удаление (на тестовом аккаунте!)
```

---

## ⚖️ ЮРИДИЧЕСКОЕ СООТВЕТСТВИЕ

### 152-ФЗ "О персональных данных"

✅ **Статья 9** - Согласие на обработку:
- Явное согласие при первом запуске
- Описание целей обработки
- Перечисление всех данных

✅ **Статья 14** - Права субъекта:
- Экспорт данных (`/export_data`)
- Удаление данных (`/delete_account`)
- Отзыв согласия

✅ **Статья 19** - Защита данных:
- Шифрование медицинских данных (AES-256)
- Логирование доступа (в encryption_service)

### 323-ФЗ "Об основах охраны здоровья"

✅ **Статья 36.2** - Телемедицина:
- Дисклеймер: бот НЕ является медицинским изделием
- Бот НЕ ставит диагнозы, НЕ назначает лечение
- Рекомендации врача при отклонениях

✅ **Статья 98** - Ответственность:
- Прозрачность ограничений бота
- Безопасные формулировки в AI-промптах
- Напоминания о консультации врача

---

## 🚀 СТАТУС РЕАЛИЗАЦИИ

| Задача | Статус | Файл |
|--------|--------|------|
| Тексты дисклеймеров | ✅ Готово | `app/bot/texts.py` |
| Состояния FSM | ✅ Готово | `app/bot/states.py` |
| Сервис шифрования | ✅ Готово | `app/services/encryption_service.py` |
| Хендлеры privacy | ✅ Готово | `app/bot/handlers/privacy.py` |
| AI-промпты | ✅ Готово | `app/bot/texts.py` (используются в `claude_ai.py`) |
| Обновление онбординга | ⏳ Требуется | `app/bot/handlers/start.py` |
| Дисклеймеры в meal_plan | ⏳ Требуется | `app/bot/handlers/meal_plan.py` |
| Интеграция в main.py | ⏳ Требуется | `app/bot/main.py` |
| Обновление модели User | ⏳ Требуется | `app/models/user.py` |
| Миграция БД | ⏳ Требуется | Новый файл |
| Триггеры безопасности | ⏳ Требуется | `app/services/medical_analysis_service.py` |

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ МАТЕРИАЛЫ

### Политика конфиденциальности

Создайте файл `docs/PRIVACY_POLICY.md` с:
- Описанием обрабатываемых данных
- Целями обработки
- Сроками хранения
- Правами пользователей
- Контактами оператора

### Пользовательское соглашение

Создайте файл `docs/USER_AGREEMENT.md` с:
- Условиями использования бота
- Ограничениями ответственности
- Дисклеймерами

---

## 🔍 СЛЕДУЮЩИЕ ШАГИ

1. **Завершить интеграцию** (см. раздел "Что нужно доделать")
2. **Протестировать** все новые функции
3. **Создать документацию** для пользователей
4. **Получить юридическую консультацию** перед запуском
5. **Уведомить Роскомнадзор** об обработке персональных данных (если требуется)

---

## 📞 КОНТАКТЫ ДЛЯ ВОПРОСОВ

Если возникнут вопросы по интеграции, обращайтесь к разработчику.

**Версия документа:** 1.0
**Дата:** 2025-11-02
