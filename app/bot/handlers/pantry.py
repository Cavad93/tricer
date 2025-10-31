"""
Обработчики для управления продуктами дома (кладовая)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger

from app.db.session import async_session_maker
from app.models.user import User
from app.services.pantry_service import PantryService
from app.services.claude_ai import ClaudeAIService
from app.bot.keyboards import main_menu_keyboard, back_to_menu_keyboard
from sqlalchemy import select

# Импортируем состояния
from app.bot.states import PantryStates

# Константы состояний для удобства
WAITING_PRODUCTS_INPUT = PantryStates.WAITING_PRODUCTS_INPUT
EDITING_PRODUCT_QUANTITY = PantryStates.EDITING_PRODUCT_QUANTITY
REVIEWING_FOR_PLAN = PantryStates.REVIEWING_FOR_PLAN


async def pantry_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы с кладовой - показ текущих продуктов"""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user

    try:
        async with async_session_maker() as session:
            # Получаем продукты пользователя
            pantry_items = await PantryService.get_user_pantry(session, user.id)

            if not pantry_items:
                text = (
                    "🏠 <b>Ваша кладовая пуста</b>\n\n"
                    "Добавьте продукты, которые есть дома, и я смогу:\n"
                    "• Составить рацион из того, что у вас есть\n"
                    "• Отслеживать остатки продуктов\n"
                    "• Предупредить когда что-то закончится\n\n"
                    "Что хотите сделать?"
                )

                keyboard = [
                    [InlineKeyboardButton("➕ Добавить продукты", callback_data="pantry_add")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]
            else:
                # Группируем по категориям
                categories = {}
                for item in pantry_items:
                    cat = item.category or "Другое"
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(item)

                text = "🏠 <b>Ваши продукты</b>\n\n"

                for category, items in sorted(categories.items()):
                    text += f"<b>{category}:</b>\n"
                    for item in items:
                        text += f"  • {item.product_name}: {item.quantity}{item.unit}\n"
                    text += "\n"

                # Оценка на сколько дней хватит
                days_supply = await PantryService.estimate_days_supply(session, user.id)
                text += f"📊 <i>Примерно на {days_supply} дней</i>\n\n"

                text += "Что хотите сделать?"

                keyboard = [
                    [InlineKeyboardButton("➕ Добавить продукты", callback_data="pantry_add")],
                    [InlineKeyboardButton("🗑 Удалить продукты", callback_data="pantry_delete_list")],
                    [InlineKeyboardButton("🍽 Создать рацион из этих продуктов", callback_data="pantry_create_plan")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]

            if query:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )

    except Exception as e:
        logger.error("Error showing pantry for user {}: {}", user.id, repr(e))
        error_text = "❌ Ошибка при загрузке кладовой"

        if query:
            await query.edit_message_text(error_text, reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text(error_text, reply_markup=main_menu_keyboard())


async def pantry_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления продуктов"""
    query = update.callback_query
    await query.answer()

    text = (
        "➕ <b>Добавление продуктов</b>\n\n"
        "Напишите список продуктов, которые есть дома. Можно в свободной форме.\n\n"
        "<b>Пример:</b>\n"
        "Курица 1кг\n"
        "Рис 500г\n"
        "Картофель 2кг\n"
        "Помидоры 5шт\n"
        "Молоко 1л\n\n"
        "Или просто перечислите:\n"
        "Курица, рис, картофель, помидоры, молоко\n\n"
        "AI поможет распознать и структурировать ваш список!"
    )

    await query.edit_message_text(text, parse_mode="HTML")
    return WAITING_PRODUCTS_INPUT


async def pantry_process_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного списка продуктов через AI"""
    user = update.effective_user
    products_text = update.message.text

    # Отправляем сообщение о процессе
    processing_msg = await update.message.reply_text(
        "🔄 Обрабатываю список продуктов..."
    )

    try:
        # Используем AI для парсинга списка продуктов
        claude_service = ClaudeAIService()

        prompt = f"""Проанализируй список продуктов и верни JSON массив.

СПИСОК ПРОДУКТОВ:
{products_text}

Верни JSON массив в формате:
[
  {{
    "name": "название продукта",
    "quantity": числовое_количество,
    "unit": "единица измерения (г, кг, шт, л, мл)",
    "category": "категория (Овощи, Фрукты, Мясо, Рыба, Крупы, Молочка, Другое)"
  }}
]

ВАЖНО:
- Если количество не указано, используй 1 и единицу "шт"
- Категории на русском
- Верни ТОЛЬКО JSON, без дополнительного текста"""

        response = await claude_service.async_client.messages.create(
            model=claude_service.model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Парсим ответ
        response_text = response.content[0].text
        parsed_products = claude_service.extract_json_from_response(response_text)

        if not parsed_products or not isinstance(parsed_products, list):
            await processing_msg.edit_text(
                "❌ Не удалось распознать продукты. Попробуйте ещё раз."
            )
            return ConversationHandler.END

        # Сохраняем продукты в БД
        async with async_session_maker() as session:
            added_count = 0

            for product in parsed_products:
                try:
                    await PantryService.add_product(
                        session,
                        user_id=user.id,
                        product_name=product.get("name", "Неизвестно"),
                        quantity=float(product.get("quantity", 1)),
                        unit=product.get("unit", "шт"),
                        category=product.get("category")
                    )
                    added_count += 1
                except Exception as e:
                    logger.error("Error adding product: {}", repr(e))

        # Формируем результат
        result_text = f"✅ <b>Добавлено продуктов: {added_count}</b>\n\n"

        for product in parsed_products:
            result_text += f"• {product['name']}: {product['quantity']}{product['unit']}\n"

        result_text += "\n\nЧто дальше?"

        keyboard = [
            [InlineKeyboardButton("➕ Добавить ещё", callback_data="pantry_add")],
            [InlineKeyboardButton("📋 Посмотреть все продукты", callback_data="pantry")],
            [InlineKeyboardButton("🍽 Создать рацион", callback_data="pantry_create_plan")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]

        await processing_msg.edit_text(
            result_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error("Error processing pantry input for user {}: {}", user.id, repr(e))
        await processing_msg.edit_text(
            "❌ Ошибка при обработке списка. Попробуйте ещё раз.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def pantry_delete_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список продуктов для удаления"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        async with async_session_maker() as session:
            pantry_items = await PantryService.get_user_pantry(session, user.id)

            if not pantry_items:
                await query.edit_message_text(
                    "📝 У вас нет продуктов в кладовой",
                    reply_markup=main_menu_keyboard()
                )
                return

            text = "🗑 <b>Выберите продукт для удаления:</b>\n\n"

            keyboard = []
            for item in pantry_items[:20]:  # Показываем первые 20
                button_text = f"{item.product_name} ({item.quantity}{item.unit})"
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"pantry_delete_{item.id}"
                )])

            keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error("Error showing delete list for user {}: {}", user.id, repr(e))
        await query.edit_message_text(
            "❌ Ошибка при загрузке списка",
            reply_markup=main_menu_keyboard()
        )


async def pantry_delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить продукт из кладовой"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        # Извлекаем ID продукта
        item_id = int(query.data.replace("pantry_delete_", ""))

        async with async_session_maker() as session:
            success = await PantryService.delete_product(session, item_id, user.id)

            if success:
                await query.edit_message_text(
                    "✅ Продукт удален из кладовой",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    "❌ Продукт не найден или уже удален",
                    reply_markup=main_menu_keyboard()
                )

    except Exception as e:
        logger.error("Error deleting pantry item for user {}: {}", user.id, repr(e))
        await query.edit_message_text(
            "❌ Ошибка при удалении",
            reply_markup=main_menu_keyboard()
        )


async def pantry_create_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания плана из продуктов - показ списка с возможностью редактирования"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        async with async_session_maker() as session:
            pantry_items = await PantryService.get_user_pantry(session, user.id)

            if not pantry_items:
                await query.edit_message_text(
                    "📝 У вас нет продуктов в кладовой.\n\n"
                    "Сначала добавьте продукты, которые есть дома.",
                    reply_markup=main_menu_keyboard()
                )
                return ConversationHandler.END

            # Сохраняем список продуктов в контексте для дальнейшего использования
            context.user_data["pantry_products_for_plan"] = {
                item.id: {
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "category": item.category
                }
                for item in pantry_items
            }

            # Формируем текст со списком продуктов
            text = (
                "🍽 <b>Создание рациона из продуктов</b>\n\n"
                "Проверьте количество продуктов. Если что-то уже съели или количество изменилось - "
                "нажмите на продукт для редактирования.\n\n"
                "<b>Ваши продукты:</b>\n"
            )

            # Группируем по категориям
            categories = {}
            for item_id, item_data in context.user_data["pantry_products_for_plan"].items():
                cat = item_data["category"] or "Другое"
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append((item_id, item_data))

            for category, items in sorted(categories.items()):
                text += f"\n<b>{category}:</b>\n"
                for item_id, item_data in items:
                    text += f"  • {item_data['name']}: {item_data['quantity']}{item_data['unit']}\n"

            text += "\n💡 Нажмите на продукт чтобы изменить количество"

            # Создаем кнопки для редактирования каждого продукта
            keyboard = []
            for item_id, item_data in context.user_data["pantry_products_for_plan"].items():
                button_text = f"✏️ {item_data['name']} ({item_data['quantity']}{item_data['unit']})"
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"pantry_edit_for_plan_{item_id}"
                )])

            # Кнопки действий
            keyboard.append([InlineKeyboardButton("✅ Всё верно, создать рацион!", callback_data="pantry_confirm_create_plan")])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )

            return REVIEWING_FOR_PLAN

    except Exception as e:
        logger.error("Error starting plan creation from pantry for user {}: {}", user.id, repr(e))
        await query.edit_message_text(
            "❌ Ошибка при загрузке продуктов",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def pantry_edit_product_for_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования количества продукта для плана"""
    query = update.callback_query
    await query.answer()

    try:
        # Извлекаем ID продукта
        item_id = int(query.data.replace("pantry_edit_for_plan_", ""))

        # Проверяем что продукт есть в контексте
        if "pantry_products_for_plan" not in context.user_data:
            await query.edit_message_text(
                "❌ Ошибка: данные не найдены. Начните заново.",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END

        if item_id not in context.user_data["pantry_products_for_plan"]:
            await query.edit_message_text(
                "❌ Продукт не найден",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END

        # Сохраняем ID редактируемого продукта
        context.user_data["editing_product_id"] = item_id
        item_data = context.user_data["pantry_products_for_plan"][item_id]

        text = (
            f"✏️ <b>Редактирование продукта</b>\n\n"
            f"<b>{item_data['name']}</b>\n"
            f"Текущее количество: {item_data['quantity']}{item_data['unit']}\n\n"
            f"Введите новое количество.\n\n"
            f"<b>Примеры:</b>\n"
            f"• 500\n"
            f"• 1.5кг\n"
            f"• 10шт\n"
            f"• 2л\n\n"
            f"Или введите <b>0</b> чтобы убрать продукт из рациона."
        )

        await query.edit_message_text(text, parse_mode="HTML")
        return EDITING_PRODUCT_QUANTITY

    except Exception as e:
        logger.error("Error starting product edit: {}", repr(e))
        await query.edit_message_text(
            "❌ Ошибка",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def pantry_save_edited_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение отредактированного количества продукта"""
    user = update.effective_user
    text_input = update.message.text.strip()

    try:
        editing_product_id = context.user_data.get("editing_product_id")
        if not editing_product_id or "pantry_products_for_plan" not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: данные не найдены",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END

        item_data = context.user_data["pantry_products_for_plan"][editing_product_id]

        # Парсим введенное количество
        import re
        # Ищем число (может быть с точкой/запятой)
        number_match = re.search(r'(\d+(?:[.,]\d+)?)', text_input)
        if not number_match:
            await update.message.reply_text(
                "❌ Не удалось распознать количество. Попробуйте ещё раз.\n\n"
                "Примеры: 500, 1.5кг, 10шт",
                reply_markup=main_menu_keyboard()
            )
            return EDITING_PRODUCT_QUANTITY

        quantity = float(number_match.group(1).replace(',', '.'))

        # Ищем единицу измерения
        unit_match = re.search(r'(кг|г|л|мл|шт)', text_input.lower())
        if unit_match:
            unit = unit_match.group(1)
        else:
            # Используем текущую единицу измерения
            unit = item_data["unit"]

        # Если количество 0 - удаляем продукт из списка
        if quantity == 0:
            del context.user_data["pantry_products_for_plan"][editing_product_id]
            confirmation = f"✅ Продукт <b>{item_data['name']}</b> убран из списка для рациона."
        else:
            # Обновляем количество
            context.user_data["pantry_products_for_plan"][editing_product_id]["quantity"] = quantity
            context.user_data["pantry_products_for_plan"][editing_product_id]["unit"] = unit
            confirmation = f"✅ Обновлено: <b>{item_data['name']}</b> - {quantity}{unit}"

        # Показываем обновленный список
        text = f"{confirmation}\n\n<b>Текущий список продуктов:</b>\n"

        # Группируем по категориям
        categories = {}
        for item_id, data in context.user_data["pantry_products_for_plan"].items():
            cat = data["category"] or "Другое"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((item_id, data))

        for category, items in sorted(categories.items()):
            text += f"\n<b>{category}:</b>\n"
            for item_id, data in items:
                text += f"  • {data['name']}: {data['quantity']}{data['unit']}\n"

        text += "\n💡 Нажмите на продукт чтобы изменить количество"

        # Создаем кнопки
        keyboard = []
        for item_id, data in context.user_data["pantry_products_for_plan"].items():
            button_text = f"✏️ {data['name']} ({data['quantity']}{data['unit']})"
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"pantry_edit_for_plan_{item_id}"
            )])

        keyboard.append([InlineKeyboardButton("✅ Всё верно, создать рацион!", callback_data="pantry_confirm_create_plan")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return REVIEWING_FOR_PLAN

    except Exception as e:
        logger.error("Error saving edited quantity for user {}: {}", user.id, repr(e))
        await update.message.reply_text(
            "❌ Ошибка при сохранении. Попробуйте ещё раз.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def pantry_confirm_and_create_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и создание плана питания из продуктов"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    try:
        # Проверяем что есть продукты
        if "pantry_products_for_plan" not in context.user_data or not context.user_data["pantry_products_for_plan"]:
            await query.edit_message_text(
                "❌ Нет продуктов для создания рациона",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END

        # Формируем список продуктов для AI
        products_list = []
        for item_id, item_data in context.user_data["pantry_products_for_plan"].items():
            products_list.append(f"{item_data['name']} ({item_data['quantity']}{item_data['unit']})")

        products_text = "\n".join(products_list)

        # Сохраняем в контексте для использования в meal_plan
        context.user_data["create_plan_from_pantry"] = True
        context.user_data["pantry_products_text"] = products_text

        # Переходим к созданию плана питания
        text = (
            "🍽 <b>Создание рациона из продуктов</b>\n\n"
            "Отлично! Сейчас создам план питания на основе ваших продуктов:\n\n"
            f"{products_text}\n\n"
            "На какой период создать план?"
        )

        keyboard = [
            [InlineKeyboardButton("📅 На 1 день", callback_data="plan_period_day")],
            [InlineKeyboardButton("📅 На неделю", callback_data="plan_period_week")],
            [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        # Очищаем временные данные
        if "editing_product_id" in context.user_data:
            del context.user_data["editing_product_id"]

        return ConversationHandler.END

    except Exception as e:
        logger.error("Error confirming plan creation for user {}: {}", user_id, repr(e))
        await query.edit_message_text(
            "❌ Ошибка при создании плана",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def cancel_pantry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции с кладовой"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ Операция отменена",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=main_menu_keyboard()
        )

    return ConversationHandler.END
