"""
API эндпоинты для работы с пользователями
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_session
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserProfileUpdate, NutritionTargets
from app.services.nutrition_calc import NutritionCalculator

router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Создание нового пользователя
    """
    # Проверяем, существует ли пользователь
    result = await session.execute(
        select(User).where(User.telegram_id == user_data.telegram_id)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    # Создаем нового пользователя
    new_user = User(
        telegram_id=user_data.telegram_id,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        language_code=user_data.language_code,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return new_user


@router.get("/users/{telegram_id}", response_model=UserResponse)
async def get_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Получение пользователя по telegram_id
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.patch("/users/{telegram_id}", response_model=UserResponse)
async def update_user_profile(
    telegram_id: int,
    profile_data: UserProfileUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Обновление профиля пользователя
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем поля профиля
    update_data = profile_data.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user, field, value)

    # Если обновлены параметры для расчета - пересчитываем целевые показатели
    if all([user.gender, user.birth_year, user.height, user.current_weight, user.activity_level, user.goal]):
        age = 2024 - user.birth_year
        nutrition_targets = NutritionCalculator.calculate_nutrition_targets(
            gender=user.gender,
            weight=user.current_weight,
            height=user.height,
            age=age,
            activity_level=user.activity_level,
            goal=user.goal,
        )

        user.target_calories = nutrition_targets.calories
        user.target_proteins = nutrition_targets.proteins
        user.target_fats = nutrition_targets.fats
        user.target_carbs = nutrition_targets.carbs
        user.onboarding_completed = True

    await session.commit()
    await session.refresh(user)

    return user


@router.get("/users/{telegram_id}/nutrition-targets", response_model=NutritionTargets)
async def get_nutrition_targets(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Получение целевых показателей питания пользователя
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.target_calories:
        raise HTTPException(status_code=400, detail="User profile is not completed")

    return NutritionTargets(
        calories=user.target_calories,
        proteins=user.target_proteins,
        fats=user.target_fats,
        carbs=user.target_carbs,
    )


@router.delete("/users/{telegram_id}", status_code=204)
async def delete_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Удаление пользователя
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()

    return None
