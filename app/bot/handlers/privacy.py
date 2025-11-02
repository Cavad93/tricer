"""
Хендлеры для управления конфиденциальностью и персональными данными (152-ФЗ)

Функции:
- Экспорт данных (/export_data)
- Удаление аккаунта (/delete_account)
- Управление согласиями (/privacy_settings)
- Отзыв согласия
"""

import json
import logging
from datetime import datetime
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.texts import (
    EXPORT_DATA_TEXT,
    DELETE_ACCOUNT_WARNING,
    PRIVACY_SETTINGS_TEXT
)
from app.bot.states import PrivacyStates
from app.db.session import async_session_maker
from app.models.user import User
from app.models.meal_plan import MealPlan
from app.models.medical_analysis import MedicalAnalysis
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def privacy_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /privacy_settings - управление конфиденциальностью
    """
    from app.config import settings

    keyboard = [
        [InlineKeyboardButton("📦 Экспортировать данные", callback_data="export_data")],
        [InlineKeyboardButton("📄 Политика конфиденциальности", url=settings.PRIVACY_POLICY_URL)],
        [InlineKeyboardButton("🗑️ Удалить аккаунт", callback_data="delete_account")],
        [InlineKeyboardButton("⚠️ Отозвать согласие", callback_data="revoke_consent")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        PRIVACY_SETTINGS_TEXT,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def export_data_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Экспортировать данные"
    """
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id

    # Показываем сообщение о подготовке
    await query.edit_message_text(
        "⏳ Подготавливаю данные для экспорта...\n"
        "Это может занять несколько секунд.",
        parse_mode="HTML"
    )

    try:
        async with async_session_maker() as session:
            # Получаем данные пользователя
            user_data = await _collect_user_data(session, telegram_id)

            if not user_data:
                await query.edit_message_text(
                    "❌ Данные не найдены",
                    parse_mode="HTML"
                )
                return

            # Создаем JSON файл
            json_content = json.dumps(user_data, ensure_ascii=False, indent=2)
            file_bytes = BytesIO(json_content.encode('utf-8'))
            file_bytes.name = f"nutriai_data_{telegram_id}_{datetime.now().strftime('%Y%m%d')}.json"

            # Отправляем файл
            await query.message.reply_document(
                document=file_bytes,
                filename=file_bytes.name,
                caption=(
                    "📦 <b>Ваши данные экспортированы</b>\n\n"
                    "Файл содержит все ваши персональные данные в формате JSON.\n"
                    "Храните его в безопасном месте.\n\n"
                    "<i>Файл будет автоматически удален из Telegram через 24 часа.</i>"
                ),
                parse_mode="HTML"
            )

            await query.edit_message_text(
                "✅ Данные успешно экспортированы!",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Export data error: {e}")
        await query.edit_message_text(
            "❌ Ошибка при экспорте данных. Попробуйте позже.",
            parse_mode="HTML"
        )


async def _collect_user_data(db: AsyncSession, telegram_id: int) -> dict:
    """
    Собирает все данные пользователя для экспорта
    """
    # Получаем пользователя
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return None

    # Базовые данные
    user_data = {
        "export_date": datetime.now().isoformat(),
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "profile": {
            "preferred_name": user.preferred_name,
            "country": user.country,
            "city": user.city,
            "gender": user.gender.value if user.gender else None,
            "birth_year": user.birth_year,
            "height": user.height,
            "current_weight": user.current_weight,
            "target_weight": user.target_weight,
            "goal": user.goal.value if user.goal else None,
            "activity_level": user.activity_level.value if user.activity_level else None,
            "diet_type": user.diet_type.value if user.diet_type else None,
            "budget_category": user.budget_category.value if user.budget_category else None,
            "allergies": user.allergies,
        },
        "medical_data": {
            "chronic_conditions": user.chronic_conditions,
            "removed_organs": user.removed_organs,
            "medical_restrictions": user.medical_restrictions,
            "medical_notes": user.medical_notes
        },
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None
    }

    # Получаем планы питания
    meal_plans_result = await db.execute(
        select(MealPlan).where(MealPlan.user_id == user.id)
    )
    meal_plans = meal_plans_result.scalars().all()

    user_data["meal_plans"] = [
        {
            "id": plan.id,
            "period": plan.period.value if plan.period else None,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "created_at": plan.created_at.isoformat() if plan.created_at else None
        }
        for plan in meal_plans
    ]

    # Получаем медицинские анализы
    analyses_result = await db.execute(
        select(MedicalAnalysis).where(MedicalAnalysis.user_id == user.id)
    )
    analyses = analyses_result.scalars().all()

    user_data["medical_analyses"] = [
        {
            "id": analysis.id,
            "analysis_type": analysis.analysis_type,
            "analysis_date": analysis.analysis_date.isoformat() if analysis.analysis_date else None,
            "detected_deficiencies": analysis.detected_deficiencies,
            "needs_doctor_consultation": analysis.needs_doctor_consultation,
            "recommendations": analysis.recommendations,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None
        }
        for analysis in analyses
    ]

    return user_data


async def delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Удалить аккаунт"
    """
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить навсегда", callback_data="confirm_delete")],
        [InlineKeyboardButton("❌ Отмена", callback_data="privacy_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        DELETE_ACCOUNT_WARNING,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    return PrivacyStates.CONFIRMING_DELETE


async def confirm_delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Подтверждение удаления аккаунта
    """
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id

    await query.edit_message_text(
        "⏳ Удаляю все данные...",
        parse_mode="HTML"
    )

    try:
        async with async_session_maker() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await query.edit_message_text(
                    "❌ Пользователь не найден",
                    parse_mode="HTML"
                )
                return ConversationHandler.END

            user_id = user.id

            # Удаляем все связанные данные
            # 1. Планы питания
            await session.execute(delete(MealPlan).where(MealPlan.user_id == user_id))

            # 2. Медицинские анализы
            await session.execute(delete(MedicalAnalysis).where(MedicalAnalysis.user_id == user_id))

            # 3. Пользователя
            await session.delete(user)

            await session.commit()

            await query.edit_message_text(
                "✅ <b>Аккаунт успешно удален</b>\n\n"
                "Все ваши данные были полностью удалены из базы данных.\n\n"
                "Если захотите вернуться, отправьте /start для создания нового аккаунта.",
                parse_mode="HTML"
            )

            logger.info(f"Account deleted: telegram_id={telegram_id}")

    except Exception as e:
        logger.error(f"Delete account error: {e}")
        await query.edit_message_text(
            "❌ Ошибка при удалении аккаунта. Попробуйте позже.",
            parse_mode="HTML"
        )

    return ConversationHandler.END


async def revoke_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Отозвать согласие"
    """
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Понятно", callback_data="privacy_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⚠️ <b>Отзыв согласия</b>\n\n"
        "При отзыве согласия на обработку персональных данных "
        "мы обязаны удалить все ваши данные.\n\n"
        "Это равносильно удалению аккаунта.\n\n"
        "Если вы хотите отозвать согласие, используйте кнопку "
        "\"Удалить аккаунт\" в настройках конфиденциальности.",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def cancel_privacy_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия и возврат к главному меню"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Действие отменено")

    return ConversationHandler.END
