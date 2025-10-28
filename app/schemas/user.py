"""
Pydantic схемы для пользователя
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.user import Gender, Goal, ActivityLevel, DietType, SubscriptionType


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "ru"


class UserCreate(UserBase):
    """Схема для создания пользователя"""
    pass


class UserProfileUpdate(BaseModel):
    """Схема для обновления профиля"""
    gender: Optional[Gender] = None
    birth_year: Optional[int] = Field(None, ge=1900, le=2024)
    height: Optional[int] = Field(None, ge=100, le=250)  # см
    current_weight: Optional[float] = Field(None, ge=30, le=300)  # кг
    target_weight: Optional[float] = Field(None, ge=30, le=300)  # кг
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None
    diet_type: Optional[DietType] = None
    allergies: Optional[List[str]] = None
    dislikes: Optional[List[str]] = None


class UserResponse(UserBase):
    """Схема для ответа"""
    id: int
    gender: Optional[Gender] = None
    birth_year: Optional[int] = None
    height: Optional[int] = None
    current_weight: Optional[float] = None
    target_weight: Optional[float] = None
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None
    target_calories: Optional[int] = None
    target_proteins: Optional[int] = None
    target_fats: Optional[int] = None
    target_carbs: Optional[int] = None
    diet_type: Optional[DietType] = None
    allergies: List[str] = []
    dislikes: List[str] = []
    subscription_type: SubscriptionType
    is_premium: bool = False
    onboarding_completed: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NutritionTargets(BaseModel):
    """Схема для целевых показателей питания"""
    calories: int
    proteins: int
    fats: int
    carbs: int
