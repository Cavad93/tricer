"""
Главный файл FastAPI приложения NutriAI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.db.session import init_db
from app.api.v1 import users

# Создаем FastAPI приложение
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="NutriAI - AI-powered nutrition tracking bot",
    debug=settings.DEBUG,
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Событие при запуске приложения"""
    logger.info("Starting FastAPI application...")

    # Инициализация БД
    await init_db()
    logger.info("Database initialized successfully")


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "NutriAI API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV
    }


# Подключаем роутеры API
app.include_router(users.router, prefix="/api/v1", tags=["users"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
