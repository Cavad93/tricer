"""
API эндпоинты для работы с AI-чатом
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.user import User
from app.models.chat import MessageRole
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    UsageStatsResponse,
    ChatMessageResponse
)
from app.services.chat_service import ChatService
from app.services.usage_service import UsageService
from app.services.claude_ai import get_claude_service
from loguru import logger

router = APIRouter()


@router.post("/chat/{telegram_id}", response_model=ChatResponse)
async def send_chat_message(
    telegram_id: int,
    request: ChatRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Отправить сообщение в AI-чат

    Args:
        telegram_id: Telegram ID пользователя
        request: Запрос с сообщением
        session: Сессия БД

    Returns:
        Ответ от AI-ассистента
    """
    # Получаем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем лимиты использования
    can_use, remaining = await UsageService.can_use_chat(session, user.id)

    if not can_use:
        raise HTTPException(
            status_code=429,
            detail=f"Daily chat limit reached. Upgrade to Premium for unlimited access."
        )

    try:
        # Получаем контекст пользователя
        user_context = await ChatService.get_user_context(session, user.id)

        # Получаем историю разговора (если нужно)
        conversation_history = []
        if request.include_history:
            conversation_history = await ChatService.get_chat_context(session, user.id, limit=10)

        # Отправляем запрос к Claude API
        logger.info(f"Sending chat request for user {telegram_id}")
        assistant_response = await get_claude_service().chat(
            user_message=request.message,
            conversation_history=conversation_history,
            user_context=user_context
        )

        # Сохраняем сообщение пользователя
        await ChatService.save_message(
            session=session,
            user_id=user.id,
            role=MessageRole.USER,
            content=request.message
        )

        # Сохраняем ответ ассистента
        await ChatService.save_message(
            session=session,
            user_id=user.id,
            role=MessageRole.ASSISTANT,
            content=assistant_response
        )

        # Увеличиваем счетчик использования
        await UsageService.increment_chat_usage(session, user.id)

        # Проверяем новый остаток
        _, new_remaining = await UsageService.can_use_chat(session, user.id)

        logger.info(f"Chat response sent to user {telegram_id}")

        return ChatResponse(
            message=assistant_response,
            remaining_messages=new_remaining
        )

    except Exception as e:
        logger.error("Error in chat for user {}: {}", telegram_id, repr(e))
        raise HTTPException(status_code=500, detail="Failed to process chat message")


@router.get("/chat/{telegram_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    telegram_id: int,
    limit: int = 20,
    session: AsyncSession = Depends(get_session)
):
    """
    Получить историю чата

    Args:
        telegram_id: Telegram ID пользователя
        limit: Количество сообщений
        session: Сессия БД

    Returns:
        История сообщений
    """
    # Получаем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получаем историю
    messages = await ChatService.get_chat_history(session, user.id, limit)
    total = await ChatService.get_total_messages_count(session, user.id)

    return ChatHistoryResponse(
        messages=[ChatMessageResponse.from_orm(msg) for msg in messages],
        total=total,
        has_more=total > limit
    )


@router.delete("/chat/{telegram_id}/history")
async def clear_chat_history(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Очистить историю чата

    Args:
        telegram_id: Telegram ID пользователя
        session: Сессия БД

    Returns:
        Результат операции
    """
    # Получаем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Очищаем историю
    count = await ChatService.clear_chat_history(session, user.id)

    return {
        "message": "Chat history cleared successfully",
        "deleted_messages": count
    }


@router.get("/usage/{telegram_id}", response_model=UsageStatsResponse)
async def get_usage_stats(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Получить статистику использования API

    Args:
        telegram_id: Telegram ID пользователя
        session: Сессия БД

    Returns:
        Статистика использования
    """
    # Получаем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получаем статистику
    stats = await UsageService.get_usage_stats(session, user.id)

    if not stats:
        raise HTTPException(status_code=404, detail="Usage stats not found")

    return UsageStatsResponse(**stats)
