"""
Handler для запроса отчетов о питании
"""
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from loguru import logger

from app.db.session import async_session_maker
from app.models.user import User
from app.services.nutrition_report_service import NutritionReportService
from app.services.pdf_report_generator import PDFReportGenerator
from sqlalchemy import select


# Состояния разговора
SELECTING_PERIOD = 1


async def reports_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало запроса отчета"""
    try:
        query = update.callback_query

        # Клавиатура выбора периода
        keyboard = [
            [InlineKeyboardButton("📊 График веса", callback_data="report_weight_chart")],
            [InlineKeyboardButton("За сегодня", callback_data="report_day")],
            [InlineKeyboardButton("За неделю", callback_data="report_week")],
            [InlineKeyboardButton("За месяц", callback_data="report_month")],
            [InlineKeyboardButton("Назад в меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "Выберите тип отчета:\n\n"
            "📊 <b>График веса</b> - визуализация изменения веса с момента регистрации\n\n"
            "<b>Отчеты о питании:</b>\n"
            "• Круговая диаграмма КБЖУ\n"
            "• Прогресс-бары по макронутриентам\n"
            "• Таблицы витаминов и минералов\n"
            "• Сравнение с целевыми значениями\n\n"
            "<i>Примечание: данные о микронутриентах являются приблизительной оценкой</i>"
        )

        if query:
            # ИСПРАВЛЕНО: если вызвано из callback (кнопка из меню)
            # используем edit_message_text для редактирования
            await query.answer()
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            # Если вызвано через команду
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

        return SELECTING_PERIOD

    except Exception as e:
        logger.error(f"Error in reports_start: {e}")
        if query:
            await query.message.reply_text("Произошла ошибка. Попробуйте позже.")
        else:
            await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END


async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация и отправка отчета"""
    try:
        query = update.callback_query
        await query.answer()

        period_type = query.data.replace("report_", "")

        # Отправляем сообщение о начале генерации
        status_message = await query.message.reply_text(
            "Генерирую отчет... Это может занять некоторое время."
        )

        telegram_id = query.from_user.id

        async with async_session_maker() as db:
            # Получаем пользователя
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await status_message.edit_text("Пользователь не найден. Пройдите /start.")
                return ConversationHandler.END

            # Определяем период
            today = date.today()

            if period_type == "day":
                report_data = await NutritionReportService.get_daily_report(
                    db, user.id, today
                )
            elif period_type == "week":
                start_date = today - timedelta(days=6)  # Последние 7 дней
                report_data = await NutritionReportService.get_period_report(
                    db, user.id, start_date, today, period_type="week"
                )
            elif period_type == "month":
                start_date = today - timedelta(days=29)  # Последние 30 дней
                report_data = await NutritionReportService.get_period_report(
                    db, user.id, start_date, today, period_type="month"
                )
            else:
                await status_message.edit_text("Неизвестный тип периода.")
                return ConversationHandler.END

            # Проверяем наличие данных
            if period_type == "day":
                if not report_data.get("meals"):
                    await status_message.edit_text(
                        "У вас пока нет данных о питании за сегодня.\n"
                        "Добавьте приемы пищи и попробуйте снова!"
                    )
                    return ConversationHandler.END
            else:
                if report_data["period"]["days_with_data"] == 0:
                    await status_message.edit_text(
                        f"У вас пока нет данных о питании за выбранный период.\n"
                        f"Добавьте приемы пищи и попробуйте снова!"
                    )
                    return ConversationHandler.END

            # Генерируем PDF
            try:
                pdf_path = await PDFReportGenerator.generate_nutrition_report_pdf(
                    report_data,
                    user_city=user.city
                )

                # Отправляем PDF
                with open(pdf_path, 'rb') as pdf_file:
                    period_names = {
                        "day": "день",
                        "week": "неделю",
                        "month": "месяц"
                    }
                    period_name = period_names.get(period_type, "период")

                    caption = (
                        f"Ваш отчет о питании за {period_name}\n\n"
                        f"<i>Данные о микронутриентах являются примерной оценкой</i>"
                    )

                    await query.message.reply_document(
                        document=pdf_file,
                        caption=caption,
                        parse_mode="HTML"
                    )

                await status_message.delete()

                # Показываем главное меню
                from app.bot.keyboards import get_main_menu_keyboard
                keyboard = get_main_menu_keyboard()

                await query.message.reply_text(
                    "Что бы вы хотели сделать дальше?",
                    reply_markup=keyboard
                )

            except Exception as e:
                logger.error(f"Error generating PDF: {e}")
                await status_message.edit_text(
                    "Произошла ошибка при генерации PDF.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in generate_report: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END


async def generate_weight_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация и отправка графика веса"""
    try:
        query = update.callback_query
        await query.answer()

        # Отправляем сообщение о начале генерации
        status_message = await query.message.reply_text(
            "📊 Генерирую график веса..."
        )

        telegram_id = query.from_user.id

        async with async_session_maker() as db:
            # Получаем пользователя
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await status_message.edit_text("Пользователь не найден. Пройдите /start.")
                return ConversationHandler.END

            # Получаем историю веса
            from app.services.weight_service import WeightService
            weight_history = await WeightService.get_weight_history(
                user_id=user.id,
                session=db,
                limit=100  # Последние 100 записей
            )

            # Сортируем по дате (от старых к новым для графика)
            weight_history = sorted(weight_history, key=lambda x: x.measured_at)

            if not weight_history or len(weight_history) < 2:
                await status_message.edit_text(
                    "📊 <b>Недостаточно данных для графика</b>\n\n"
                    "Для построения графика нужно минимум 2 измерения веса.\n\n"
                    "Добавьте новый вес через профиль (👤 Профиль → ⚖️ Изменить вес)",
                    parse_mode='HTML'
                )
                return ConversationHandler.END

            # Генерируем график
            try:
                from app.services.weight_chart_service import WeightChartService

                chart_buffer = WeightChartService.generate_weight_chart(
                    weight_history=weight_history,
                    target_weight=user.target_weight,
                    user_name=user.preferred_name or user.first_name,
                    height=user.height
                )

                # Формируем статистику для подписи
                start_weight = weight_history[0].weight
                current_weight = weight_history[-1].weight
                weight_change = current_weight - start_weight
                days_tracking = (weight_history[-1].measured_at - weight_history[0].measured_at).days

                if weight_change < 0:
                    change_text = f"📉 Потеря: {abs(weight_change):.1f} кг"
                elif weight_change > 0:
                    change_text = f"📈 Набор: {weight_change:.1f} кг"
                else:
                    change_text = "Вес стабилен"

                caption = (
                    f"📊 <b>График изменения веса</b>\n\n"
                    f"Начальный вес: {start_weight:.1f} кг\n"
                    f"Текущий вес: {current_weight:.1f} кг\n"
                    f"{change_text}\n"
                    f"Период: {days_tracking} дней\n"
                    f"Записей: {len(weight_history)}"
                )

                # Отправляем график
                await query.message.reply_photo(
                    photo=chart_buffer,
                    caption=caption,
                    parse_mode='HTML'
                )

                await status_message.delete()

                # Показываем главное меню
                from app.bot.keyboards import get_main_menu_keyboard
                keyboard = get_main_menu_keyboard()

                await query.message.reply_text(
                    "Что бы вы хотели сделать дальше?",
                    reply_markup=keyboard
                )

            except Exception as e:
                logger.error(f"Error generating weight chart: {e}")
                await status_message.edit_text(
                    "Произошла ошибка при генерации графика.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in generate_weight_chart: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END


async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена запроса отчета"""
    try:
        query = update.callback_query
        if query:
            await query.answer()

            # ИСПРАВЛЕНО: используем edit_message_text вместо reply_text
            # чтобы заменить текущее сообщение, а не создавать новое
            from app.bot.keyboards import main_menu_keyboard

            await query.edit_message_text(
                "Главное меню:",
                reply_markup=main_menu_keyboard()
            )
        else:
            # Если вызвано через команду (не callback)
            from app.bot.keyboards import main_menu_keyboard
            await update.message.reply_text(
                "Главное меню:",
                reply_markup=main_menu_keyboard()
            )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in cancel_report: {e}")
        return ConversationHandler.END


# Создаем ConversationHandler
def get_reports_conversation_handler():
    """Получить conversation handler для отчетов"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reports_start, pattern="^reports$"),
        ],
        states={
            SELECTING_PERIOD: [
                CallbackQueryHandler(generate_weight_chart, pattern="^report_weight_chart$"),
                CallbackQueryHandler(generate_report, pattern="^report_(day|week|month)$"),
                CallbackQueryHandler(cancel_report, pattern="^back_to_menu$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_report, pattern="^back_to_menu$"),
        ],
        name="reports_conversation",
        persistent=False,
        allow_reentry=True
    )
