"""
Celery задачи для работы с кэшированными планами питания

ВАЖНО: Использует специальный механизм управления event loop
для предотвращения ошибки "RuntimeError: Event loop is closed"
"""
from app.celery_app import celery_app
from app.db.celery_session import celery_session_maker, cleanup_celery_connections
from app.celery_event_loop import run_async_task
from app.models.meal_plan import PlanPeriod
from app.services.cached_meal_plan_service import CachedMealPlanService
from app.services.meal_plan_service import MealPlanService
from app.models.user import User
from loguru import logger
from datetime import datetime
from sqlalchemy import select


@celery_app.task(
    bind=True,
    name='tasks.update_cached_meal_plans',
    max_retries=3,
    default_retry_delay=300,  # 5 минут
    soft_time_limit=1800,     # Мягкий лимит 30 минут
    time_limit=2400           # Жесткий лимит 40 минут
)
def update_cached_meal_plans_task(self):
    """
    Периодическая задача для обновления кэша планов питания.

    Запускается каждые 24 часа (настраивается в celery beat).

    Логика:
    1. Помечает старые планы (>7 дней) как устаревшие
    2. Находит категории с недостаточным количеством планов
    3. Генерирует новые планы через AI для этих категорий
    """
    try:
        logger.info("🔄 Starting cached meal plans update task...")

        # Используем run_async_task вместо asyncio.run()
        result = run_async_task(_update_cached_plans_async)

        logger.info(f"✅ Cached meal plans update complete: {result}")
        return result

    except Exception as exc:
        logger.error(f"❌ Error in cached meal plans update task: {exc}")
        raise self.retry(exc=exc)

    finally:
        # Очищаем соединения после задачи
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"Error during connection cleanup: {cleanup_error}")


async def _update_cached_plans_async():
        try:
            async with celery_session_maker() as session:
                logger.info("🔄 Starting cached meal plans update task...")

                # Шаг 1: Помечаем старые планы как устаревшие
                outdated_count = await CachedMealPlanService.mark_old_plans_outdated(session, days_old=7)
                logger.info(f"✅ Marked {outdated_count} plans as outdated")

                # Шаг 2: Находим категории которым нужно больше планов
                categories_needing_plans = await CachedMealPlanService.get_categories_needing_plans(
                    session,
                    min_plans_per_period=20  # Минимум 20 планов на период
                )

                if not categories_needing_plans:
                    logger.info("✅ All categories have sufficient plans")
                    return {
                        "status": "success",
                        "outdated_count": outdated_count,
                        "generated_count": 0,
                        "message": "All categories have sufficient plans"
                    }

                logger.info(f"Found {len(categories_needing_plans)} category-period pairs needing plans")

                # Шаг 3: Генерируем новые планы
                generated_count = 0
                for item in categories_needing_plans[:50]:  # Ограничиваем 50 планами за раз
                    category = item["category"]
                    period_type_str = item["period_type"]
                    needed_count = item["needed_count"]

                    # Конвертируем period_type в enum
                    period_map = {
                        "day": PlanPeriod.DAY,
                        "week": PlanPeriod.WEEK,
                        "month": PlanPeriod.MONTH
                    }
                    period_type = period_map.get(period_type_str)

                    if not period_type:
                        logger.warning(f"Unknown period type: {period_type_str}")
                        continue

                    logger.info(f"Generating {needed_count} plans for category {category.id}, period {period_type_str}")

                    # Генерируем недостающие планы (максимум 5 за категорию за раз)
                    for i in range(min(needed_count, 5)):
                        try:
                            # Создаем временного пользователя с параметрами категории
                            mock_user = User(
                                telegram_id=0,  # Фиктивный ID
                                target_calories=category.target_calories,
                                target_proteins=category.target_proteins,
                                target_fats=category.target_fats,
                                target_carbs=category.target_carbs,
                                allergies=category.allergies or []
                            )

                            # Устанавливаем enum значения
                            from app.models.user import DietType, BudgetCategory
                            mock_user.diet_type = DietType(category.diet_type)
                            mock_user.budget_category = BudgetCategory(category.budget_category)

                            # Формируем промпт и генерируем план через AI
                            days_count = {
                                PlanPeriod.DAY: 1,
                                PlanPeriod.WEEK: 7,
                                PlanPeriod.MONTH: 30
                            }[period_type]

                            prompt = MealPlanService._build_meal_plan_prompt(
                                user=mock_user,
                                period_type=period_type,
                                days_count=days_count,
                                preferences=None,
                                medical_context=None,
                                old_plan_data=None,
                                batch_cooking=False,
                                personal_insights=None
                            )

                            # Генерируем через AI
                            from app.services.claude_ai import ClaudeAIService
                            from app.config import settings

                            ai_service = ClaudeAIService()
                            ai_response = await ai_service.async_client.messages.create(
                                model=settings.CLAUDE_MODEL,
                                max_tokens=16000,
                                temperature=0.8,
                                messages=[{
                                    "role": "user",
                                    "content": prompt
                                }]
                            )

                            plan_data = ai_response.content[0].text
                            parsed_plan = MealPlanService._parse_ai_meal_plan(plan_data)

                            # Сохраняем в кэш
                            await CachedMealPlanService.save_cached_plan(
                                session,
                                category,
                                period_type,
                                parsed_plan
                            )

                            generated_count += 1
                            logger.info(f"✅ Generated plan {i+1}/{min(needed_count, 5)} for category {category.id}")

                        except Exception as e:
                            logger.error(f"Failed to generate plan for category {category.id}: {repr(e)}")
                            continue

                logger.info(f"✅ Cached meal plans update complete: outdated={outdated_count}, generated={generated_count}")

                return {
                    "status": "success",
                    "outdated_count": outdated_count,
                    "generated_count": generated_count,
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"❌ Error in _update_cached_plans_async: {repr(e)}")
            raise


@celery_app.task(name='tasks.initialize_cached_plans_for_new_user')
def initialize_cached_plans_for_new_user_task(user_id: int):
    """
    Инициализирует кэшированные планы для новой категории пользователя.

    Вызывается после регистрации нового пользователя или изменения его параметров.

    Args:
        user_id: ID пользователя в Telegram
    """
    try:
        run_async_task(_initialize_plans_async, user_id)
    finally:
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"Error during connection cleanup: {cleanup_error}")


async def _initialize_plans_async(user_id: int):
        try:
            async with celery_session_maker() as session:

                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    logger.warning(f"User {user_id} not found for cache initialization")
                    return

                # Определяем категорию пользователя
                category = await CachedMealPlanService.get_or_create_category(session, user)

                logger.info(f"Initializing cached plans for user {user_id}, category {category.id}")

                # Проверяем сколько планов уже есть для этой категории
                stats = await CachedMealPlanService.get_category_stats(session, category.id)

                if stats.get("total_plans", 0) >= 10:
                    logger.info(f"Category {category.id} already has sufficient plans ({stats['total_plans']})")
                    return

                logger.info(f"Category {category.id} needs more plans, will be generated in next update cycle")

        except Exception as e:
            logger.error(f"Error initializing cached plans for user {user_id}: {repr(e)}")


@celery_app.task(name='tasks.cleanup_unused_cached_plans')
def cleanup_unused_cached_plans_task():
    """
    Удаляет неиспользуемые кэшированные планы.

    Критерии удаления:
    - План не использовался более 30 дней
    - План помечен как OUTDATED более 14 дней назад
    - Категория имеет 0 пользователей
    """
    try:
        return run_async_task(_cleanup_async)
    finally:
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"Error during connection cleanup: {cleanup_error}")


async def _cleanup_async():
        try:
            from datetime import timedelta
            from sqlalchemy import and_, delete
            from app.models.cached_meal_plan import CachedMealPlan, CachedMealPlanStatus, UserCategory

            async with celery_session_maker() as session:

                logger.info("🧹 Starting cleanup of unused cached plans...")

                cutoff_date_30 = datetime.now() - timedelta(days=30)
                cutoff_date_14 = datetime.now() - timedelta(days=14)

                # Удаляем старые неиспользуемые планы
                result = await session.execute(
                    delete(CachedMealPlan).where(
                        and_(
                            CachedMealPlan.last_used_at < cutoff_date_30,
                            CachedMealPlan.usage_count == 0
                        )
                    )
                )
                unused_count = result.rowcount

                # Удаляем устаревшие планы
                result = await session.execute(
                    delete(CachedMealPlan).where(
                        and_(
                            CachedMealPlan.status == CachedMealPlanStatus.OUTDATED,
                            CachedMealPlan.updated_at < cutoff_date_14
                        )
                    )
                )
                outdated_count = result.rowcount

                # Удаляем категории без пользователей
                result = await session.execute(
                    delete(UserCategory).where(UserCategory.users_count == 0)
                )
                empty_categories = result.rowcount

                await session.commit()

                logger.info(f"✅ Cleanup complete: unused={unused_count}, outdated={outdated_count}, empty_categories={empty_categories}")

                return {
                    "status": "success",
                    "unused_count": unused_count,
                    "outdated_count": outdated_count,
                    "empty_categories": empty_categories
                }

        except Exception as e:
            logger.error(f"Error in cleanup task: {repr(e)}")
            raise


@celery_app.task(name='tasks.deactivate_expired_plans')
def deactivate_expired_plans_task():
    """
    Деактивирует истёкшие планы питания.

    Критерии деактивации:
    - План активен (is_active=True)
    - Дата окончания плана (end_date) прошла

    Запускается каждый день в 1:00 UTC через Celery Beat.
    """
    try:
        logger.info("🔄 Starting deactivation of expired meal plans...")
        return run_async_task(_deactivate_expired_plans_async)
    finally:
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"Error during connection cleanup: {cleanup_error}")


async def _deactivate_expired_plans_async():
    """
    Асинхронная часть деактивации истёкших планов
    """
    try:
        async with celery_session_maker() as session:
            # Используем метод сервиса для деактивации
            deactivated_count = await MealPlanService.deactivate_expired_plans(session)

            logger.info(f"✅ Deactivated {deactivated_count} expired meal plans")

            return {
                "status": "success",
                "deactivated_count": deactivated_count,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"❌ Error deactivating expired plans: {repr(e)}")
        raise
