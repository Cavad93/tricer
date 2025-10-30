"""
Обработчики для работы с медицинскими анализами
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode
from loguru import logger
from datetime import datetime
import json

from app.db.session import async_session_maker
from app.models.user import User
from app.models.medical_analysis import MedicalAnalysis
from app.services.medical_analysis_service import MedicalAnalysisService
from app.bot.keyboards import back_to_menu_keyboard
from app.bot.states import MedicalAnalysisStates
from sqlalchemy import select


async def medical_analysis_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Стартовое меню медицинских анализов
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Получаем количество сохраненных анализов
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            await query.edit_message_text(
                "❌ Пользователь не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return ConversationHandler.END

        # Получаем количество анализов
        analyses = await MedicalAnalysisService.get_user_analyses(session, db_user.id, limit=100)
        analyses_count = len(analyses)

    keyboard = [
        [InlineKeyboardButton("📤 Добавить новый анализ", callback_data="add_new_analysis")],
    ]

    if analyses_count > 0:
        keyboard.append([InlineKeyboardButton(f"📜 История анализов ({analyses_count})", callback_data="view_history")])

    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])

    text = (
        "📋 <b>Медицинские анализы</b>\n\n"
        "Загрузи результаты своих лабораторных анализов, и AI поможет:\n"
        "• Выявить дефициты витаминов и минералов\n"
        "• Определить какие нутриенты нужно увеличить в рационе\n"
        "• Дать рекомендации по питанию на основе показателей\n\n"
        "⚠️ <b>Важно:</b> Это не медицинское заключение! "
        "AI дает рекомендации только по питанию. При отклонениях от нормы обратись к врачу."
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return MedicalAnalysisStates.ASKING_TO_UPLOAD


async def add_new_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Выбор способа добавления анализа
    """
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📄 Загрузить файл/фото", callback_data="upload_file")],
        [InlineKeyboardButton("✍️ Ввести показатели текстом", callback_data="input_text")],
        [InlineKeyboardButton("🔙 Назад", callback_data="medical_analysis")],
    ]

    await query.edit_message_text(
        "📤 <b>Как ты хочешь добавить анализ?</b>\n\n"
        "• <b>Файл/фото</b> - отправь скан или фото результатов анализа\n"
        "• <b>Текст</b> - введи показатели вручную (например: \"Гемоглобин 130, Железо 15\")",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return MedicalAnalysisStates.ASKING_TO_UPLOAD


async def upload_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрос загрузки файла
    """
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📄 <b>Отправь файл или фото результатов анализа</b>\n\n"
        "Поддерживаются форматы: PDF, JPG, PNG\n\n"
        "❌ Для отмены нажми /cancel",
        parse_mode=ParseMode.HTML
    )

    return MedicalAnalysisStates.WAITING_FILE


async def input_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрос текстового ввода
    """
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✍️ <b>Введи показатели анализов</b>\n\n"
        "Можешь написать в свободной форме, например:\n"
        "\"<i>Гемоглобин 130 г/л, Эритроциты 4.5, Железо 15 мкмоль/л, "
        "Витамин D 25 нг/мл, Холестерин 5.2</i>\"\n\n"
        "Или скопируй из электронного результата анализа.\n\n"
        "❌ Для отмены нажми /cancel",
        parse_mode=ParseMode.HTML
    )

    return MedicalAnalysisStates.WAITING_TEXT_INPUT


async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка загруженного файла или фото
    """
    user = update.effective_user

    # Определяем тип файла
    file = None
    file_type = None

    if update.message.document:
        file = update.message.document
        file_type = "document"
    elif update.message.photo:
        file = update.message.photo[-1]  # Берем самое большое фото
        file_type = "photo"

    if not file:
        await update.message.reply_text(
            "❌ Пожалуйста, отправь файл или фото с результатами анализа"
        )
        return MedicalAnalysisStates.WAITING_FILE

    # Сообщение о начале обработки
    status_message = await update.message.reply_text(
        "⏳ Обрабатываю файл...\n"
        "Это может занять несколько секунд."
    )

    try:
        # Сохраняем file_id для будущего использования
        context.user_data["analysis_file_id"] = file.file_id
        context.user_data["analysis_file_type"] = file_type

        # Извлекаем текст с помощью OCR через Claude Vision API
        await status_message.edit_text(
            "📄 <b>Файл получен!</b>\n\n"
            "🔬 Извлекаю данные из изображения с помощью AI...\n"
            "Это может занять 10-15 секунд.",
            parse_mode=ParseMode.HTML
        )

        # Скачиваем файл
        telegram_file = await context.bot.get_file(file.file_id)
        photo_bytes = await telegram_file.download_as_bytearray()

        # Импортируем ClaudeAIService
        from app.services.claude_ai import ClaudeAIService
        claude_service = ClaudeAIService()

        # Извлекаем текст через OCR
        extracted_text = await claude_service.extract_medical_analysis_from_image(bytes(photo_bytes))

        # Проверяем результат извлечения
        if "ОШИБКА:" in extracted_text:
            logger.warning(f"OCR failed for user {user.id}: {extracted_text}")
            await status_message.edit_text(
                "❌ <b>Не удалось распознать медицинский анализ</b>\n\n"
                "На изображении не обнаружены данные медицинских анализов.\n\n"
                "Пожалуйста, убедись что:\n"
                "• Фото четкое и читаемое\n"
                "• На фото виден бланк анализа с показателями\n"
                "• Текст не размыт и не перевернут\n\n"
                "Можешь попробовать снова или ввести показатели вручную текстом:\n"
                "Например: \"<i>Гемоглобин 130, Железо 15, Витамин D 25</i>\"",
                parse_mode=ParseMode.HTML
            )
            return MedicalAnalysisStates.WAITING_TEXT_INPUT

        # Успешное извлечение - продолжаем анализ
        logger.info(f"OCR successful for user {user.id}, extracted {len(extracted_text)} characters")

        # Сообщение о начале AI-анализа
        await status_message.edit_text(
            "✅ <b>Данные успешно извлечены!</b>\n\n"
            "🔬 Анализирую показатели с помощью AI...\n"
            "Это займет 10-20 секунд.",
            parse_mode=ParseMode.HTML
        )

        # Получаем пользователя из БД
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await status_message.edit_text(
                    "❌ Пользователь не найден",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Формируем сырые данные для сохранения
            raw_data = {
                "input_method": "ocr",
                "extracted_text": extracted_text,
                "file_id": file.file_id,
                "file_type": file_type,
                "timestamp": datetime.now().isoformat()
            }

            # Анализируем через AI
            analysis_result = await MedicalAnalysisService.analyze_lab_results(
                user=db_user,
                raw_data=raw_data,
                analysis_type="Общий анализ",
                analysis_date=datetime.now()
            )

            if not analysis_result.get("success"):
                await status_message.edit_text(
                    "❌ Не удалось проанализировать данные.\n"
                    f"Ошибка: {analysis_result.get('error', 'Неизвестная ошибка')}\n\n"
                    "Попробуй ввести показатели вручную текстом.",
                    reply_markup=back_to_menu_keyboard()
                )
                return MedicalAnalysisStates.WAITING_TEXT_INPUT

            # Сохраняем результаты в БД
            saved_analysis = await MedicalAnalysisService.save_analysis(
                db=session,
                user_id=db_user.id,
                raw_data=raw_data,
                ai_analysis=analysis_result.get("ai_analysis"),
                analysis_type="Общий анализ",
                analysis_date=datetime.now(),
                file_url=None
            )

            # Обновляем медицинские ограничения с учетом новых дефицитов
            try:
                await status_message.edit_text(
                    "🔬 <b>Анализ завершен!</b>\n\n"
                    "Обновляю рекомендации по питанию на основе выявленных дефицитов...",
                    parse_mode=ParseMode.HTML
                )

                # Генерируем/обновляем медицинские ограничения
                await MedicalAnalysisService.generate_medical_restrictions(db_user, session)

                # Обновляем объект пользователя
                await session.refresh(db_user)

                logger.info(f"Medical restrictions updated for user {db_user.id} after OCR analysis")
            except Exception as e:
                logger.error("Error updating medical restrictions after analysis: %s", str(e))
                # Не прерываем процесс, если не удалось обновить ограничения

            # Формируем красивый ответ
            await status_message.delete()
            await show_analysis_results(update, context, analysis_result, saved_analysis.id)

            # Очищаем временные данные
            context.user_data.pop("analysis_file_id", None)
            context.user_data.pop("analysis_file_type", None)

            return ConversationHandler.END

    except Exception as e:
        logger.error("Error handling file upload with OCR: %s", str(e), exc_info=True)
        await status_message.edit_text(
            "❌ Произошла ошибка при обработке файла.\n"
            "Попробуй ввести показатели текстом или загрузи другое фото.",
            reply_markup=back_to_menu_keyboard()
        )
        return MedicalAnalysisStates.WAITING_TEXT_INPUT


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка текстового ввода показателей
    """
    user = update.effective_user
    text_input = update.message.text.strip()

    if not text_input:
        await update.message.reply_text(
            "❌ Пожалуйста, введи показатели анализов"
        )
        return MedicalAnalysisStates.WAITING_TEXT_INPUT

    # Сообщение о начале анализа
    status_message = await update.message.reply_text(
        "🔬 <b>Анализирую данные...</b>\n\n"
        "AI изучает твои показатели и ищет возможные дефициты нутриентов.\n"
        "Это займет 10-20 секунд.",
        parse_mode=ParseMode.HTML
    )

    try:
        # Получаем пользователя из БД
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await status_message.edit_text(
                    "❌ Пользователь не найден",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Формируем сырые данные для сохранения
            raw_data = {
                "input_method": "text",
                "text_input": text_input,
                "timestamp": datetime.now().isoformat()
            }

            # Если был загружен файл - добавляем информацию о нем
            if context.user_data.get("analysis_file_id"):
                raw_data["file_id"] = context.user_data["analysis_file_id"]
                raw_data["file_type"] = context.user_data["analysis_file_type"]

            # Анализируем через AI
            analysis_result = await MedicalAnalysisService.analyze_lab_results(
                user=db_user,
                raw_data=raw_data,
                analysis_type="Общий анализ",
                analysis_date=datetime.now()
            )

            if not analysis_result.get("success"):
                await status_message.edit_text(
                    "❌ Не удалось проанализировать данные.\n"
                    f"Ошибка: {analysis_result.get('error', 'Неизвестная ошибка')}",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Сохраняем результаты в БД
            saved_analysis = await MedicalAnalysisService.save_analysis(
                db=session,
                user_id=db_user.id,
                raw_data=raw_data,
                ai_analysis=analysis_result.get("ai_analysis"),
                analysis_type="Общий анализ",
                analysis_date=datetime.now(),
                file_url=None
            )

            # Обновляем медицинские ограничения с учетом новых дефицитов
            try:
                await status_message.edit_text(
                    "🔬 <b>Анализ завершен!</b>\n\n"
                    "Обновляю рекомендации по питанию на основе выявленных дефицитов...",
                    parse_mode=ParseMode.HTML
                )

                # Генерируем/обновляем медицинские ограничения
                await MedicalAnalysisService.generate_medical_restrictions(db_user, session)

                # Обновляем объект пользователя
                await session.refresh(db_user)

                logger.info(f"Medical restrictions updated for user {db_user.id} after analysis")
            except Exception as e:
                logger.error("Error updating medical restrictions after analysis: %s", str(e))
                # Не прерываем процесс, если не удалось обновить ограничения

            # Формируем красивый ответ
            await status_message.delete()
            await show_analysis_results(update, context, analysis_result, saved_analysis.id)

            # Очищаем временные данные
            context.user_data.pop("analysis_file_id", None)
            context.user_data.pop("analysis_file_type", None)

            return ConversationHandler.END

    except Exception as e:
        logger.error("Error analyzing lab results: %s", str(e), exc_info=True)
        await status_message.edit_text(
            "❌ Произошла ошибка при анализе данных.\n"
            "Попробуй еще раз позже.",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END


async def show_analysis_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    analysis_result: dict,
    analysis_id: int
) -> None:
    """
    Красивый вывод результатов анализа
    """
    deficiencies = analysis_result.get("detected_deficiencies", [])
    needs_doctor = analysis_result.get("needs_doctor_consultation", False)
    recommendations = analysis_result.get("recommendations", [])
    summary = analysis_result.get("summary", "")

    # Формируем сообщение
    response = "📊 <b>Результаты анализа</b>\n\n"

    # Краткая сводка
    if summary:
        response += f"📝 {summary}\n\n"

    # Дефициты
    if deficiencies:
        response += "⚠️ <b>Выявленные дефициты:</b>\n\n"
        for deficiency in deficiencies:
            nutrient = deficiency.get("nutrient", "Неизвестно")
            severity = deficiency.get("severity", "moderate")
            indicator = deficiency.get("indicator", "")
            current_value = deficiency.get("current_value", "")
            normal_range = deficiency.get("normal_range", "")
            explanation = deficiency.get("explanation", "")

            # Эмодзи в зависимости от серьезности
            severity_emoji = {
                "low": "🟡",
                "moderate": "🟠",
                "high": "🔴"
            }.get(severity, "🟠")

            response += f"{severity_emoji} <b>{nutrient}</b>\n"
            if indicator:
                response += f"   Показатель: {indicator}\n"
            if current_value:
                response += f"   Текущее значение: {current_value}\n"
            if normal_range:
                response += f"   Норма: {normal_range}\n"
            if explanation:
                response += f"   <i>{explanation}</i>\n"
            response += "\n"
    else:
        response += "✅ <b>Критических дефицитов не обнаружено!</b>\n\n"

    # Рекомендации по питанию
    if recommendations:
        response += "💡 <b>Рекомендации по питанию:</b>\n\n"
        for i, rec in enumerate(recommendations, 1):
            response += f"{i}. {rec}\n"
        response += "\n"

    # Информация об обновлении плана питания
    if deficiencies:
        response += (
            "🍽 <b>Планы питания обновлены!</b>\n"
            "При создании нового рациона AI будет автоматически учитывать "
            "выявленные дефициты и подбирать блюда для их восполнения.\n\n"
        )

    # Предупреждение о консультации врача
    if needs_doctor:
        doctor_reason = analysis_result.get("ai_analysis", {}).get("doctor_consultation_reason", "")
        response += "⚕️ <b>ВАЖНО: Рекомендуется консультация врача!</b>\n"
        if doctor_reason:
            response += f"<i>{doctor_reason}</i>\n"
        response += "\n"

    response += (
        "ℹ️ <i>Это не медицинское заключение. "
        "Рекомендации даны с точки зрения оптимизации питания.</i>"
    )

    # Кнопки
    keyboard = [
        [InlineKeyboardButton("📜 История анализов", callback_data="view_history")],
        [InlineKeyboardButton("📤 Добавить еще", callback_data="add_new_analysis")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await update.message.reply_text(
        response,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def view_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Просмотр истории анализов
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            await query.edit_message_text(
                "❌ Пользователь не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return ConversationHandler.END

        # Получаем историю анализов
        analyses = await MedicalAnalysisService.get_user_analyses(session, db_user.id, limit=10)

        if not analyses:
            await query.edit_message_text(
                "📜 <b>История анализов пуста</b>\n\n"
                "Ты еще не загружал медицинские анализы.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 Добавить анализ", callback_data="add_new_analysis")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return ConversationHandler.END

        # Формируем список анализов
        response = "📜 <b>История медицинских анализов</b>\n\n"

        for i, analysis in enumerate(analyses, 1):
            date_str = analysis.created_at.strftime("%d.%m.%Y")
            analysis_type = analysis.analysis_type or "Общий анализ"

            response += f"{i}. <b>{analysis_type}</b> - {date_str}\n"

            # Показываем краткую информацию о дефицитах
            if analysis.detected_deficiencies:
                deficiencies_count = len(analysis.detected_deficiencies)
                response += f"   ⚠️ Дефицитов: {deficiencies_count}\n"

                # Показываем первые 2 дефицита
                for def_item in analysis.detected_deficiencies[:2]:
                    nutrient = def_item.get("nutrient", "")
                    if nutrient:
                        response += f"   • {nutrient}\n"

                if deficiencies_count > 2:
                    response += f"   • ... и еще {deficiencies_count - 2}\n"
            else:
                response += "   ✅ Дефицитов не обнаружено\n"

            if analysis.needs_doctor_consultation:
                response += "   ⚕️ Требуется консультация врача\n"

            response += "\n"

        keyboard = [
            [InlineKeyboardButton("📤 Добавить новый", callback_data="add_new_analysis")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]

        await query.edit_message_text(
            response,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return ConversationHandler.END


async def cancel_medical_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена процесса добавления анализа
    """
    # Очищаем временные данные
    context.user_data.pop("analysis_file_id", None)
    context.user_data.pop("analysis_file_type", None)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "❌ Операция отменена",
            reply_markup=back_to_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=back_to_menu_keyboard()
        )

    return ConversationHandler.END


# ConversationHandler для медицинских анализов
medical_analysis_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(medical_analysis_start, pattern="^medical_analysis$")
    ],
    states={
        MedicalAnalysisStates.ASKING_TO_UPLOAD: [
            CallbackQueryHandler(add_new_analysis_callback, pattern="^add_new_analysis$"),
            CallbackQueryHandler(upload_file_callback, pattern="^upload_file$"),
            CallbackQueryHandler(input_text_callback, pattern="^input_text$"),
            CallbackQueryHandler(view_history_callback, pattern="^view_history$"),
            CallbackQueryHandler(cancel_medical_analysis, pattern="^main_menu$"),
        ],
        MedicalAnalysisStates.WAITING_FILE: [
            MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file_upload),
            CallbackQueryHandler(upload_file_callback, pattern="^upload_file$"),
            CallbackQueryHandler(input_text_callback, pattern="^input_text$"),
            CallbackQueryHandler(add_new_analysis_callback, pattern="^add_new_analysis$"),
        ],
        MedicalAnalysisStates.WAITING_TEXT_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input),
            CallbackQueryHandler(upload_file_callback, pattern="^upload_file$"),
            CallbackQueryHandler(input_text_callback, pattern="^input_text$"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_medical_analysis, pattern="^main_menu$"),
        CallbackQueryHandler(medical_analysis_start, pattern="^medical_analysis$"),
    ],
    per_message=False,
    allow_reentry=True
)
