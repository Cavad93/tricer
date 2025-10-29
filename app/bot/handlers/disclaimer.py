"""
Обработчики для дисклеймера
"""
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger

from app.bot.states import OnboardingStates


async def disclaimer_accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка согласия с дисклеймером"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Сохраняем согласие в БД
    from app.db.session import async_session_maker
    from app.models.user_consent import UserConsent
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Проверяем, есть ли уже запись
        result = await session.execute(
            select(UserConsent).where(UserConsent.telegram_id == user.id)
        )
        consent = result.scalar_one_or_none()

        if consent:
            # Обновляем существующую запись
            consent.medical_disclaimer_accepted = True
            consent.medical_disclaimer_accepted_at = datetime.utcnow()
            consent.updated_at = datetime.utcnow()
        else:
            # Создаем новую запись
            consent = UserConsent(
                telegram_id=user.id,
                medical_disclaimer_accepted=True,
                medical_disclaimer_accepted_at=datetime.utcnow(),
                medical_disclaimer_version="1.0"
            )
            session.add(consent)

        await session.commit()

    logger.info(f"User {user.id} accepted medical disclaimer")

    # Продолжаем онбординг
    await query.edit_message_text(
        "✅ Спасибо за согласие!\n\n"
        "Теперь давай начнем с настройки твоего профиля! Это займет всего 2 минуты.\n\n"
        "Как мне к тебе обращаться? Напиши своё имя:"
    )

    return OnboardingStates.PREFERRED_NAME


async def disclaimer_decline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка отказа от дисклеймера"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    logger.info(f"User {user.id} declined medical disclaimer")

    await query.edit_message_text(
        "❌ Без согласия с условиями я не могу работать с тобой.\n\n"
        "Это необходимо для твоей безопасности и соблюдения законодательства.\n\n"
        "Если передумаешь, просто напиши /start снова! 👋"
    )

    return ConversationHandler.END
