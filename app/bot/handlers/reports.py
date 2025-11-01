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
            [InlineKeyboardButton("💡 Интересные факты", callback_data="wellness_insights")],
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
        logger.error("Error in reports_start: {}", repr(e))
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
                    keyboard = [
                        [InlineKeyboardButton("📊 Другой отчёт", callback_data="another_report")],
                        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await status_message.edit_text(
                        "У вас пока нет данных о питании за сегодня.\n"
                        "Добавьте приемы пищи и попробуйте снова!",
                        reply_markup=reply_markup
                    )
                    return SELECTING_PERIOD
            else:
                if report_data["period"]["days_with_data"] == 0:
                    keyboard = [
                        [InlineKeyboardButton("📊 Другой отчёт", callback_data="another_report")],
                        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await status_message.edit_text(
                        f"У вас пока нет данных о питании за выбранный период.\n"
                        f"Добавьте приемы пищи и попробуйте снова!",
                        reply_markup=reply_markup
                    )
                    return SELECTING_PERIOD

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

                # Показываем кнопки для продолжения
                keyboard = [
                    [InlineKeyboardButton("📊 Другой отчёт", callback_data="another_report")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.message.reply_text(
                    "Что бы вы хотели сделать дальше?",
                    reply_markup=reply_markup
                )

            except Exception as e:
                logger.error("Error generating PDF: {}", repr(e))
                await status_message.edit_text(
                    "Произошла ошибка при генерации PDF.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
                return ConversationHandler.END

        return SELECTING_PERIOD

    except Exception as e:
        logger.error("Error in generate_report: {}", repr(e))
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
                keyboard = [
                    [InlineKeyboardButton("📊 Другой отчёт", callback_data="another_report")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await status_message.edit_text(
                    "📊 <b>Недостаточно данных для графика</b>\n\n"
                    "Для построения графика нужно минимум 2 измерения веса.\n\n"
                    "Добавьте новый вес через профиль (👤 Профиль → ⚖️ Изменить вес)",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return SELECTING_PERIOD

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

                # Показываем кнопки для продолжения
                keyboard = [
                    [InlineKeyboardButton("📊 Другой отчёт", callback_data="another_report")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.message.reply_text(
                    "Что бы вы хотели сделать дальше?",
                    reply_markup=reply_markup
                )

            except Exception as e:
                logger.error("Error generating weight chart: {}", repr(e))
                await status_message.edit_text(
                    "Произошла ошибка при генерации графика.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
                return ConversationHandler.END

        return SELECTING_PERIOD

    except Exception as e:
        logger.error("Error in generate_weight_chart: {}", repr(e))
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
        logger.error("Error in cancel_report: {}", repr(e))
        return ConversationHandler.END


async def wellness_insights_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки 'Интересные факты'
    Показывает пользователю найденные корреляции между едой и самочувствием
    """
    try:
        query = update.callback_query
        await query.answer()

        # Показываем прогресс
        status_message = await query.edit_message_text(
            "🔍 Собираю интересные факты о вашем питании и самочувствии...\n\n"
            "Это может занять несколько секунд."
        )

        user_id = query.from_user.id

        async with async_session_maker() as db:
            # Получаем пользователя
            result = await db.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await status_message.edit_text(
                    "❌ Пользователь не найден. Пройдите /start.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад", callback_data="reports")
                    ]])
                )
                return ConversationHandler.END

            # Импортируем сервис анализа корреляций
            from app.services.correlation_analysis_service import CorrelationAnalysisService

            correlation_service = CorrelationAnalysisService()

            # Получаем сохраненные интересные факты
            insights = await correlation_service.get_user_insights(db, user.id, active_only=True)

            # Если фактов нет, запускаем анализ
            if not insights:
                await status_message.edit_text(
                    "🔄 Анализирую ваши данные, чтобы найти интересные закономерности...\n\n"
                    "Это займет около минуты."
                )

                # Запускаем анализ
                insights = await correlation_service.analyze_user_correlations(
                    db, user.id, days_back=90
                )

            # Если фактов все еще нет
            if not insights:
                await status_message.edit_text(
                    "📊 <b>Недостаточно данных для анализа</b>\n\n"
                    "Для поиска интересных закономерностей нужно:\n"
                    "• Регулярно добавлять приемы пищи (минимум 10-20 раз)\n"
                    "• Заполнять опросы о самочувствии после еды\n"
                    "• Делать это как минимум 2-3 недели\n\n"
                    "💡 <b>Как это работает:</b>\n"
                    "Бот анализирует связь между продуктами и вашим самочувствием, "
                    "ищет устойчивые закономерности (достоверность 95%+) и объясняет их научно.\n\n"
                    "Продолжайте вести дневник питания, и скоро здесь появятся персональные инсайты!",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Назад к отчётам", callback_data="reports")
                    ]])
                )
                return ConversationHandler.END

            # Формируем сообщение с фактами
            message_parts = [
                "💡 <b>Интересные факты о вашем питании</b>\n\n"
                f"Найдено закономерностей: {len(insights)}\n"
                "Все факты основаны на ваших данных с достоверностью 95%+\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
            ]

            # Добавляем каждый факт
            for i, insight in enumerate(insights, 1):
                fact_text = insight.get_user_friendly_text()
                message_parts.append(f"<b>Факт #{i}</b>\n{fact_text}\n")
                message_parts.append("━━━━━━━━━━━━━━━━━━━━\n\n")

                # Telegram ограничивает длину сообщения до 4096 символов
                # Если сообщение становится слишком длинным, разбиваем на части
                current_message = "".join(message_parts)
                if len(current_message) > 3500 and i < len(insights):
                    # Отправляем текущую часть
                    await query.message.reply_text(
                        current_message,
                        parse_mode="HTML"
                    )
                    # Начинаем новую часть
                    message_parts = []

            # Отправляем последнюю часть (или единственное сообщение)
            final_message = "".join(message_parts)
            final_message += (
                "💡 <b>Как использовать эти факты:</b>\n"
                "• Бот автоматически учитывает их при составлении рациона\n"
                "• AI-чат знает о них и даст персональные советы\n"
                "• При добавлении еды вы получите предупреждения о возможных эффектах"
            )

            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data="insights_statistics")],
                [InlineKeyboardButton("🔄 Обновить анализ", callback_data="wellness_insights")],
                [InlineKeyboardButton("🔙 Назад к отчётам", callback_data="reports")]
            ]

            await status_message.edit_text(
                final_message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in wellness_insights_callback: {repr(e)}", exc_info=True)
        try:
            await query.message.reply_text(
                "❌ Произошла ошибка при анализе данных.\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="reports")
                ]])
            )
        except:
            pass
        return ConversationHandler.END


async def insights_statistics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает сводную статистику по фактам"""
    query = update.callback_query
    await query.answer()

    from app.db.session import async_session_maker
    from app.services.user_service import UserService
    from app.services.insight_statistics_service import InsightStatisticsService

    async with async_session_maker() as session:
        # Получаем пользователя
        user = await UserService.get_user_by_telegram_id(session, query.from_user.id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Получаем статистику
        stats = await InsightStatisticsService.get_summary_statistics(session, user.id)

        if stats["total_facts"] == 0:
            text = "📊 <b>Статистика интересных фактов</b>\n\n"
            text += "У вас пока нет обнаруженных фактов о корреляциях.\n\n"
            text += "Продолжайте вести дневник питания и заполнять опросы о самочувствии, "
            text += "и система автоматически найдет связи между продуктами и вашим состоянием!"
        else:
            text = "📊 <b>Статистика интересных фактов</b>\n\n"
            text += f"📚 Всего фактов: {stats['total_facts']}\n"
            text += f"✅ Активных: {stats['active_facts']}\n"
            text += f"🔄 Неактивных: {stats['inactive_facts']}\n\n"

            text += f"🟢 Положительных: {stats['positive_facts']}\n"
            text += f"🔴 Отрицательных: {stats['negative_facts']}\n"
            text += f"⚪ Нейтральных: {stats['neutral_facts']}\n\n"

            text += f"🎯 Средняя достоверность: {int(stats['average_confidence'] * 100)}%\n\n"

            if stats['top_positive_foods']:
                text += "✨ <b>Топ полезных продуктов:</b>\n"
                for i, food in enumerate(stats['top_positive_foods'][:3], 1):
                    metric_names = {
                        "energy_level": "энергия",
                        "mood": "настроение",
                        "digestive_comfort": "пищеварение",
                        "mental_clarity": "ясность ума",
                        "sleep_quality": "сон"
                    }
                    metric = metric_names.get(food['metric'], food['metric'])
                    conf = int(food['confidence'] * 100)
                    text += f"{i}. {food['food_name']} ({metric}, {conf}%)\n"
                text += "\n"

            if stats['top_negative_foods']:
                text += "⚠️ <b>Топ продуктов с негативным эффектом:</b>\n"
                for i, food in enumerate(stats['top_negative_foods'][:3], 1):
                    metric_names = {
                        "energy_level": "энергия",
                        "mood": "настроение",
                        "digestive_comfort": "пищеварение",
                        "mental_clarity": "ясность ума",
                        "sleep_quality": "сон"
                    }
                    metric = metric_names.get(food['metric'], food['metric'])
                    conf = int(food['confidence'] * 100)
                    text += f"{i}. {food['food_name']} ({metric}, {conf}%)\n"

        keyboard = [
            [InlineKeyboardButton("📈 График корреляций", callback_data="insights_graph")],
            [InlineKeyboardButton("📜 История изменений", callback_data="insights_history")],
            [InlineKeyboardButton("💾 Экспорт данных", callback_data="insights_export")],
            [InlineKeyboardButton("◀️ Назад", callback_data="wellness_insights")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    return SELECTING_PERIOD


async def insights_graph_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текстовый график корреляций"""
    query = update.callback_query
    await query.answer()

    from app.db.session import async_session_maker
    from app.services.user_service import UserService
    from app.services.insight_statistics_service import InsightStatisticsService

    async with async_session_maker() as session:
        # Получаем пользователя
        user = await UserService.get_user_by_telegram_id(session, query.from_user.id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Генерируем график
        graph_text = await InsightStatisticsService.get_correlation_graph_text(
            session, user.id, top_n=10
        )

        graph_text += "\n\n<i>Примечание: Графики показывают топ-10 самых достоверных корреляций</i>"

        keyboard = [
            [InlineKeyboardButton("◀️ Назад к статистике", callback_data="insights_statistics")]
        ]

        await query.edit_message_text(
            graph_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    return SELECTING_PERIOD


async def insights_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю изменений фактов"""
    query = update.callback_query
    await query.answer()

    from app.db.session import async_session_maker
    from app.services.user_service import UserService
    from app.services.insight_statistics_service import InsightStatisticsService

    async with async_session_maker() as session:
        # Получаем пользователя
        user = await UserService.get_user_by_telegram_id(session, query.from_user.id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Получаем историю
        history = await InsightStatisticsService.get_fact_history(session, user.id)

        if not history:
            text = "📜 <b>История изменений фактов</b>\n\n"
            text += "История пуста. Пока нет фактов о корреляциях."
        else:
            text = "📜 <b>История изменений фактов</b>\n\n"

            # Группируем по статусу
            active = [h for h in history if h['is_active']]
            inactive = [h for h in history if not h['is_active']]

            if active:
                text += f"✅ <b>Активных: {len(active)}</b>\n\n"
                for h in active[:5]:  # Показываем только первые 5
                    created = datetime.fromisoformat(h['created_at']).strftime("%d.%m.%Y")
                    validated = ""
                    if h['last_validated']:
                        validated_date = datetime.fromisoformat(h['last_validated']).strftime("%d.%m.%Y")
                        validated = f" | Проверен: {validated_date}"

                    text += f"• {h['food_name']} → {h['wellness_metric']}\n"
                    text += f"  Создан: {created}{validated}\n"
                    text += f"  Достоверность: {int(h['confidence_level'] * 100)}%\n\n"

            if inactive:
                text += f"\n❌ <b>Деактивировано: {len(inactive)}</b>\n\n"
                for h in inactive[:3]:  # Показываем только первые 3
                    created = datetime.fromisoformat(h['created_at']).strftime("%d.%m.%Y")
                    updated = datetime.fromisoformat(h['updated_at']).strftime("%d.%m.%Y")

                    text += f"• {h['food_name']} → {h['wellness_metric']}\n"
                    text += f"  Создан: {created} | Деактивирован: {updated}\n\n"

        keyboard = [
            [InlineKeyboardButton("◀️ Назад к статистике", callback_data="insights_statistics")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    return SELECTING_PERIOD


async def insights_export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспортирует факты в JSON или CSV"""
    query = update.callback_query
    await query.answer()

    text = "💾 <b>Экспорт данных</b>\n\n"
    text += "Выберите формат для экспорта ваших фактов о корреляциях:"

    keyboard = [
        [InlineKeyboardButton("📄 JSON", callback_data="export_json")],
        [InlineKeyboardButton("📊 CSV", callback_data="export_csv")],
        [InlineKeyboardButton("◀️ Назад", callback_data="insights_statistics")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return SELECTING_PERIOD


async def export_json_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспортирует факты в JSON"""
    query = update.callback_query
    await query.answer("Генерирую JSON файл...")

    from app.db.session import async_session_maker
    from app.services.user_service import UserService
    from app.services.insight_statistics_service import InsightStatisticsService
    import io

    async with async_session_maker() as session:
        # Получаем пользователя
        user = await UserService.get_user_by_telegram_id(session, query.from_user.id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Экспортируем в JSON
        json_data = await InsightStatisticsService.export_facts_to_json(
            session, user.id, active_only=False
        )

        # Отправляем файл
        file_name = f"wellness_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_bytes = io.BytesIO(json_data.encode('utf-8'))
        file_bytes.name = file_name

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_bytes,
            filename=file_name,
            caption="📄 Ваши факты о корреляциях в формате JSON"
        )

        # Возвращаемся к меню экспорта
        keyboard = [
            [InlineKeyboardButton("◀️ Назад к статистике", callback_data="insights_statistics")]
        ]

        await query.edit_message_text(
            "✅ JSON файл успешно создан и отправлен!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return SELECTING_PERIOD


async def export_csv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспортирует факты в CSV"""
    query = update.callback_query
    await query.answer("Генерирую CSV файл...")

    from app.db.session import async_session_maker
    from app.services.user_service import UserService
    from app.services.insight_statistics_service import InsightStatisticsService
    import io

    async with async_session_maker() as session:
        # Получаем пользователя
        user = await UserService.get_user_by_telegram_id(session, query.from_user.id)
        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Экспортируем в CSV
        csv_data = await InsightStatisticsService.export_facts_to_csv(
            session, user.id, active_only=False
        )

        # Отправляем файл
        file_name = f"wellness_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_bytes = io.BytesIO(csv_data.encode('utf-8-sig'))  # BOM для правильного отображения в Excel
        file_bytes.name = file_name

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_bytes,
            filename=file_name,
            caption="📊 Ваши факты о корреляциях в формате CSV"
        )

        # Возвращаемся к меню экспорта
        keyboard = [
            [InlineKeyboardButton("◀️ Назад к статистике", callback_data="insights_statistics")]
        ]

        await query.edit_message_text(
            "✅ CSV файл успешно создан и отправлен!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return SELECTING_PERIOD


# Создаем ConversationHandler
def get_reports_conversation_handler():
    """Получить conversation handler для отчетов"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reports_start, pattern="^reports$"),
        ],
        states={
            SELECTING_PERIOD: [
                CallbackQueryHandler(wellness_insights_callback, pattern="^wellness_insights$"),
                CallbackQueryHandler(insights_statistics_callback, pattern="^insights_statistics$"),
                CallbackQueryHandler(insights_graph_callback, pattern="^insights_graph$"),
                CallbackQueryHandler(insights_history_callback, pattern="^insights_history$"),
                CallbackQueryHandler(insights_export_callback, pattern="^insights_export$"),
                CallbackQueryHandler(export_json_callback, pattern="^export_json$"),
                CallbackQueryHandler(export_csv_callback, pattern="^export_csv$"),
                CallbackQueryHandler(generate_weight_chart, pattern="^report_weight_chart$"),
                CallbackQueryHandler(generate_report, pattern="^report_(day|week|month)$"),
                CallbackQueryHandler(reports_start, pattern="^another_report$"),
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
