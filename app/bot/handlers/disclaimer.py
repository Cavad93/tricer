"""
Обработчики для дисклеймера
"""
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


async def disclaimer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /disclaimer - показывает полный дисклеймер о функциях и ограничениях бота
    """
    from app.config import settings

    disclaimer_text = """
⚠️ <b>ВАЖНАЯ ИНФОРМАЦИЯ О NUTRIAI</b>

🔹 <b>ЧТО ТАКОЕ NUTRIAI?</b>

NutriAI - это <b>информационно-образовательный сервис</b> для планирования питания.

<b>В соответствии с Постановлением Правительства РФ №1684 от 01.03.2025</b>, данный бот <b>НЕ ЯВЛЯЕТСЯ медицинским изделием</b>, так как:

✅ НЕ выполняет диагностических функций
✅ НЕ используется для лечения заболеваний
✅ НЕ осуществляет мониторинг состояния здоровья
✅ Составляет рационы ТОЛЬКО на основе ваших пожеланий

🔹 <b>ЧТО ДЕЛАЕТ БОТ:</b>

✅ Помогает планировать рацион питания
✅ Считает калории и БЖУ
✅ Учитывает ваши пищевые предпочтения
✅ Адаптирует меню под ваш бюджет и образ жизни
✅ Предоставляет общую информацию о питании
✅ Персонализирует рацион с учетом wellness данных

🔹 <b>ЧТО БОТ НЕ ДЕЛАЕТ:</b>

❌ НЕ ставит медицинские диагнозы
❌ НЕ назначает лечение
❌ НЕ заменяет консультацию врача
❌ НЕ является медицинской услугой
❌ НЕ проводит мониторинг здоровья
❌ НЕ дает медицинских заключений

🔹 <b>ИСПОЛЬЗОВАНИЕ WELLNESS ДАННЫХ:</b>

Информация о хронических заболеваниях и удаленных органах:
• Используется ТОЛЬКО для персонализации рациона
• НЕ используется для диагностики или лечения
• Хранится в зашифрованном виде (AES-128)
• Не передается третьим лицам

🔹 <b>ЗАЩИТА ПЕРСОНАЛЬНЫХ ДАННЫХ (152-ФЗ):</b>

• Все данные зашифрованы
• Вы можете экспортировать свои данные: /export_data
• Вы можете удалить все данные: /delete_account
• Подробнее: <a href="{privacy_url}">Политика конфиденциальности</a>

⚠️ <b>ВАЖНОЕ НАПОМИНАНИЕ:</b>

При наличии заболеваний, приеме лекарств, беременности или любых вопросах о здоровье - <b>ОБЯЗАТЕЛЬНО проконсультируйтесь с врачом</b> перед изменением рациона питания.

При ухудшении самочувствия НЕМЕДЛЕННО обратитесь к врачу.
""".format(privacy_url=settings.PRIVACY_POLICY_URL)

    keyboard = [
        [InlineKeyboardButton("📄 Политика конфиденциальности", url=settings.PRIVACY_POLICY_URL)],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        disclaimer_text,
        reply_markup=reply_markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

    logger.info(f"User {update.effective_user.id} viewed disclaimer via /disclaimer command")
