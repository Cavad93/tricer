"""
Модель для хранения актуальных цен на продукты
Кэш цен с автоматическим обновлением раз в сутки
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from datetime import datetime
from app.db.session import Base


class ProductPrice(Base):
    """
    Модель для хранения актуальных цен на продукты по городам

    Цены кэшируются для ускорения работы и уменьшения запросов к AI.
    Обновляются автоматически раз в сутки.
    """
    __tablename__ = "product_prices"

    id = Column(Integer, primary_key=True, index=True)

    # Информация о продукте
    product_name = Column(String(255), nullable=False, index=True)  # Нормализованное название
    unit = Column(String(50), nullable=False)  # Единица измерения (кг, л, шт и т.д.)

    # Локация
    country = Column(String(100), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)

    # Бюджетная категория
    budget_category = Column(String(20), nullable=False, index=True)  # economy/normal/premium

    # Цены
    price = Column(Float, nullable=False)  # Цена за указанное количество
    price_per_unit = Column(Float, nullable=False)  # Цена за единицу

    # Информация о магазине
    shop_name = Column(String(255), nullable=True)
    shop_url = Column(String(500), nullable=True)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Составной индекс для быстрого поиска
    __table_args__ = (
        Index(
            'idx_product_location_budget',
            'product_name', 'city', 'country', 'budget_category'
        ),
    )

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "product_name": self.product_name,
            "unit": self.unit,
            "country": self.country,
            "city": self.city,
            "budget_category": self.budget_category,
            "price": self.price,
            "price_per_unit": self.price_per_unit,
            "shop_name": self.shop_name,
            "shop_url": self.shop_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    def is_stale(self, hours: int = 24) -> bool:
        """
        Проверка, устарела ли цена

        Args:
            hours: Количество часов, после которых цена считается устаревшей

        Returns:
            True если цена устарела, False если актуальна
        """
        from datetime import timedelta
        if not self.last_updated:
            return True
        age = datetime.utcnow() - self.last_updated
        return age > timedelta(hours=hours)

    def __repr__(self):
        return f"<ProductPrice {self.product_name} in {self.city}, {self.country}: {self.price} руб/{self.unit}>"
