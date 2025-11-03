# Реализация распределения задач между моделями Claude

## Актуальные модели Claude (2025)

### Claude Sonnet 4.5
- **API ID**: `claude-sonnet-4-5` или `claude-sonnet-4-5-20250929`
- **Цена**: $3/$15 per million tokens (input/output)
- **Использование**: Сложные задачи, требующие максимального качества
  - Анализ фото меню ресторана
  - Медицинский анализ (medical_analysis_service)
  - Сложные консультации в чате
  - Генерация детальных отчетов

### Claude Haiku 4.5
- **API ID**: `claude-haiku-4-5`
- **Цена**: $1/$5 per million tokens (input/output) - **в 3 раза дешевле**
- **Скорость**: в 2+ раза быстрее Sonnet
- **Использование**: Быстрые задачи с хорошим качеством
  - ✅ Составление дневных планов питания
  - ✅ Проверка дневника питания
  - ✅ Веб-поиск и извлечение данных о продуктах (DuckDuckGo + Claude)
  - Простые вопросы в чате

### Claude Haiku 3.5
- **API ID**: `claude-3-5-haiku-latest` или `claude-3-5-haiku-20241022`
- **Цена**: $1/$5 per million tokens (input/output)
- **Использование**: Vision tasks
  - ✅ Анализ фото еды (НЕ меню ресторана!)
  - Распознавание ингредиентов

---

## Распределение задач

### Haiku 4.5 (быстрая + дешевая)
1. **Составление дневных планов питания** - `meal_plan_service.py`
   - Метод: `generate_meal_plan()`
   - Простая структурированная задача

2. **Проверка дневника питания** - `diary_check_service.py` (если есть)
   - Валидация записей
   - Проверка КБЖУ

3. **Веб-поиск продуктов** - `web_search_service.py`
   - DuckDuckGo возвращает HTML
   - Haiku 4.5 извлекает: калории, белки, жиры, углеводы
   - **ВАЖНО**: Добавить извлечение микронутриентов (витамины + минералы)
   - Кэширование в БД (модель `Product`)

### Haiku 3.5 (Vision)
1. **Анализ фото еды** - `photo.py` handler
   - Метод: `claude_ai.analyze_food_photo()`
   - Распознавание блюд и ингредиентов
   - **НЕ используется для меню ресторана**

### Sonnet 4.5 (премиум)
1. **Анализ меню ресторана** - остается как есть
2. **Медицинский анализ** - `medical_analysis_service.py`
3. **Сложные консультации** - chat handler для детальных вопросов
4. **Все остальные функции** - по умолчанию

---

## План реализации

### ✅ Завершено
1. Проверка актуальных версий моделей API
2. Изучение структуры БД и AI использования
3. Создание модели `Product` для кэширования
4. Обновление `config.py` с настройками моделей

### 🔄 В процессе

#### 1. Обновить ClaudeAIService (app/services/claude_ai.py)

Добавить параметр `model` во все основные методы:

```python
async def analyze_food_photo(
    self,
    image_bytes: bytes,
    additional_context: str = "",
    model: Optional[str] = None  # ← ДОБАВИТЬ
) -> Dict:
    model_to_use = model or settings.CLAUDE_MODEL_HAIKU_3_5  # ← ИЗМЕНИТЬ

    # В вызове API:
    message = await self._call_with_rate_limit_and_retry(
        self.async_client.messages.create,
        model=model_to_use,  # ← ИСПОЛЬЗОВАТЬ
        ...
    )
```

Аналогично для всех методов:
- `analyze_food_photo()` → default: `CLAUDE_MODEL_HAIKU_3_5`
- `generate_meal_plan()` → default: `CLAUDE_MODEL_HAIKU_4_5`
- `search_product_nutrition()` → default: `CLAUDE_MODEL_HAIKU_4_5`
- `analyze_medical_data()` → default: `CLAUDE_MODEL_SONNET_4`
- Остальные → default: `self.model` (Sonnet 4.5)

#### 2. Обновить web_search_service.py

**Текущее состояние**: Использует DuckDuckGo для поиска, но **не извлекает микронутриенты**

**Требуется**:
1. Добавить использование Haiku 4.5 для анализа HTML
2. Извлекать не только КБЖУ, но и микронутриенты:
   - Витамины: A, B1, B2, B3, B6, B9, B12, C, D, E, K
   - Минералы: Fe (железо), Ca (кальций), Mg (магний), K (калий), Zn (цинк), и т.д.
3. Создать/использовать сервис для работы с БД `products`
4. Перед поиском - проверять наличие в кэше (по hash названия)
5. После поиска - сохранять в кэш с микронутриентами

**Структура промпта для Haiku 4.5**:
```python
prompt = f"""Проанализируй HTML страницу с информацией о продукте "{product_name}".

Извлеки следующие данные (на 100г продукта):

1. Макронутриенты:
   - Калории (ккал)
   - Белки (г)
   - Жиры (г)
   - Углеводы (г)

2. Микронутриенты (если есть в таблице):

   Витамины:
   - A (мкг)
   - B1/тиамин (мг)
   - B2/рибофлавин (мг)
   - B3/ниацин (мг)
   - B6/пиридоксин (мг)
   - B9/фолиевая кислота (мкг)
   - B12/кобаламин (мкг)
   - C/аскорбиновая кислота (мг)
   - D (мкг)
   - E (мг)
   - K (мкг)

   Минералы:
   - Железо/Fe (мг)
   - Кальций/Ca (мг)
   - Магний/Mg (мг)
   - Калий/K (мг)
   - Натрий/Na (мг)
   - Цинк/Zn (мг)
   - Фосфор/P (мг)
   - Йод/I (мкг)
   - Селен/Se (мкг)

Верни в формате JSON:
{{
  "name": "точное название продукта",
  "per_100g": {{
    "calories": number,
    "proteins": number,
    "fats": number,
    "carbs": number
  }},
  "micronutrients": {{
    "vitamins": {{
      "A": number or null,
      "B1": number or null,
      ...
    }},
    "minerals": {{
      "iron": number or null,
      "calcium": number or null,
      ...
    }}
  }},
  "source": "название сайта",
  "confidence": 0.0-1.0
}}

HTML:
{html_content}
"""
```

#### 3. Обновить meal_plan_service.py

Изменить вызов Claude для использования Haiku 4.5:

```python
# В методе generate_meal_plan()
meal_plan_response = await claude_service.generate_meal_plan(
    ...,
    model=settings.CLAUDE_MODEL_HAIKU_4_5  # ← ДОБАВИТЬ
)
```

#### 4. Обновить photo handler (app/bot/handlers/photo.py)

Изменить вызов для анализа фото еды:

```python
# В handle_photo()
food_data = await claude_service.analyze_food_photo(
    image_bytes,
    additional_context=context_str,
    model=settings.CLAUDE_MODEL_HAIKU_3_5  # ← ДОБАВИТЬ (уже по умолчанию)
)
```

#### 5. Создать ProductService для работы с кэшем

Файл: `app/services/product_service.py`

```python
from app.models.product import Product
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class ProductService:
    @staticmethod
    async def find_by_name(session: AsyncSession, name: str) -> Optional[Product]:
        """Найти продукт по названию"""
        name_hash = Product.generate_hash(name)
        result = await session.execute(
            select(Product).where(Product.name_hash == name_hash)
        )
        product = result.scalar_one_or_none()

        if product:
            # Обновить статистику
            product.usage_count += 1
            product.last_used_at = func.now()
            await session.commit()

        return product

    @staticmethod
    async def create_or_update(
        session: AsyncSession,
        name: str,
        calories: float,
        proteins: float,
        fats: float,
        carbs: float,
        micronutrients: dict,
        source: str,
        confidence: float = 1.0,
        category: str = None
    ) -> Product:
        """Создать или обновить продукт"""
        name_normalized = Product.normalize_name(name)
        name_hash = Product.generate_hash(name)

        # Проверить существование
        result = await session.execute(
            select(Product).where(Product.name_hash == name_hash)
        )
        product = result.scalar_one_or_none()

        if product:
            # Обновить существующий
            product.calories = calories
            product.proteins = proteins
            product.fats = fats
            product.carbs = carbs
            product.micronutrients = micronutrients
            product.confidence = max(product.confidence, confidence)  # Лучшая уверенность
            product.usage_count += 1
            product.last_used_at = func.now()
        else:
            # Создать новый
            product = Product(
                name=name,
                name_normalized=name_normalized,
                name_hash=name_hash,
                calories=calories,
                proteins=proteins,
                fats=fats,
                carbs=carbs,
                micronutrients=micronutrients,
                source=source,
                confidence=confidence,
                category=category
            )
            session.add(product)

        await session.commit()
        await session.refresh(product)
        return product
```

#### 6. Обновить отображение микронутриентов в UI

**В photo handler** после добавления еды:

```python
# После сохранения MealFood
if meal_food.micronutrients:
    # Форматируем топ-5 микронутриентов
    top_nutrients = _get_top_micronutrients(meal_food.micronutrients, limit=5)

    nutrient_text = "\n\n🌟 <b>Богат питательными веществами:</b>\n"
    for name, value, unit in top_nutrients:
        nutrient_text += f"  • {name}: {value:.1f} {unit}\n"

    # Добавить к сообщению
    message += nutrient_text

def _get_top_micronutrients(micronutrients: dict, limit: int = 5) -> list:
    """Получить топ-N микронутриентов"""
    all_nutrients = []

    vitamins = micronutrients.get("vitamins", {})
    for name, value in vitamins.items():
        if value and value > 0:
            unit = "мкг" if name in ["A", "B9", "B12", "D", "K"] else "мг"
            display_name = f"Витамин {name.upper()}"
            all_nutrients.append((display_name, value, unit))

    minerals = micronutrients.get("minerals", {})
    mineral_names = {
        "iron": "Железо",
        "calcium": "Кальций",
        "magnesium": "Магний",
        "potassium": "Калий",
        "zinc": "Цинк",
        "phosphorus": "Фосфор"
    }
    for key, value in minerals.items():
        if value and value > 0:
            name = mineral_names.get(key, key.title())
            unit = "мкг" if key in ["iodine", "selenium"] else "мг"
            all_nutrients.append((name, value, unit))

    # Сортировка по % от суточной нормы (упрощенно - по значению)
    all_nutrients.sort(key=lambda x: x[1], reverse=True)
    return all_nutrients[:limit]
```

#### 7. Создать миграцию БД

Файл: `migrations/add_products_table.py`

```python
"""
Добавление таблицы products для кэширования данных о продуктах
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

def upgrade():
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(500), nullable=False, index=True),
        sa.Column('name_normalized', sa.String(500), nullable=False, index=True),
        sa.Column('name_hash', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('calories', sa.Float(), nullable=False),
        sa.Column('proteins', sa.Float(), nullable=False),
        sa.Column('fats', sa.Float(), nullable=False),
        sa.Column('carbs', sa.Float(), nullable=False),
        sa.Column('micronutrients', JSONB, default=dict),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('usage_count', sa.Integer(), default=1),
        sa.Column('last_used_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Индексы
    op.create_index('idx_product_name_search', 'products', ['name_normalized'])
    op.create_index('idx_product_hash_unique', 'products', ['name_hash'], unique=True)

def downgrade():
    op.drop_table('products')
```

---

## Ожидаемые результаты

### Экономия токенов
- Планы питания: Haiku 4.5 вместо Sonnet → **экономия 66%**
- Фото еды: Haiku 3.5 вместо Sonnet → **экономия 66%**
- Веб-поиск: Haiku 4.5 → **новая функция, без дополнительных расходов**

### Улучшение UX
- ✅ Пользователь видит 3-5 главных витаминов/минералов при добавлении еды
- ✅ Данные кэшируются → повторные запросы мгновенные
- ✅ Быстрее генерация планов (Haiku 4.5 в 2+ раза быстрее)

### Качество данных
- ✅ Микронутриенты извлекаются из веб-источников
- ✅ Кэш продуктов для консистентности
- ✅ Статистика использования продуктов

---

## Порядок реализации

1. ✅ Config.py - настройка моделей
2. ✅ Product model - создание модели
3. 🔄 ClaudeAIService - добавить параметр model
4. 🔄 ProductService - сервис для работы с кэшем
5. 🔄 Web_search_service - Haiku 4.5 + микронутриенты
6. 🔄 Meal_plan_service - использовать Haiku 4.5
7. 🔄 Photo handler - Haiku 3.5 + отображение микронутриентов
8. 🔄 Миграция БД
9. 🔄 Тестирование

---

## Тестирование

### 1. Тест анализа фото
- Загрузить фото яблока
- Проверить, что используется Haiku 3.5
- Убедиться, что в ответе есть топ-5 микронутриентов

### 2. Тест веб-поиска
- Поиск "яблоко"
- Проверить, что данные сохранены в products
- Повторный поиск должен брать из кэша (мгновенно)
- Проверить наличие микронутриентов в БД

### 3. Тест планов питания
- Сгенерировать план на день
- Проверить использование Haiku 4.5 в логах
- Убедиться в корректности КБЖУ

---

## Документация для пользователя

После завершения реализации обновить:
- README.md - описание оптимизации моделей
- API_MODELS.md - подробности использования разных моделей
- MICRONUTRIENTS.md - как работает отображение витаминов/минералов
