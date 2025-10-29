"""
Сервис для анализа медицинских данных пользователя с помощью AI
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import json

from app.models.medical_analysis import MedicalAnalysis
from app.models.user import User
from loguru import logger


class MedicalAnalysisService:
    """Сервис для работы с медицинскими анализами"""

    @staticmethod
    async def analyze_lab_results(
        user: User,
        raw_data: Dict[str, Any],
        analysis_type: Optional[str] = None,
        analysis_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Анализ лабораторных показателей с помощью Claude AI

        ВАЖНО:
        - НЕ ставим диагнозы
        - НЕ даем рекомендации по лечению
        - Только выявляем дефициты нутриентов
        - При существенных отклонениях рекомендуем врача
        """
        from app.services.claude_ai import ClaudeAIService

        # Формируем промпт для Claude
        prompt = f"""
Проанализируй лабораторные показатели пользователя и выяви дефициты микро- и макронутриентов.

**ВАЖНЫЕ ОГРАНИЧЕНИЯ:**
- НЕ ставь диагнозы
- НЕ давай рекомендации по лечению заболеваний
- Анализируй ТОЛЬКО с точки зрения питания и дефицитов нутриентов
- При существенных отклонениях от нормы - рекомендуй консультацию врача

**Информация о пользователе:**
- Пол: {user.gender.value if user.gender else "не указан"}
- Возраст: {user.age if user.age else "не указан"}
- Вес: {user.current_weight} кг
- Рост: {user.height} см

**Лабораторные показатели:**
{json.dumps(raw_data, ensure_ascii=False, indent=2)}

**Задача:**
1. Проанализируй каждый показатель
2. Выяви возможные дефициты питательных веществ
3. Определи, какие витамины/минералы/нутриенты могут быть в дефиците
4. Оцени, есть ли критические отклонения (нужна ли консультация врача)

**Верни JSON:**
{{
  "detected_deficiencies": [
    {{
      "nutrient": "Железо",  # Название нутриента
      "severity": "moderate",  # low/moderate/high
      "indicator": "Гемоглобин",  # Какой показатель указывает на дефицит
      "current_value": "110 г/л",
      "normal_range": "120-160 г/л",
      "explanation": "Сниженный уровень гемоглобина может указывать на дефицит железа"
    }}
  ],
  "needs_doctor_consultation": false,  # true если есть существенные отклонения
  "doctor_consultation_reason": "",  # Причина, по которой нужен врач (если needs_doctor_consultation=true)
  "nutrition_recommendations": [
    "Увеличить потребление продуктов, богатых железом (красное мясо, печень, бобовые)",
    "Добавить в рацион источники витамина C для лучшего усвоения железа"
  ],
  "summary": "Краткая сводка по анализу (2-3 предложения)"
}}

**ПОМНИ:** Это не медицинское заключение, а рекомендации по питанию на основе лабораторных данных.
"""

        try:
            # Запрашиваем анализ у Claude
            claude = ClaudeAIService()
            response = await claude.analyze_text(prompt)

            # Парсим JSON из ответа
            ai_analysis = claude.extract_json_from_response(response)

            if not ai_analysis:
                raise ValueError("Claude не вернул валидный JSON")

            return {
                "success": True,
                "ai_analysis": ai_analysis,
                "detected_deficiencies": ai_analysis.get("detected_deficiencies", []),
                "needs_doctor_consultation": ai_analysis.get("needs_doctor_consultation", False),
                "recommendations": ai_analysis.get("nutrition_recommendations", []),
                "summary": ai_analysis.get("summary", "")
            }

        except Exception as e:
            logger.error(f"Ошибка анализа медицинских данных: {e}")
            return {
                "success": False,
                "error": str(e),
                "ai_analysis": None,
                "detected_deficiencies": [],
                "needs_doctor_consultation": False,
                "recommendations": [],
                "summary": "Ошибка при анализе данных"
            }

    @staticmethod
    async def save_analysis(
        db: AsyncSession,
        user_id: int,
        raw_data: Dict[str, Any],
        ai_analysis: Optional[Dict[str, Any]] = None,
        analysis_type: Optional[str] = None,
        analysis_date: Optional[datetime] = None,
        file_url: Optional[str] = None,
        user_notes: Optional[str] = None
    ) -> MedicalAnalysis:
        """Сохранение результатов анализа в БД"""

        analysis = MedicalAnalysis(
            user_id=user_id,
            analysis_type=analysis_type,
            analysis_date=analysis_date or datetime.now(),
            raw_data=raw_data,
            file_url=file_url,
            ai_analysis=ai_analysis,
            detected_deficiencies=ai_analysis.get("detected_deficiencies", []) if ai_analysis else [],
            needs_doctor_consultation=ai_analysis.get("needs_doctor_consultation", False) if ai_analysis else False,
            recommendations=ai_analysis.get("summary", "") if ai_analysis else None,
            user_notes=user_notes
        )

        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

        logger.info(f"Сохранен медицинский анализ для пользователя {user_id}")

        return analysis

    @staticmethod
    async def get_user_analyses(
        db: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[MedicalAnalysis]:
        """Получить историю анализов пользователя"""

        result = await db.execute(
            select(MedicalAnalysis)
            .where(MedicalAnalysis.user_id == user_id)
            .order_by(MedicalAnalysis.created_at.desc())
            .limit(limit)
        )

        return result.scalars().all()

    @staticmethod
    async def get_latest_deficiencies(
        db: AsyncSession,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """Получить актуальные дефициты из последнего анализа"""

        result = await db.execute(
            select(MedicalAnalysis)
            .where(MedicalAnalysis.user_id == user_id)
            .order_by(MedicalAnalysis.created_at.desc())
            .limit(1)
        )

        latest = result.scalar_one_or_none()

        if latest and latest.detected_deficiencies:
            return latest.detected_deficiencies

        return []

    @staticmethod
    async def generate_medical_restrictions(
        user: User,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Генерация медицинских ограничений по питанию на основе:
        1. Хронических заболеваний
        2. Удаленных органов
        3. Последних медицинских анализов

        Использует Claude AI для создания списка ограничений
        """
        from app.services.claude_ai import ClaudeAIService

        # Получаем последние дефициты
        deficiencies = await MedicalAnalysisService.get_latest_deficiencies(db, user.id)

        prompt = f"""
Создай список медицинских ограничений и рекомендаций по питанию на основе медицинской информации пользователя.

**ВАЖНО:**
- НЕ ставь диагнозы и не давай медицинские рекомендации
- Формируй ТОЛЬКО ограничения и рекомендации по питанию
- Будь консервативен - безопасность прежде всего

**Информация о пользователе:**
- Пол: {user.gender.value if user.gender else "не указан"}
- Возраст: {user.age if user.age else "не указан"}
- Хронические заболевания: {json.dumps(user.chronic_conditions, ensure_ascii=False) if user.chronic_conditions else "нет"}
- Удаленные органы: {json.dumps(user.removed_organs, ensure_ascii=False) if user.removed_organs else "нет"}
- Выявленные дефициты нутриентов: {json.dumps(deficiencies, ensure_ascii=False) if deficiencies else "нет данных"}

**Задача:**
Создай структурированный список:
1. Продукты/нутриенты, которые НУЖНО увеличить
2. Продукты/нутриенты, которые НУЖНО ограничить
3. Продукты/нутриенты, которые НУЖНО избегать
4. Общие рекомендации

**Верни JSON:**
{{
  "foods_to_increase": ["список продуктов для увеличения"],
  "foods_to_limit": ["список продуктов для ограничения"],
  "foods_to_avoid": ["список продуктов для избегания"],
  "nutrients_to_focus": ["список нутриентов в фокусе"],
  "general_notes": ["общие заметки"],
  "restrictions_summary": "Краткая сводка всех ограничений"
}}
"""

        try:
            claude = ClaudeAIService()
            response = await claude.analyze_text(prompt)
            restrictions = claude.extract_json_from_response(response)

            if not restrictions:
                logger.warning(f"Claude не вернул ограничения для пользователя {user.id}")
                restrictions = {
                    "foods_to_increase": [],
                    "foods_to_limit": [],
                    "foods_to_avoid": [],
                    "nutrients_to_focus": [],
                    "general_notes": [],
                    "restrictions_summary": "Нет специальных ограничений"
                }

            # Сохраняем в профиль пользователя
            user.medical_restrictions = restrictions
            await db.commit()

            logger.info(f"Сгенерированы медицинские ограничения для пользователя {user.id}")

            return restrictions

        except Exception as e:
            logger.error(f"Ошибка генерации медицинских ограничений: {e}")
            return {
                "foods_to_increase": [],
                "foods_to_limit": [],
                "foods_to_avoid": [],
                "nutrients_to_focus": [],
                "general_notes": [],
                "restrictions_summary": "Не удалось сгенерировать ограничения"
            }
