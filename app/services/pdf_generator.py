"""
Сервис для генерации PDF файлов с планами питания и списками покупок
"""
import os
from datetime import datetime
from typing import List
from io import BytesIO
import pytz

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from loguru import logger

from app.models.meal_plan import MealPlan
from app.models.shopping_list import ShoppingList


class PDFGeneratorService:
    """Сервис для генерации PDF документов"""

    # Путь для хранения PDF файлов
    PDF_STORAGE_PATH = "storage/pdfs"

    # Словарь городов и их часовых поясов
    CITY_TIMEZONES = {
        "Москва": "Europe/Moscow",
        "Санкт-Петербург": "Europe/Moscow",
        "Казань": "Europe/Moscow",
        "Новосибирск": "Asia/Novosibirsk",
        "Екатеринбург": "Asia/Yekaterinburg",
        "Владивосток": "Asia/Vladivostok",
        "Алматы": "Asia/Almaty",
        "Астана": "Asia/Almaty",
        "Киев": "Europe/Kiev",
        "Минск": "Europe/Minsk",
        "Ташкент": "Asia/Tashkent",
        "Баку": "Asia/Baku",
        "Ереван": "Asia/Yerevan",
        "Тбилиси": "Asia/Tbilisi",
    }

    @staticmethod
    def _get_local_time(city: str = None) -> datetime:
        """
        Получить местное время для города

        Args:
            city: Название города

        Returns:
            datetime: Местное время
        """
        # Определяем часовой пояс
        timezone_name = PDFGeneratorService.CITY_TIMEZONES.get(city, "Europe/Moscow")

        try:
            tz = pytz.timezone(timezone_name)
            return datetime.now(tz)
        except Exception as e:
            logger.warning(f"Could not get timezone for {city}: {e}, using UTC")
            return datetime.now(pytz.UTC)

    @staticmethod
    def _setup_fonts():
        """Настройка русских шрифтов"""
        try:
            # Пытаемся найти и зарегистрировать шрифты DejaVu (они поддерживают кириллицу)
            # Возможные пути к шрифтам в разных ОС
            font_paths = [
                # Linux
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                # MacOS
                "/Library/Fonts/DejaVuSans.ttf",
                "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
                # Относительный путь (если шрифт скопирован в проект)
                "fonts/DejaVuSans.ttf",
            ]

            font_bold_paths = [
                # Linux
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
                # MacOS
                "/Library/Fonts/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf",
                # Относительный путь
                "fonts/DejaVuSans-Bold.ttf",
            ]

            # Ищем основной шрифт
            regular_font_found = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                    regular_font_found = True
                    logger.info(f"Registered DejaVuSans font from {font_path}")
                    break

            # Ищем жирный шрифт
            bold_font_found = False
            for font_path in font_bold_paths:
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path))
                    bold_font_found = True
                    logger.info(f"Registered DejaVuSans-Bold font from {font_path}")
                    break

            if not regular_font_found:
                logger.warning("DejaVu fonts not found. Cyrillic text may not display correctly.")
                logger.warning("Please install DejaVu fonts: sudo apt-get install fonts-dejavu")

        except Exception as e:
            logger.error(f"Could not register custom fonts: {e}")

    @staticmethod
    def _get_styles():
        """Получить стили для документа"""
        styles = getSampleStyleSheet()

        # Проверяем, зарегистрирован ли DejaVu шрифт
        try:
            pdfmetrics.getFont('DejaVuSans')
            regular_font = 'DejaVuSans'
            bold_font = 'DejaVuSans-Bold'
        except:
            # Fallback на стандартные шрифты (кириллица не будет работать)
            regular_font = 'Helvetica'
            bold_font = 'Helvetica-Bold'
            logger.warning("Using Helvetica font - Cyrillic may not display correctly")

        # Заголовок
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=bold_font
        ))

        # Подзаголовок
        styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12,
            spaceBefore=12,
            fontName=bold_font
        ))

        # Обычный текст
        styles.add(ParagraphStyle(
            name='CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            fontName=regular_font
        ))

        # Мелкий текст
        styles.add(ParagraphStyle(
            name='CustomSmall',
            parent=styles['BodyText'],
            fontSize=9,
            textColor=colors.HexColor('#7F8C8D'),
            spaceAfter=6,
            fontName=regular_font
        ))

        return styles

    @staticmethod
    async def generate_meal_plan_pdf(
        meal_plan: MealPlan,
        days_data: List,
        user_name: str = "Пользователь",
        user_city: str = None
    ) -> str:
        """
        Генерация PDF с планом питания

        Args:
            meal_plan: План питания
            days_data: Данные о днях плана [(day, [meals])]
            user_name: Имя пользователя
            user_city: Город пользователя для определения местного времени

        Returns:
            str: Путь к созданному PDF файлу
        """
        # Создаем директорию для хранения если её нет
        os.makedirs(PDFGeneratorService.PDF_STORAGE_PATH, exist_ok=True)

        # Получаем местное время
        local_time = PDFGeneratorService._get_local_time(user_city)
        timestamp = local_time.strftime("%Y%m%d_%H%M%S")

        # Генерируем имя файла
        filename = f"meal_plan_{meal_plan.id}_{timestamp}.pdf"
        filepath = os.path.join(PDFGeneratorService.PDF_STORAGE_PATH, filename)

        # Настраиваем шрифты
        PDFGeneratorService._setup_fonts()

        # Создаем документ
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Получаем стили
        styles = PDFGeneratorService._get_styles()

        # Строим содержимое документа
        story = []

        # Заголовок
        story.append(Paragraph("NutriAI - План питания", styles['CustomTitle']))
        story.append(Spacer(1, 0.3*cm))

        # Информация о плане
        period_text = {
            "day": "на 1 день",
            "week": "на неделю",
            "month": "на месяц"
        }.get(meal_plan.period_type, "")

        info_text = f"""
        <b>Пользователь:</b> {user_name}<br/>
        <b>Период:</b> {period_text}<br/>
        <b>Даты:</b> {meal_plan.start_date.strftime('%d.%m.%Y')} - {meal_plan.end_date.strftime('%d.%m.%Y')}<br/>
        <b>Создан:</b> {meal_plan.created_at.strftime('%d.%m.%Y %H:%M')}<br/>
        """

        story.append(Paragraph(info_text, styles['CustomBody']))
        story.append(Spacer(1, 0.5*cm))

        # Целевые показатели
        story.append(Paragraph("Целевые показатели на день:", styles['CustomHeading']))

        targets_data = [
            ['Показатель', 'Значение'],
            ['Калории', f"{meal_plan.daily_calories} ккал"],
            ['Белки', f"{meal_plan.daily_proteins}г"],
            ['Жиры', f"{meal_plan.daily_fats}г"],
            ['Углеводы', f"{meal_plan.daily_carbs}г"],
        ]

        targets_table = Table(targets_data, colWidths=[8*cm, 6*cm])
        targets_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))

        story.append(targets_table)
        story.append(Spacer(1, 0.8*cm))

        # Дни и приемы пищи
        for day, meals in days_data:
            # Новый день - новая страница (кроме первого дня)
            if day.day_number > 1:
                story.append(PageBreak())

            # Заголовок дня
            day_title = f"День {day.day_number} ({day.day_date.strftime('%d.%m.%Y')})"
            story.append(Paragraph(day_title, styles['CustomTitle']))
            story.append(Spacer(1, 0.3*cm))

            # Итоги дня
            day_totals = f"""
            <b>Итого за день:</b> {day.total_calories} ккал |
            Б: {day.total_proteins}г | Ж: {day.total_fats}г | У: {day.total_carbs}г
            """
            story.append(Paragraph(day_totals, styles['CustomBody']))
            story.append(Spacer(1, 0.5*cm))

            # Приемы пищи
            meal_type_names = {
                "breakfast": "Завтрак",
                "lunch": "Обед",
                "dinner": "Ужин",
                "snack": "Перекус"
            }

            for meal in meals:
                meal_type_text = meal_type_names.get(meal.meal_type, meal.meal_type.capitalize())

                # Название приема пищи
                story.append(Paragraph(f"{meal_type_text}: {meal.recipe_name}", styles['CustomHeading']))

                # КБЖУ
                nutrition_text = f"Калории: {meal.calories} ккал | Б: {meal.proteins}г | Ж: {meal.fats}г | У: {meal.carbs}г"
                story.append(Paragraph(nutrition_text, styles['CustomSmall']))
                story.append(Spacer(1, 0.2*cm))

                # Ингредиенты
                story.append(Paragraph("<b>Ингредиенты:</b>", styles['CustomBody']))

                ingredients_list = []
                for ingredient in meal.ingredients:
                    name = ingredient.get("name", "")
                    qty = ingredient.get("quantity", 0)
                    unit = ingredient.get("unit", "")
                    ingredients_list.append(f"• {name} - {qty}{unit}")

                ingredients_text = "<br/>".join(ingredients_list)
                story.append(Paragraph(ingredients_text, styles['CustomSmall']))
                story.append(Spacer(1, 0.3*cm))

                # Инструкции
                if meal.cooking_instructions:
                    story.append(Paragraph("<b>Приготовление:</b>", styles['CustomBody']))
                    story.append(Paragraph(meal.cooking_instructions, styles['CustomSmall']))

                # Время приготовления
                if meal.cooking_time_minutes:
                    time_text = f"<i>Время приготовления: {meal.cooking_time_minutes} мин</i>"
                    story.append(Paragraph(time_text, styles['CustomSmall']))

                story.append(Spacer(1, 0.5*cm))

        # Строим PDF
        doc.build(story)
        logger.info(f"Meal plan PDF generated: {filepath}")

        return filepath

    @staticmethod
    async def generate_shopping_list_pdf(
        shopping_list: ShoppingList,
        items: List,
        meal_plan: MealPlan,
        user_name: str = "Пользователь",
        user_city: str = None
    ) -> str:
        """
        Генерация PDF со списком покупок

        Args:
            shopping_list: Список покупок
            items: Элементы списка
            meal_plan: План питания
            user_name: Имя пользователя
            user_city: Город пользователя для определения местного времени

        Returns:
            str: Путь к созданному PDF файлу
        """
        # Создаем директорию для хранения если её нет
        os.makedirs(PDFGeneratorService.PDF_STORAGE_PATH, exist_ok=True)

        # Получаем местное время
        local_time = PDFGeneratorService._get_local_time(user_city)
        timestamp = local_time.strftime("%Y%m%d_%H%M%S")

        # Генерируем имя файла
        filename = f"shopping_list_{shopping_list.id}_{timestamp}.pdf"
        filepath = os.path.join(PDFGeneratorService.PDF_STORAGE_PATH, filename)

        # Настраиваем шрифты
        PDFGeneratorService._setup_fonts()

        # Создаем документ
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # Получаем стили
        styles = PDFGeneratorService._get_styles()

        # Строим содержимое документа
        story = []

        # Заголовок
        story.append(Paragraph("NutriAI - Список покупок", styles['CustomTitle']))
        story.append(Spacer(1, 0.3*cm))

        # Информация о списке
        period_text = {
            "day": "на 1 день",
            "week": "на неделю",
            "month": "на месяц"
        }.get(meal_plan.period_type, "")

        info_text = f"""
        <b>Пользователь:</b> {user_name}<br/>
        <b>Период:</b> {period_text}<br/>
        <b>Создан:</b> {shopping_list.generated_at.strftime('%d.%m.%Y %H:%M')}<br/>
        <b>Общая стоимость:</b> ~{shopping_list.total_cost:.2f} {shopping_list.currency}<br/>
        """

        story.append(Paragraph(info_text, styles['CustomBody']))
        story.append(Spacer(1, 0.8*cm))

        # Группируем товары по категориям
        items_by_category = {}
        for item in items:
            category = item.category or "Другое"
            if category not in items_by_category:
                items_by_category[category] = []
            items_by_category[category].append(item)

        # Генерируем таблицы для каждой категории
        for category, category_items in sorted(items_by_category.items()):
            # Заголовок категории
            story.append(Paragraph(category, styles['CustomHeading']))

            # Таблица с товарами
            table_data = [['Продукт', 'Количество', 'Цена']]

            for item in category_items:
                price_text = f"~{item.estimated_price:.2f} ₽" if item.estimated_price else "-"

                table_data.append([
                    item.product_name,
                    f"{item.quantity} {item.unit}",
                    price_text
                ])

            # Создаем таблицу
            table = Table(table_data, colWidths=[9*cm, 4*cm, 3*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))

            story.append(table)
            story.append(Spacer(1, 0.5*cm))

        # Итоговая информация
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph("Итого", styles['CustomHeading']))

        total_data = [
            ['Общая стоимость', f"~{shopping_list.total_cost:.2f} {shopping_list.currency}"],
            ['Количество позиций', str(len(items))]
        ]

        total_table = Table(total_data, colWidths=[10*cm, 6*cm])
        total_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2ECC71')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.whitesmoke),
        ]))

        story.append(total_table)

        # Примечание
        story.append(Spacer(1, 1*cm))
        note_text = """
        <i>Примечание: Указанные цены являются примерными и могут отличаться
        в зависимости от региона и выбранного магазина.</i>
        """
        story.append(Paragraph(note_text, styles['CustomSmall']))

        # Строим PDF
        doc.build(story)
        logger.info(f"Shopping list PDF generated: {filepath}")

        return filepath
