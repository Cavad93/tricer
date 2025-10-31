"""
Обработчик AI-чата в Telegram боте
"""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from app.db.session import async_session_maker
from app.services.chat_service import ChatService
from app.services.usage_service import UsageService
from app.services.claude_ai import get_claude_service
from app.services.meal_recommendation_service import MealRecommendationService
from app.services.temporary_meal_plan_service import TemporaryMealPlanService
from app.models.chat import MessageRole
from app.models.user import User
from sqlalchemy import select
from app.bot.keyboards import back_to_menu_keyboard, meal_recommendations_keyboard


async def chat_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстовых сообщений для AI-чата
    """
    user = update.effective_user
    message_text = update.message.text

    logger.info(f"User {user.id} sent message to AI-chat: {message_text[:50]}...")

    # Показываем индикатор "печатает..."
    await update.message.chat.send_action("typing")

    async with async_session_maker() as session:
        try:
            # Получаем пользователя из БД
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await update.message.reply_text(
                    "❌ Пользователь не найден в системе.\n"
                    "Пожалуйста, пройдите регистрацию командой /start"
                )
                return

            # Проверяем лимиты использования
            can_use, remaining = await UsageService.can_use_chat(session, db_user.id)

            if not can_use:
                await update.message.reply_text(
                    "⚠️ *Дневной лимит сообщений исчерпан*\n\n"
                    f"Бесплатный план: {remaining if remaining is not None else 0} сообщений/день\n\n"
                    "🌟 Обновитесь до Premium для безлимитного доступа к AI-чату!\n\n"
                    "Premium включает:\n"
                    "• Безлимитный AI-чат\n"
                    "• Безлимитное распознавание фото\n"
                    "• Планирование меню\n"
                    "• Продвинутая аналитика\n\n"
                    "💳 Стоимость: 499₽/месяц",
                    parse_mode="Markdown",
                    reply_markup=back_to_menu_keyboard()
                )
                return

            # Получаем контекст пользователя
            user_context = await ChatService.get_user_context(session, db_user.id)

            # Получаем историю разговора (последние 10 сообщений)
            conversation_history = await ChatService.get_chat_context(session, db_user.id, message_limit=10)

            # ПРОВЕРКА: Спрашивает ли пользователь о еде?
            logger.info(f"Detecting food inquiry intent for user {user.id}")
            intent_result = await get_claude_service().detect_food_inquiry_intent(
                user_message=message_text,
                conversation_history=conversation_history
            )

            # Если это вопрос о еде - обрабатываем специальным образом
            if intent_result.get("is_food_inquiry", False) and intent_result.get("confidence") in ["high", "medium"]:
                logger.info(f"Food inquiry detected for user {user.id}, confidence: {intent_result.get('confidence')}")

                # Проверяем есть ли уже временный план на сегодня
                temp_plan = await TemporaryMealPlanService.get_today_plan(db_user.id, session)

                # Если есть временный план - предлагаем использовать его
                if temp_plan:
                    plan_data = temp_plan.get_meal_plan_data()
                    saved_recommendations = plan_data.get("recommendations", "")

                    if saved_recommendations:
                        assistant_response = {
                            "text_only": True,
                            "text": (
                                "📋 <b>У тебя уже есть рекомендации на сегодня:</b>\n\n"
                                f"{saved_recommendations}\n\n"
                                "💡 Хочешь новые рекомендации? Просто напиши еще раз!"
                            )
                        }
                    else:
                        # Генерируем новые рекомендации
                        assistant_response = await generate_meal_recommendations(
                            db_user, message_text, conversation_history, session, context
                        )
                else:
                    # Генерируем новые рекомендации
                    assistant_response = await generate_meal_recommendations(
                        db_user, message_text, conversation_history, session, context
                    )

            else:
                # Обычный чат через Claude API
                logger.info(f"Sending regular chat request to Claude for user {user.id}")

                assistant_response = await get_claude_service().chat(
                    user_message=message_text,
                    conversation_history=conversation_history,
                    user_context=user_context
                )

            # Проверяем тип ответа (dict или string)
            is_structured_recommendation = isinstance(assistant_response, dict) and not assistant_response.get("text_only", False)
            is_text_only = isinstance(assistant_response, dict) and assistant_response.get("text_only", False)

            # Текст для сохранения в историю
            if is_text_only:
                text_to_save = assistant_response["text"]
            elif is_structured_recommendation:
                import json
                text_to_save = json.dumps(assistant_response, ensure_ascii=False)
            else:
                text_to_save = assistant_response

            # Сохраняем сообщение пользователя
            await ChatService.save_message(
                session=session,
                user_id=db_user.id,
                role=MessageRole.USER,
                content=message_text
            )

            # Сохраняем ответ ассистента
            await ChatService.save_message(
                session=session,
                user_id=db_user.id,
                role=MessageRole.ASSISTANT,
                content=text_to_save
            )

            # Увеличиваем счетчик использования
            await UsageService.increment_chat_usage(session, db_user.id)

            # Проверяем новый остаток
            _, new_remaining = await UsageService.can_use_chat(session, db_user.id)

            # Определяем parse_mode
            parse_mode = "HTML" if intent_result.get("is_food_inquiry", False) else "Markdown"

            # Формируем и отправляем ответ
            if is_structured_recommendation:
                # Структурированные рекомендации с вариантами
                variants = assistant_response.get("variants", [])
                general_advice = assistant_response.get("general_advice", "")

                response_text = "🍽️ <b>Рекомендации для тебя:</b>\n\n"

                for i, variant in enumerate(variants, 1):
                    from_plan_badge = "📋 " if variant.get("from_plan") else ""
                    response_text += f"<b>Вариант {i}:</b> {from_plan_badge}{variant['name']}\n"
                    response_text += f"📊 {variant['calories']} ккал | "
                    response_text += f"Б: {variant['proteins']}г | "
                    response_text += f"Ж: {variant['fats']}г | "
                    response_text += f"У: {variant['carbs']}г\n"
                    response_text += f"💭 {variant['description']}\n\n"

                if general_advice:
                    response_text += f"💡 <b>Совет:</b> {general_advice}\n\n"

                response_text += "👇 <b>Выберите вариант:</b>"

                # Для Free пользователей добавляем информацию об остатке
                if new_remaining is not None:
                    remaining_info = f"\n\n<i>Осталось сообщений сегодня: {new_remaining}</i>"
                    if new_remaining <= 2:
                        remaining_info += "\n⚠️ <i>Лимит почти исчерпан!</i>"
                    response_text += remaining_info

                await update.message.reply_text(
                    response_text,
                    parse_mode="HTML",
                    reply_markup=meal_recommendations_keyboard()
                )
            else:
                # Текстовый ответ (обычный чат или text_only)
                response_text = text_to_save if is_text_only else assistant_response

                # Для Free пользователей добавляем информацию об остатке
                if new_remaining is not None:
                    remaining_info = f"\n\n_Осталось сообщений сегодня: {new_remaining}_"
                    if new_remaining <= 2:
                        remaining_info += "\n⚠️ _Лимит почти исчерпан!_"
                    response_text += remaining_info

                await update.message.reply_text(
                    response_text,
                    parse_mode=parse_mode,
                    reply_markup=back_to_menu_keyboard()
                )

            logger.info(f"AI-chat response sent to user {user.id}")

        except Exception as e:
            logger.error("Error in AI-chat for user {}: {}", user.id, repr(e))

            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего сообщения.\n\n"
                "Пожалуйста, попробуйте:\n"
                "• Переформулировать вопрос\n"
                "• Задать более короткий вопрос\n"
                "• Попробовать позже\n\n"
                "Если проблема повторяется, обратитесь в поддержку.",
                reply_markup=back_to_menu_keyboard()
            )


async def generate_meal_recommendations(
    db_user: User,
    message_text: str,
    conversation_history,
    session,
    context: ContextTypes.DEFAULT_TYPE
) -> dict:
    """
    Генерация рекомендаций по питанию для пользователя

    Args:
        db_user: Объект пользователя
        message_text: Сообщение пользователя
        conversation_history: История разговора
        session: Сессия БД
        context: Контекст Telegram бота

    Returns:
        Словарь с рекомендациями или текстом ошибки
    """
    try:
        # Собираем контекст для рекомендаций
        recommendation_context = await MealRecommendationService.generate_meal_recommendation_context(
            db_user, session
        )

        # Если у пользователя уже есть постоянный план - напоминаем об этом
        if recommendation_context["has_plan"] and recommendation_context["plan_type"] == "permanent":
            return {
                "text_only": True,
                "text": (
                    "📋 <b>Обрати внимание!</b>\n\n"
                    "У тебя уже есть <b>план питания</b> на сегодня. "
                    "Рекомендую посмотреть его через главное меню → \"План питания\".\n\n"
                    "Если всё же хочешь получить разовую рекомендацию, напиши мне еще раз!"
                )
            }

        # Генерируем рекомендации через Claude AI
        logger.info(f"Generating meal recommendations for user {db_user.id}")
        recommendations = await get_claude_service().generate_meal_recommendation(
            user_message=message_text,
            recommendation_context=recommendation_context,
            conversation_history=conversation_history
        )

        # Сохраняем рекомендации в context для дальнейшего использования
        context.user_data["meal_recommendations"] = recommendations

        # Сохраняем рекомендации во временный план
        try:
            import json
            remaining = recommendation_context["remaining"]
            await TemporaryMealPlanService.create_or_update_plan(
                user_id=db_user.id,
                meal_plan_data={
                    "recommendations": json.dumps(recommendations, ensure_ascii=False),
                    "meal_type": recommendation_context["meal_type"],
                    "generated_at": recommendation_context["current_time"],
                    "context": {
                        "remaining_calories": remaining["remaining_calories"],
                        "bonus_calories": remaining["bonus_calories"]
                    }
                },
                total_calories=remaining["target_calories"],
                session=session
            )
            logger.info(f"Saved temporary meal plan for user {db_user.id}")
        except Exception as e:
            logger.error("Error saving temporary meal plan for user {}: {}", db_user.id, repr(e))
            # Не прерываем процесс, если не удалось сохранить

        return recommendations

    except Exception as e:
        logger.error("Error generating meal recommendations for user {}: {}", db_user.id, repr(e), exc_info=True)
        return {
            "text_only": True,
            "text": (
                "❌ Произошла ошибка при генерации рекомендаций.\n\n"
                "Попробуй спросить по-другому или создай полноценный план питания через меню!"
            )
        }


async def clear_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для очистки истории чата
    """
    user = update.effective_user

    async with async_session_maker() as session:
        try:
            # Получаем пользователя из БД
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await update.message.reply_text("❌ Пользователь не найден в системе.")
                return

            # Очищаем историю
            count = await ChatService.clear_chat_history(session, db_user.id)

            await update.message.reply_text(
                f"✅ История чата очищена!\n\n"
                f"Удалено сообщений: {count}\n\n"
                "Теперь можете начать новый разговор с чистого листа.",
                reply_markup=back_to_menu_keyboard()
            )

            logger.info(f"Chat history cleared for user {user.id}, deleted {count} messages")

        except Exception as e:
            logger.error("Error clearing chat history for user {}: {}", user.id, repr(e))

            await update.message.reply_text(
                "❌ Произошла ошибка при очистке истории.",
                reply_markup=back_to_menu_keyboard()
            )


async def chat_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для просмотра статистики чата
    """
    user = update.effective_user

    async with async_session_maker() as session:
        try:
            # Получаем пользователя из БД
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await update.message.reply_text("❌ Пользователь не найден в системе.")
                return

            # Получаем статистику использования
            stats = await UsageService.get_usage_stats(session, db_user.id)

            # Получаем количество сообщений в истории
            total_messages = await ChatService.get_total_messages_count(session, db_user.id)

            stats_text = (
                "📊 *Статистика использования*\n\n"
                f"💬 *AI-чат:*\n"
                f"• Сообщений сегодня: {stats['chat_messages']}"
            )

            if stats['is_premium']:
                stats_text += " (безлимит)\n"
            else:
                stats_text += f"/{stats['chat_limit']}\n"

            stats_text += (
                f"• Всего в истории: {total_messages} сообщений\n\n"
                f"📸 *Распознавание фото:*\n"
                f"• Использовано сегодня: {stats['photo_recognitions']}"
            )

            if stats['is_premium']:
                stats_text += " (безлимит)\n"
            else:
                stats_text += f"/{stats['photo_limit']}\n"

            stats_text += f"\n💎 Статус: {'Premium' if stats['is_premium'] else 'Free'}"

            if not stats['is_premium']:
                stats_text += (
                    "\n\n_Обновитесь до Premium для безлимитного доступа!_"
                )

            await update.message.reply_text(
                stats_text,
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error("Error getting chat stats for user {}: {}", user.id, repr(e))

            await update.message.reply_text(
                "❌ Произошла ошибка при получении статистики.",
                reply_markup=back_to_menu_keyboard()
            )
