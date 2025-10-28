"""
Обработчик фото для распознавания еды
"""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger
import io

from app.services.claude_ai import claude_service
from app.bot.keyboards import back_to_menu_keyboard


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик фото еды
    """
    user = update.effective_user
    photo = update.message.photo[-1]  # Самое большое разрешение

    logger.info(f"User {user.id} sent a photo for food recognition")

    # Уведомление пользователя
    processing_msg = await update.message.reply_text(
        "🔍 Анализирую фото...\nЭто может занять несколько секунд."
    )

    try:
        # Скачивание фото
        file = await context.bot.get_file(photo.file_id)
        image_bytes_io = io.BytesIO()
        await file.download_to_memory(image_bytes_io)
        image_bytes = image_bytes_io.getvalue()

        logger.info(f"Photo downloaded, size: {len(image_bytes)} bytes")

        # Распознавание через Claude API
        result = await claude_service.analyze_food_photo(
            image_bytes=image_bytes,
            additional_context=""
        )

        # Формирование ответа
        if result and "dishes" in result and len(result["dishes"]) > 0:
            dish = result["dishes"][0]
            nutrition = dish["nutrition"]

            response_text = (
                f"✅ *Распознано!*\n\n"
                f"🍽 *{dish['name']}*\n\n"
                f"📊 *Пищевая ценность:*\n"
                f"Порция: ~{dish['portion_size_grams']}г\n"
                f"🔥 Калории: {nutrition['calories']} ккал\n"
                f"🥩 Белки: {nutrition['proteins']}г\n"
                f"🧈 Жиры: {nutrition['fats']}г\n"
                f"🍞 Углеводы: {nutrition['carbs']}г\n\n"
                f"📝 *Ингредиенты:*\n"
                f"{', '.join(dish['ingredients'])}\n\n"
                f"Способ приготовления: {dish['cooking_method']}"
            )

            if dish.get("confidence", 1.0) < 0.7:
                response_text += "\n\n⚠️ Уверенность в распознавании ниже 70%. Проверьте данные."

            await processing_msg.edit_text(
                response_text,
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard()
            )

            logger.info(f"Food recognition successful for user {user.id}: {dish['name']}")

        else:
            await processing_msg.edit_text(
                "❌ Не удалось распознать еду на фото.\n\n"
                "Попробуйте:\n"
                "• Сделать фото при лучшем освещении\n"
                "• Сфотографировать блюдо ближе\n"
                "• Убрать лишние предметы из кадра\n\n"
                "Или опишите блюдо текстом!",
                reply_markup=back_to_menu_keyboard()
            )

            logger.warning(f"Failed to recognize food for user {user.id}")

    except Exception as e:
        logger.error(f"Error in photo recognition for user {user.id}: {e}")

        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке фото.\n\n"
            "Пожалуйста, попробуйте:\n"
            "• Отправить фото заново\n"
            "• Убедиться в хорошем качестве фото\n"
            "• Описать блюдо текстом\n\n"
            "Если проблема повторяется, обратитесь в поддержку.",
            reply_markup=back_to_menu_keyboard()
        )
