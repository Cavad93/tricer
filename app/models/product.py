"""
Модель для кэширования данных о продуктах
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from datetime import datetime
import hashlib
from app.db.session import Base


class Product(Base):
    """
    Кэш данных о продуктах с их нутриентами.

    Используется для хранения информации о продуктах, полученной из:
    - Веб-поиска (DuckDuckGo + Haiku 4.5)
    - Claude Vision анализа фото
    - Пользовательского ввода

    Позволяет избежать повторных запросов к внешним API для идентичных продуктов.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    # Название продукта
    name = Column(String(500), nullable=False, index=True)  # Оригинальное название
    name_normalized = Column(String(500), nullable=False, index=True)  # Нормализованное для поиска
    name_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 хеш для быстрого поиска

    # Основные макронутриенты (на 100г)
    calories = Column(Float, nullable=False)  # ккал
    proteins = Column(Float, nullable=False)  # г
    fats = Column(Float, nullable=False)  # г
    carbs = Column(Float, nullable=False)  # г

    # Микронутриенты (на 100г) - JSONB для гибкости
    # Структура: {"vitamins": {...}, "minerals": {...}}
    micronutrients = Column(JSONB, default=dict)

    # Дополнительная информация
    category = Column(String(100), nullable=True)  # Категория продукта (фрукты, мясо, и т.д.)
    source = Column(String(50), nullable=False)  # Источник данных (web_search, ai_vision, user_input)
    confidence = Column(Float, nullable=True)  # Уверенность AI в данных (0.0-1.0)

    # Статистика использования
    usage_count = Column(Integer, default=1)  # Количество использований
    last_used_at = Column(DateTime, default=func.now())  # Последнее использование

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Индексы для быстрого поиска
    __table_args__ = (
        Index('idx_product_name_search', 'name_normalized'),
        Index('idx_product_hash_unique', 'name_hash'),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, calories={self.calories})>"

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Нормализует название продукта для поиска.

        Args:
            name: Оригинальное название

        Returns:
            Нормализованное название (lowercase, без лишних пробелов)
        """
        return " ".join(name.lower().strip().split())

    @staticmethod
    def generate_hash(name: str) -> str:
        """
        Генерирует SHA256 хеш для названия продукта.

        Args:
            name: Название продукта (нормализованное)

        Returns:
            SHA256 хеш (hex строка)
        """
        normalized = Product.normalize_name(name)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def to_dict(self) -> dict:
        """
        Преобразует продукт в словарь.

        Returns:
            Словарь с данными продукта
        """
        return {
            "id": self.id,
            "name": self.name,
            "name_normalized": self.name_normalized,
            "calories": self.calories,
            "proteins": self.proteins,
            "fats": self.fats,
            "carbs": self.carbs,
            "micronutrients": self.micronutrients,
            "category": self.category,
            "source": self.source,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_top_micronutrients(self, limit: int = 5) -> list:
        """
        Возвращает топ-N микронутриентов по количеству.

        Args:
            limit: Количество микронутриентов для возврата

        Returns:
            Список кортежей (название, значение, единица измерения)
        """
        if not self.micronutrients:
            return []

        all_nutrients = []

        # Собираем витамины
        vitamins = self.micronutrients.get("vitamins", {})
        for name, value in vitamins.items():
            if value and value > 0:
                unit = "мкг" if "b12" in name.lower() or "b9" in name.lower() or "d" in name.lower() else "мг"
                all_nutrients.append((name, value, unit))

        # Собираем минералы
        minerals = self.micronutrients.get("minerals", {})
        for name, value in minerals.items():
            if value and value > 0:
                unit = "мкг" if name.lower() in ["iodine", "selenium", "chromium"] else "мг"
                all_nutrients.append((name, value, unit))

        # Сортируем по значению (в порядке убывания) и берем топ-N
        all_nutrients.sort(key=lambda x: x[1], reverse=True)
        return all_nutrients[:limit]

    def format_micronutrients_display(self) -> str:
        """
        Форматирует микронутриенты для отображения пользователю.

        Returns:
            Строка с топ-5 микронутриентами
        """
        top_nutrients = self.get_top_micronutrients(limit=5)
        if not top_nutrients:
            return "Данные по микронутриентам отсутствуют"

        lines = []
        for name, value, unit in top_nutrients:
            # Красивое название
            display_name = name.replace("_", " ").title()
            lines.append(f"  • {display_name}: {value:.1f} {unit}")

        return "\n".join(lines)
