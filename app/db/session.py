"""
Конфигурация SQLAlchemy для работы с SQLite
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Создаем async engine для SQLite
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base класс для моделей
Base = declarative_base()


async def get_session() -> AsyncSession:
    """Dependency для получения сессии БД"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Инициализация БД (создание таблиц)"""
    # Импортируем все модели, чтобы они были зарегистрированы в Base.metadata
    from app.models.user import User  # noqa
    from app.models.chat import ChatMessage  # noqa
    from app.models.usage import DailyUsage  # noqa
    from app.models.meal import Meal, MealFood  # noqa
    from app.models.meal_plan import MealPlan, MealPlanDay, PlannedMeal  # noqa
    from app.models.shopping_list import ShoppingList, ShoppingItem  # noqa
    from app.models.product_price import ProductPrice  # noqa
    from app.models.user_consent import UserConsent  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from loguru import logger
    logger.info("Database tables created successfully")
