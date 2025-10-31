"""
Конфигурация SQLAlchemy для работы с PostgreSQL
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Создаем async engine для PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,

    # === НАСТРОЙКИ ПУЛА СОЕДИНЕНИЙ ===
    pool_pre_ping=True,        # Проверка соединения перед использованием
    pool_size=50,               # Увеличено с 10 до 50 для поддержки большего количества одновременных пользователей
    max_overflow=100,           # Увеличено с 20 до 100 (итого max 150 соединений)
    pool_timeout=30,            # Время ожидания свободного соединения (30 сек)
    pool_recycle=3600,          # Пересоздание соединений каждый час (избегаем "мёртвых" соединений)

    # === НАСТРОЙКИ СОЕДИНЕНИЙ ===
    connect_args={
        "server_settings": {
            "application_name": "nutriai_bot",  # Для мониторинга в PostgreSQL
        },
        "command_timeout": 60,     # Таймаут для команд (60 сек)
        "timeout": 10,             # Таймаут подключения (10 сек)
    },
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
    from app.models.micronutrients import DailyMicronutrients  # noqa
    from app.models.food_correction import FoodRecognitionCorrection  # noqa
    from app.models.medical_analysis import MedicalAnalysis  # noqa
    from app.models.wellness_log import WellnessLog  # noqa
    from app.models.pantry import UserPantry, PantryUsageLog  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from loguru import logger
    logger.info("Database tables created successfully")
