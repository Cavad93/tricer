"""
Обработчик AI-чата в Telegram боте
"""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from app.db.session import async_session_maker
from app.services.chat_service import ChatService
from app.services.usage_service import UsageService
from app.services.claude_ai import claude_service
from app.models.chat import MessageRole
from app.models.user import User
from sqlalchemy import select
from app.bot.keyboards import back_to_menu_keyboard


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

            # Отправляем запрос к Claude API
            logger.info(f"Sending chat request to Claude for user {user.id}")

            assistant_response = await claude_service.chat(
                user_message=message_text,
                conversation_history=conversation_history,
                user_context=user_context
            )

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
                content=assistant_response
            )

            # Увеличиваем счетчик использования
            await UsageService.increment_chat_usage(session, db_user.id)

            # Проверяем новый остаток
            _, new_remaining = await UsageService.can_use_chat(session, db_user.id)

            # Формируем ответ
            response_text = assistant_response

            # Для Free пользователей добавляем информацию об остатке
            if new_remaining is not None:
                remaining_info = f"\n\n_Осталось сообщений сегодня: {new_remaining}_"
                if new_remaining <= 2:
                    remaining_info += "\n⚠️ _Лимит почти исчерпан!_"
                response_text += remaining_info

            await update.message.reply_text(
                response_text,
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard()
            )

            logger.info(f"AI-chat response sent to user {user.id}")

        except Exception as e:
            logger.error(f"Error in AI-chat for user {user.id}: {e}")

            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего сообщения.\n\n"
                "Пожалуйста, попробуйте:\n"
                "• Переформулировать вопрос\n"
                "• Задать более короткий вопрос\n"
                "• Попробовать позже\n\n"
                "Если проблема повторяется, обратитесь в поддержку.",
                reply_markup=back_to_menu_keyboard()
            )


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
            logger.error(f"Error clearing chat history for user {user.id}: {e}")

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
            logger.error(f"Error getting chat stats for user {user.id}: {e}")

            await update.message.reply_text(
                "❌ Произошла ошибка при получении статистики.",
                reply_markup=back_to_menu_keyboard()
            )
