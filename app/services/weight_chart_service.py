"""
Сервис для генерации графиков изменения веса
"""
from datetime import datetime, timedelta
from typing import List, Optional, BinaryIO
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Backend без GUI для серверной среды
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from app.models.weight_history import WeightHistory
from loguru import logger


class WeightChartService:
    """Сервис для создания визуализаций истории веса"""

    @staticmethod
    def generate_weight_chart(
        weight_history: List[WeightHistory],
        target_weight: Optional[float] = None,
        user_name: Optional[str] = None,
        height: Optional[int] = None
    ) -> BytesIO:
        """
        Генерирует график изменения веса

        Args:
            weight_history: Список записей истории веса (отсортированных по дате)
            target_weight: Целевой вес пользователя (для линии цели)
            user_name: Имя пользователя для заголовка
            height: Рост пользователя для расчета диапазона здорового веса

        Returns:
            BytesIO объект с изображением графика в формате PNG
        """
        if not weight_history:
            logger.warning("No weight history data to generate chart")
            return WeightChartService._generate_empty_chart()

        # Извлекаем данные
        dates = [entry.measured_at for entry in weight_history]
        weights = [entry.weight for entry in weight_history]

        # Создаем фигуру с заданным размером и разрешением
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)

        # Настройка цветов и стиля
        bg_color = '#f8f9fa'
        grid_color = '#dee2e6'
        main_line_color = '#0d6efd'
        target_line_color = '#198754'
        healthy_range_color = '#20c997'

        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        # Рисуем диапазон здорового веса (если указан рост)
        if height:
            from app.services.nutrition_calc import NutritionCalculator
            min_healthy, max_healthy = NutritionCalculator.get_healthy_weight_range(height)

            ax.axhspan(min_healthy, max_healthy, alpha=0.15, color=healthy_range_color,
                      label=f'Здоровый диапазон ({min_healthy}-{max_healthy} кг)')

        # Рисуем линию целевого веса
        if target_weight:
            ax.axhline(y=target_weight, color=target_line_color, linestyle='--',
                      linewidth=2, label=f'Целевой вес ({target_weight} кг)')

        # Основная линия веса
        ax.plot(dates, weights, marker='o', linewidth=2.5, markersize=6,
               color=main_line_color, label='Текущий вес')

        # Подписи значений на точках (только если точек не много)
        if len(weights) <= 15:
            for date, weight in zip(dates, weights):
                ax.annotate(f'{weight:.1f}',
                          xy=(date, weight),
                          xytext=(0, 10),
                          textcoords='offset points',
                          ha='center',
                          fontsize=8,
                          color='#495057')

        # Заголовок
        title = "График изменения веса"
        if user_name:
            title = f"График изменения веса - {user_name}"
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20, color='#212529')

        # Подписи осей
        ax.set_xlabel('Дата', fontsize=12, fontweight='bold', color='#495057')
        ax.set_ylabel('Вес (кг)', fontsize=12, fontweight='bold', color='#495057')

        # Форматирование дат на оси X
        if len(dates) > 1:
            days_range = (dates[-1] - dates[0]).days
            if days_range <= 14:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                ax.xaxis.set_major_locator(mdates.DayLocator())
            elif days_range <= 90:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                ax.xaxis.set_major_locator(mdates.WeekdayLocator())
            else:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m.%Y'))
                ax.xaxis.set_major_locator(mdates.MonthLocator())

        # Поворот подписей дат
        plt.xticks(rotation=45, ha='right')

        # Сетка
        ax.grid(True, alpha=0.3, color=grid_color, linestyle='-', linewidth=0.5)
        ax.set_axisbelow(True)

        # Легенда
        ax.legend(loc='best', framealpha=0.9, edgecolor='#ced4da')

        # Рамка
        for spine in ax.spines.values():
            spine.set_edgecolor('#ced4da')
            spine.set_linewidth(1.5)

        # Статистика внизу графика
        if len(weights) >= 2:
            start_weight = weights[0]
            current_weight = weights[-1]
            weight_change = current_weight - start_weight
            change_percent = (weight_change / start_weight) * 100

            if weight_change < 0:
                stats_text = f"📉 Потеря веса: {abs(weight_change):.1f} кг ({abs(change_percent):.1f}%)"
                stats_color = '#198754'
            elif weight_change > 0:
                stats_text = f"📈 Набор веса: {weight_change:.1f} кг ({change_percent:.1f}%)"
                stats_color = '#fd7e14'
            else:
                stats_text = "Вес стабилен"
                stats_color = '#0d6efd'

            days_tracking = (dates[-1] - dates[0]).days
            stats_text += f" | Период отслеживания: {days_tracking} дней"

            fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10,
                    color=stats_color, fontweight='bold')

        # Автоматическая подгонка layout
        plt.tight_layout()

        # Сохраняем в BytesIO
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor=bg_color, edgecolor='none')
        buf.seek(0)

        plt.close(fig)

        logger.info("Weight chart generated successfully")
        return buf

    @staticmethod
    def _generate_empty_chart() -> BytesIO:
        """
        Генерирует пустой график с сообщением об отсутствии данных

        Returns:
            BytesIO объект с изображением
        """
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)

        bg_color = '#f8f9fa'
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        ax.text(0.5, 0.5, 'Недостаточно данных для отображения графика\n\n'
                          'Добавьте записи о весе в профиле',
                ha='center', va='center', fontsize=14, color='#6c757d')

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight',
                   facecolor=bg_color, edgecolor='none')
        buf.seek(0)

        plt.close(fig)

        return buf
