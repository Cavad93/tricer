"""
Обработчик выбора рекомендованных блюд
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.user import User
from app.services.claude_ai import get_claude_service
from app.bot.keyboards import back_to_menu_keyboard

# Состояния conversation handler
WAITING_CUSTOM_MEAL = 1


async def handle_meal_variant_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора одного из рекомендованных вариантов
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    callback_data = query.data

    # Извлекаем номер варианта из callback_data
    variant_num = int(callback_data.split("_")[-1])  # meal_rec_variant_1 -> 1

    # Получаем сохраненные рекомендации из context
    recommendations = context.user_data.get("meal_recommendations")

    if not recommendations or "variants" not in recommendations:
        await query.edit_message_text(
            "❌ Рекомендации устарели. Пожалуйста, попросите новые рекомендации.",
            reply_markup=back_to_menu_keyboard()
        )
        return

    # Получаем выбранный вариант
    variants = recommendations["variants"]
    if variant_num < 1 or variant_num > len(variants):
        await query.edit_message_text(
            "❌ Неверный выбор варианта.",
            reply_markup=back_to_menu_keyboard()
        )
        return

    selected_variant = variants[variant_num - 1]

    # Проверяем безопасность выбора
    async with async_session_maker() as session:
        try:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await query.edit_message_text("❌ Пользователь не найден в системе.")
                return

            # Формируем контекст для проверки
            user_context = {
                "medical_restrictions": db_user.medical_restrictions or {},
                "allergies": db_user.allergies or [],
                "chronic_conditions": db_user.chronic_conditions or []
            }

            # Проверяем безопасность
            safety_check = await get_claude_service().check_meal_safety(
                meal_choice=selected_variant["name"],
                user_context=user_context
            )

            if not safety_check.get("is_safe", True):
                # Есть предупреждения
                warnings = safety_check.get("warnings", [])
                alternative = safety_check.get("alternative")

                warning_text = "⚠️ <b>Внимание!</b>\n\n"
                warning_text += f"Выбранное блюдо <b>{selected_variant['name']}</b> может вам навредить:\n\n"

                for warning in warnings:
                    warning_text += f"• {warning}\n"

                if alternative:
                    warning_text += f"\n💡 <b>Рекомендуем альтернативу:</b>\n\n"
                    warning_text += f"🍽 <b>{alternative['name']}</b>\n"
                    warning_text += f"📊 {alternative['calories']} ккал | "
                    warning_text += f"Б: {alternative['proteins']}г | "
                    warning_text += f"Ж: {alternative['fats']}г | "
                    warning_text += f"У: {alternative['carbs']}г\n\n"
                    warning_text += f"💭 {alternative['description']}"

                await query.edit_message_text(
                    warning_text,
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard()
                )
            else:
                # Блюдо безопасно, подтверждаем выбор
                from_plan_badge = "📋 " if selected_variant.get("from_plan") else ""

                response_text = f"✅ <b>Отличный выбор!</b>\n\n"
                response_text += f"{from_plan_badge}<b>{selected_variant['name']}</b>\n\n"
                response_text += f"📊 <b>Пищевая ценность:</b>\n"
                response_text += f"• Калории: {selected_variant['calories']} ккал\n"
                response_text += f"• Белки: {selected_variant['proteins']}г\n"
                response_text += f"• Жиры: {selected_variant['fats']}г\n"
                response_text += f"• Углеводы: {selected_variant['carbs']}г\n\n"
                response_text += f"💭 {selected_variant['description']}\n\n"
                response_text += "🍴 Приятного аппетита!"

                await query.edit_message_text(
                    response_text,
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard()
                )

                # Очищаем сохраненные рекомендации
                context.user_data.pop("meal_recommendations", None)

        except Exception as e:
            logger.error("Error handling meal variant choice: {}", repr(e), exc_info=True)
            await query.edit_message_text(
                "❌ Произошла ошибка при обработке выбора.",
                reply_markup=back_to_menu_keyboard()
            )


async def handle_custom_meal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало ввода своего варианта блюда
    """
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✏️ <b>Введите свой вариант</b>\n\n"
        "Напишите название блюда, которое вы хотите съесть.\n\n"
        "Например: <i>Жареная картошка с грибами</i>",
        parse_mode="HTML"
    )

    return WAITING_CUSTOM_MEAL


async def handle_custom_meal_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода своего варианта
    """
    user = update.effective_user
    meal_choice = update.message.text

    async with async_session_maker() as session:
        try:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await update.message.reply_text(
                    "❌ Пользователь не найден в системе.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Показываем индикатор "печатает..."
            await update.message.chat.send_action("typing")

            # Формируем контекст для проверки
            user_context = {
                "medical_restrictions": db_user.medical_restrictions or {},
                "allergies": db_user.allergies or [],
                "chronic_conditions": db_user.chronic_conditions or []
            }

            # Проверяем безопасность
            safety_check = await get_claude_service().check_meal_safety(
                meal_choice=meal_choice,
                user_context=user_context
            )

            if not safety_check.get("is_safe", True):
                # Есть предупреждения
                warnings = safety_check.get("warnings", [])
                alternative = safety_check.get("alternative")

                warning_text = "⚠️ <b>Внимание!</b>\n\n"
                warning_text += f"Выбранное блюдо <b>{meal_choice}</b> может вам навредить:\n\n"

                for warning in warnings:
                    warning_text += f"• {warning}\n"

                if alternative:
                    warning_text += f"\n💡 <b>Рекомендуем более безопасную альтернативу:</b>\n\n"
                    warning_text += f"🍽 <b>{alternative['name']}</b>\n"
                    warning_text += f"📊 {alternative['calories']} ккал | "
                    warning_text += f"Б: {alternative['proteins']}г | "
                    warning_text += f"Ж: {alternative['fats']}г | "
                    warning_text += f"У: {alternative['carbs']}г\n\n"
                    warning_text += f"💭 {alternative['description']}"

                await update.message.reply_text(
                    warning_text,
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard()
                )
            else:
                # Блюдо безопасно
                response_text = f"✅ <b>Отличный выбор!</b>\n\n"
                response_text += f"<b>{meal_choice}</b>\n\n"
                response_text += "🍴 Приятного аппетита!\n\n"
                response_text += "💡 <i>Не забудьте добавить это блюдо в дневник через меню \"Добавить еду\"</i>"

                await update.message.reply_text(
                    response_text,
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard()
                )

            # Очищаем сохраненные рекомендации
            context.user_data.pop("meal_recommendations", None)

            return ConversationHandler.END

        except Exception as e:
            logger.error("Error handling custom meal input: {}", repr(e), exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при проверке вашего выбора.",
                reply_markup=back_to_menu_keyboard()
            )
            return ConversationHandler.END


async def handle_meal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Передумал есть"
    """
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🚫 Хорошо, вы передумали есть.\n\n"
        "Если захотите поесть позже - просто напишите мне!",
        reply_markup=back_to_menu_keyboard()
    )

    # Очищаем сохраненные рекомендации
    context.user_data.pop("meal_recommendations", None)


async def cancel_custom_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отмена ввода своего варианта
    """
    await update.message.reply_text(
        "❌ Отменено.",
        reply_markup=back_to_menu_keyboard()
    )

    # Очищаем сохраненные рекомендации
    context.user_data.pop("meal_recommendations", None)

    return ConversationHandler.END
