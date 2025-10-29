"""
Расширение PDF генератора для создания отчетов о питании с графиками
"""
import os
from datetime import datetime
from typing import Dict
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Backend без GUI
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Wedge
import pytz

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from loguru import logger

from app.services.pdf_generator import PDFGeneratorService


class PDFReportGenerator:
    """Генератор PDF-отчетов о питании с графиками"""

    @staticmethod
    def _create_pie_chart(macros_data: Dict, title: str = "КБЖУ") -> str:
        """
        Создать круговую диаграмму КБЖУ

        Args:
            macros_data: Словарь с данными (proteins, fats, carbs)
            title: Заголовок диаграммы

        Returns:
            Путь к файлу изображения
        """
        try:
            # Создаем временную директорию
            os.makedirs("storage/temp", exist_ok=True)

            # Данные для диаграммы
            labels = ['Белки', 'Жиры', 'Углеводы']
            sizes = [
                macros_data.get('proteins', 0) * 4,  # калории из белков
                macros_data.get('fats', 0) * 9,  # калории из жиров
                macros_data.get('carbs', 0) * 4  # калории из углеводов
            ]

            # Цвета
            colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1']

            # Создаем фигуру
            fig, ax = plt.subplots(figsize=(6, 4), dpi=100)

            # Круговая диаграмма
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                colors=colors_list,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 10}
            )

            # Улучшаем внешний вид
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.set_title(title, fontsize=12, fontweight='bold')
            ax.axis('equal')

            # Сохраняем
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = f"storage/temp/pie_chart_{timestamp}.png"
            plt.savefig(filepath, bbox_inches='tight', dpi=100)
            plt.close()

            return filepath

        except Exception as e:
            logger.error(f"Error creating pie chart: {e}")
            return None

    @staticmethod
    def _create_progress_bars(data: Dict, max_value: float = 100) -> str:
        """
        Создать прогресс-бары (ползунки)

        Args:
            data: Словарь с данными {label: percentage}
            max_value: Максимальное значение (обычно 100%)

        Returns:
            Путь к файлу изображения
        """
        try:
            os.makedirs("storage/temp", exist_ok=True)

            # Создаем фигуру
            fig, ax = plt.subplots(figsize=(10, len(data) * 0.6), dpi=100)

            # Цвета для ползунков
            bar_colors = {
                'Калории': '#FF6B6B',
                'Белки': '#4ECDC4',
                'Жиры': '#45B7D1',
                'Углеводы': '#F7B731'
            }

            # Отрисовка ползунков
            y_pos = 0
            for label, percentage in data.items():
                # Фон ползунка (серый)
                ax.barh(y_pos, max_value, height=0.5, color='#E0E0E0', alpha=0.3)

                # Заполненная часть
                color = bar_colors.get(label, '#3498DB')
                actual_width = min(percentage, max_value)  # Ограничиваем максимумом
                ax.barh(y_pos, actual_width, height=0.5, color=color, alpha=0.8)

                # Текст с процентами
                text_x = actual_width + 2
                if text_x > max_value:
                    text_x = max_value - 5

                ax.text(text_x, y_pos, f'{percentage:.0f}%',
                       va='center', fontweight='bold', fontsize=10)

                # Название показателя
                ax.text(-5, y_pos, label, va='center', ha='right', fontsize=10)

                y_pos += 1

            # Настройка осей
            ax.set_xlim(-20, max_value + 10)
            ax.set_ylim(-0.5, len(data) - 0.5)
            ax.axis('off')

            # Сохраняем
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filepath = f"storage/temp/progress_bars_{timestamp}.png"
            plt.savefig(filepath, bbox_inches='tight', dpi=100)
            plt.close()

            return filepath

        except Exception as e:
            logger.error(f"Error creating progress bars: {e}")
            return None

    @staticmethod
    async def generate_nutrition_report_pdf(
        report_data: Dict,
        user_city: str = None
    ) -> str:
        """
        Генерация PDF-отчета о питании с графиками

        Args:
            report_data: Данные отчета из NutritionReportService
            user_city: Город пользователя

        Returns:
            Путь к созданному PDF файлу
        """
        try:
            # Создаем директорию
            os.makedirs(PDFGeneratorService.PDF_STORAGE_PATH, exist_ok=True)

            # Получаем местное время
            local_time = PDFGeneratorService._get_local_time(user_city)
            timestamp = local_time.strftime("%Y%m%d_%H%M%S")

            # Определяем тип отчета
            if "period" in report_data:
                period_type = report_data["period"]["type"]
                start_date = report_data["period"]["start_date"]
                filename = f"nutrition_report_{period_type}_{start_date}_{timestamp}.pdf"
            else:
                report_date = report_data.get("date", "unknown")
                filename = f"nutrition_report_day_{report_date}_{timestamp}.pdf"

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
            story = []

            # Дисклеймер
            disclaimer_text = """
            <b>Важное примечание:</b> Данные о микронутриентах являются <u>примерной оценкой</u>
            и могут отличаться от фактических значений. Расчеты основаны на усредненных данных
            о составе продуктов. Для точной оценки рекомендуется консультация со специалистом.
            """
            disclaimer_style = ParagraphStyle(
                name='Disclaimer',
                parent=styles['CustomSmall'],
                textColor=colors.HexColor('#E74C3C'),
                backColor=colors.HexColor('#FFEBEE'),
                borderPadding=8,
                borderWidth=1,
                borderColor=colors.HexColor('#E74C3C')
            )
            story.append(Paragraph(disclaimer_text, disclaimer_style))
            story.append(Spacer(1, 0.5*cm))

            # Заголовок
            user_name = report_data.get("user", {}).get("name", "Пользователь")

            if "period" in report_data:
                period_names = {"week": "Неделя", "month": "Месяц"}
                period_name = period_names.get(report_data["period"]["type"], "Период")
                title = f"Отчет о питании: {period_name}"
            else:
                title = "Отчет о питании: День"

            story.append(Paragraph(f"{title}", styles['CustomTitle']))
            story.append(Spacer(1, 0.3*cm))

            # Информация о пользователе и периоде
            if "period" in report_data:
                period = report_data["period"]
                info_text = f"""
                <b>Пользователь:</b> {user_name}<br/>
                <b>Период:</b> {period['start_date']} — {period['end_date']}<br/>
                <b>Дней с данными:</b> {period['days_with_data']} из {period['days_count']}<br/>
                """
            else:
                info_text = f"""
                <b>Пользователь:</b> {user_name}<br/>
                <b>Дата:</b> {report_data['date']}<br/>
                """

            story.append(Paragraph(info_text, styles['CustomBody']))
            story.append(Spacer(1, 0.5*cm))

            # КБЖУ - Круговая диаграмма
            story.append(Paragraph("Макронутриенты (КБЖУ)", styles['CustomHeading']))

            macros = report_data["macros"]
            consumed = macros.get("consumed") or macros.get("average")
            targets = macros["targets"]
            percentages = macros["percentages"]

            # Создаем круговую диаграмму
            pie_chart_path = PDFReportGenerator._create_pie_chart(consumed)
            if pie_chart_path and os.path.exists(pie_chart_path):
                img = Image(pie_chart_path, width=10*cm, height=7*cm)
                story.append(img)
                story.append(Spacer(1, 0.3*cm))

            # Прогресс-бары для КБЖУ
            progress_data = {
                'Калории': percentages['calories'],
                'Белки': percentages['proteins'],
                'Жиры': percentages['fats'],
                'Углеводы': percentages['carbs']
            }

            progress_bars_path = PDFReportGenerator._create_progress_bars(progress_data)
            if progress_bars_path and os.path.exists(progress_bars_path):
                img = Image(progress_bars_path, width=14*cm, height=5*cm)
                story.append(img)
                story.append(Spacer(1, 0.5*cm))

            # Таблица с данными КБЖУ
            regular_font, bold_font = PDFGeneratorService._get_fonts()

            macro_table_data = [
                ['Показатель', 'Факт', 'Цель', '%'],
                ['Калории', f"{consumed['calories']:.0f} ккал", f"{targets['calories']} ккал", f"{percentages['calories']:.0f}%"],
                ['Белки', f"{consumed['proteins']:.1f}г", f"{targets['proteins']}г", f"{percentages['proteins']:.0f}%"],
                ['Жиры', f"{consumed['fats']:.1f}г", f"{targets['fats']}г", f"{percentages['fats']:.0f}%"],
                ['Углеводы', f"{consumed['carbs']:.1f}г", f"{targets['carbs']}г", f"{percentages['carbs']:.0f}%"],
            ]

            macro_table = Table(macro_table_data, colWidths=[5*cm, 3.5*cm, 3.5*cm, 2.5*cm])
            macro_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), bold_font),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ECF0F1')),
                ('FONTNAME', (0, 1), (-1, -1), regular_font),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))

            story.append(macro_table)
            story.append(Spacer(1, 0.8*cm))

            # Микронутриенты (если есть данные)
            if report_data.get("micronutrients"):
                story.append(PageBreak())
                story.append(Paragraph("Микронутриенты (Витамины и Минералы)", styles['CustomTitle']))
                story.append(Spacer(1, 0.3*cm))

                # Дисклеймер для микронутриентов
                micro_disclaimer = """
                <b>Примечание:</b> Значения микронутриентов рассчитаны на основе усредненных данных
                и являются приблизительными. Рекомендуем консультироваться со специалистом для
                точной оценки вашего рациона.
                """
                story.append(Paragraph(micro_disclaimer, disclaimer_style))
                story.append(Spacer(1, 0.5*cm))

                micronutrients = report_data["micronutrients"]

                # Группируем витамины и минералы
                vitamins = {k: v for k, v in micronutrients.items() if k.startswith('vitamin') or k == 'beta_carotene' or k == 'choline'}
                minerals = {k: v for k, v in micronutrients.items() if k not in vitamins}

                # Витамины
                story.append(Paragraph("Витамины", styles['CustomHeading']))

                vitamin_table_data = [['Витамин', 'Факт', 'Норма', '%']]
                for key, data in list(vitamins.items())[:10]:  # Первые 10 витаминов
                    consumed_key = 'consumed' if 'consumed' in data else 'average'
                    vitamin_table_data.append([
                        data['name'],
                        f"{data[consumed_key]:.1f} {data['unit']}",
                        f"{data['target']} {data['unit']}",
                        f"{data['percentage']:.0f}%"
                    ])

                vitamin_table = Table(vitamin_table_data, colWidths=[6*cm, 3*cm, 3*cm, 2.5*cm])
                vitamin_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9B59B6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), bold_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F4ECF7')),
                    ('FONTNAME', (0, 1), (-1, -1), regular_font),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 1), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ]))

                story.append(vitamin_table)
                story.append(Spacer(1, 0.5*cm))

                # Минералы
                story.append(Paragraph("Минералы", styles['CustomHeading']))

                mineral_table_data = [['Минерал', 'Факт', 'Норма', '%']]
                for key, data in list(minerals.items())[:12]:  # Первые 12 минералов
                    consumed_key = 'consumed' if 'consumed' in data else 'average'
                    mineral_table_data.append([
                        data['name'],
                        f"{data[consumed_key]:.1f} {data['unit']}",
                        f"{data['target']} {data['unit']}",
                        f"{data['percentage']:.0f}%"
                    ])

                mineral_table = Table(mineral_table_data, colWidths=[6*cm, 3*cm, 3*cm, 2.5*cm])
                mineral_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E67E22')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), bold_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FDF2E9')),
                    ('FONTNAME', (0, 1), (-1, -1), regular_font),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 1), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ]))

                story.append(mineral_table)

            # Строим PDF
            doc.build(story)
            logger.info(f"Nutrition report PDF generated: {filepath}")

            # Удаляем временные изображения
            if pie_chart_path and os.path.exists(pie_chart_path):
                os.remove(pie_chart_path)
            if progress_bars_path and os.path.exists(progress_bars_path):
                os.remove(progress_bars_path)

            return filepath

        except Exception as e:
            logger.error(f"Error generating nutrition report PDF: {e}")
            raise
