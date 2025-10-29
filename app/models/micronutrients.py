"""
Модели для учета микронутриентов (витаминов и минералов)
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import date
from app.db.session import Base


class DailyMicronutrients(Base):
    """Суточная статистика по микронутриентам"""
    __tablename__ = "daily_micronutrients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)  # Дата

    # Витамины (мкг/мг)
    vitamin_a = Column(Float, default=0)  # Витамин A (мкг)
    beta_carotene = Column(Float, default=0)  # Бета-каротин (мкг)
    vitamin_b1 = Column(Float, default=0)  # B1 Тиамин (мг)
    vitamin_b2 = Column(Float, default=0)  # B2 Рибофлавин (мг)
    vitamin_b3 = Column(Float, default=0)  # B3 Ниацин/PP (мг)
    vitamin_b5 = Column(Float, default=0)  # B5 Пантотеновая кислота (мг)
    vitamin_b6 = Column(Float, default=0)  # B6 Пиридоксин (мг)
    vitamin_b7 = Column(Float, default=0)  # B7 Биотин/H (мкг)
    vitamin_b9 = Column(Float, default=0)  # B9 Фолиевая кислота (мкг)
    vitamin_b12 = Column(Float, default=0)  # B12 Кобаламин (мкг)
    vitamin_c = Column(Float, default=0)  # Витамин C (мг)
    vitamin_d = Column(Float, default=0)  # Витамин D (мкг)
    vitamin_e = Column(Float, default=0)  # Витамин E (мг)
    vitamin_k = Column(Float, default=0)  # Витамин K (мкг)
    choline = Column(Float, default=0)  # Холин (мг)

    # Минералы (мг/мкг)
    calcium = Column(Float, default=0)  # Кальций Ca (мг)
    phosphorus = Column(Float, default=0)  # Фосфор P (мг)
    magnesium = Column(Float, default=0)  # Магний Mg (мг)
    potassium = Column(Float, default=0)  # Калий K (мг)
    sodium = Column(Float, default=0)  # Натрий Na (мг)
    chloride = Column(Float, default=0)  # Хлор Cl (мг)
    iron = Column(Float, default=0)  # Железо Fe (мг)
    zinc = Column(Float, default=0)  # Цинк Zn (мг)
    iodine = Column(Float, default=0)  # Йод I (мкг)
    selenium = Column(Float, default=0)  # Селен Se (мкг)
    copper = Column(Float, default=0)  # Медь Cu (мг)
    manganese = Column(Float, default=0)  # Марганец Mn (мг)
    chromium = Column(Float, default=0)  # Хром Cr (мкг)
    fluoride = Column(Float, default=0)  # Фтор F (мг)
    cobalt = Column(Float, default=0)  # Кобальт Co (мкг)
    silicon = Column(Float, default=0)  # Кремний Si (мг)

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DailyMicronutrients(user_id={self.user_id}, date={self.date})>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "vitamins": {
                "A": self.vitamin_a,
                "beta_carotene": self.beta_carotene,
                "B1": self.vitamin_b1,
                "B2": self.vitamin_b2,
                "B3": self.vitamin_b3,
                "B5": self.vitamin_b5,
                "B6": self.vitamin_b6,
                "B7": self.vitamin_b7,
                "B9": self.vitamin_b9,
                "B12": self.vitamin_b12,
                "C": self.vitamin_c,
                "D": self.vitamin_d,
                "E": self.vitamin_e,
                "K": self.vitamin_k,
                "choline": self.choline,
            },
            "minerals": {
                "calcium": self.calcium,
                "phosphorus": self.phosphorus,
                "magnesium": self.magnesium,
                "potassium": self.potassium,
                "sodium": self.sodium,
                "chloride": self.chloride,
                "iron": self.iron,
                "zinc": self.zinc,
                "iodine": self.iodine,
                "selenium": self.selenium,
                "copper": self.copper,
                "manganese": self.manganese,
                "chromium": self.chromium,
                "fluoride": self.fluoride,
                "cobalt": self.cobalt,
                "silicon": self.silicon,
            }
        }


class MicronutrientTargets:
    """
    Справочник целевых значений микронутриентов (суточная норма)
    Источник: Нормы физиологических потребностей в энергии и пищевых веществах
    для различных групп населения РФ (МР 2.3.1.0253-21)
    """

    # Целевые значения для взрослых (усредненные)
    # Для точных значений нужно учитывать возраст, пол, вес, беременность и т.д.

    DAILY_TARGETS = {
        # Витамины
        "vitamin_a": {  # мкг
            "male": 900,
            "female": 700,
            "unit": "мкг",
            "name": "Витамин A"
        },
        "beta_carotene": {  # мкг
            "male": 5000,
            "female": 5000,
            "unit": "мкг",
            "name": "Бета-каротин"
        },
        "vitamin_b1": {  # мг
            "male": 1.5,
            "female": 1.5,
            "unit": "мг",
            "name": "Витамин B1 (Тиамин)"
        },
        "vitamin_b2": {  # мг
            "male": 1.8,
            "female": 1.8,
            "unit": "мг",
            "name": "Витамин B2 (Рибофлавин)"
        },
        "vitamin_b3": {  # мг (PP)
            "male": 20,
            "female": 20,
            "unit": "мг",
            "name": "Витамин B3/PP (Ниацин)"
        },
        "vitamin_b5": {  # мг
            "male": 5,
            "female": 5,
            "unit": "мг",
            "name": "Витамин B5 (Пантотеновая к-та)"
        },
        "vitamin_b6": {  # мг
            "male": 2.0,
            "female": 2.0,
            "unit": "мг",
            "name": "Витамин B6 (Пиридоксин)"
        },
        "vitamin_b7": {  # мкг (H)
            "male": 50,
            "female": 50,
            "unit": "мкг",
            "name": "Витамин B7/H (Биотин)"
        },
        "vitamin_b9": {  # мкг
            "male": 400,
            "female": 400,
            "unit": "мкг",
            "name": "Витамин B9 (Фолиевая к-та)"
        },
        "vitamin_b12": {  # мкг
            "male": 3,
            "female": 3,
            "unit": "мкг",
            "name": "Витамин B12 (Кобаламин)"
        },
        "vitamin_c": {  # мг
            "male": 90,
            "female": 90,
            "unit": "мг",
            "name": "Витамин C"
        },
        "vitamin_d": {  # мкг
            "male": 10,
            "female": 10,
            "unit": "мкг",
            "name": "Витамин D"
        },
        "vitamin_e": {  # мг
            "male": 15,
            "female": 15,
            "unit": "мг",
            "name": "Витамин E"
        },
        "vitamin_k": {  # мкг
            "male": 120,
            "female": 120,
            "unit": "мкг",
            "name": "Витамин K"
        },
        "choline": {  # мг
            "male": 500,
            "female": 500,
            "unit": "мг",
            "name": "Холин"
        },

        # Минералы
        "calcium": {  # мг
            "male": 1000,
            "female": 1000,
            "unit": "мг",
            "name": "Кальций (Ca)"
        },
        "phosphorus": {  # мг
            "male": 800,
            "female": 800,
            "unit": "мг",
            "name": "Фосфор (P)"
        },
        "magnesium": {  # мг
            "male": 400,
            "female": 400,
            "unit": "мг",
            "name": "Магний (Mg)"
        },
        "potassium": {  # мг
            "male": 3500,
            "female": 3500,
            "unit": "мг",
            "name": "Калий (K)"
        },
        "sodium": {  # мг
            "male": 1300,
            "female": 1300,
            "unit": "мг",
            "name": "Натрий (Na)"
        },
        "chloride": {  # мг
            "male": 2300,
            "female": 2300,
            "unit": "мг",
            "name": "Хлор (Cl)"
        },
        "iron": {  # мг
            "male": 10,
            "female": 18,  # Выше для женщин
            "unit": "мг",
            "name": "Железо (Fe)"
        },
        "zinc": {  # мг
            "male": 12,
            "female": 12,
            "unit": "мг",
            "name": "Цинк (Zn)"
        },
        "iodine": {  # мкг
            "male": 150,
            "female": 150,
            "unit": "мкг",
            "name": "Йод (I)"
        },
        "selenium": {  # мкг
            "male": 70,
            "female": 55,
            "unit": "мкг",
            "name": "Селен (Se)"
        },
        "copper": {  # мг
            "male": 1,
            "female": 1,
            "unit": "мг",
            "name": "Медь (Cu)"
        },
        "manganese": {  # мг
            "male": 2.3,
            "female": 1.8,
            "unit": "мг",
            "name": "Марганец (Mn)"
        },
        "chromium": {  # мкг
            "male": 50,
            "female": 50,
            "unit": "мкг",
            "name": "Хром (Cr)"
        },
        "fluoride": {  # мг
            "male": 4,
            "female": 3,
            "unit": "мг",
            "name": "Фтор (F)"
        },
        "cobalt": {  # мкг
            "male": 10,
            "female": 10,
            "unit": "мкг",
            "name": "Кобальт (Co)"
        },
        "silicon": {  # мг
            "male": 30,
            "female": 30,
            "unit": "мг",
            "name": "Кремний (Si)"
        },
    }

    @classmethod
    def get_daily_target(cls, nutrient_name: str, gender: str = "male") -> float:
        """
        Получить целевое суточное значение микронутриента

        Args:
            nutrient_name: Название микронутриента (например, "vitamin_c")
            gender: Пол ("male" или "female")

        Returns:
            Целевое значение в соответствующих единицах
        """
        if nutrient_name in cls.DAILY_TARGETS:
            return cls.DAILY_TARGETS[nutrient_name].get(gender, cls.DAILY_TARGETS[nutrient_name]["male"])
        return 0

    @classmethod
    def get_all_targets(cls, gender: str = "male") -> dict:
        """
        Получить все целевые значения для пола

        Args:
            gender: Пол ("male" или "female")

        Returns:
            Словарь с целевыми значениями
        """
        targets = {}
        for nutrient, data in cls.DAILY_TARGETS.items():
            targets[nutrient] = {
                "target": data.get(gender, data["male"]),
                "unit": data["unit"],
                "name": data["name"]
            }
        return targets
