"""
Сервис шифрования медицинских данных (152-ФЗ)

Использует симметричное шифрование (Fernet) для защиты
чувствительных персональных данных о здоровье
"""

import os
import json
import logging
from cryptography.fernet import Fernet
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EncryptionService:
    """Сервис для шифрования/дешифрования медицинских данных"""

    def __init__(self):
        """Инициализация сервиса с ключом шифрования"""
        # Получаем ключ из переменных окружения
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            logger.warning(
                "ENCRYPTION_KEY not found in environment variables! "
                "Generating a new key..."
            )
            encryption_key = Fernet.generate_key().decode()
            logger.warning(
                f"Generated encryption key: {encryption_key}\n"
                "IMPORTANT: Save this key to .env file as ENCRYPTION_KEY!"
            )

        # Создаем Fernet cipher
        try:
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            self.cipher = Fernet(encryption_key)
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise ValueError("Invalid encryption key")

    def encrypt(self, data: Any) -> Optional[bytes]:
        """
        Шифрует данные

        Args:
            data: Данные для шифрования (str, list, dict)

        Returns:
            Зашифрованные байты или None при ошибке
        """
        if data is None:
            return None

        try:
            # Конвертируем в JSON строку
            if isinstance(data, (list, dict)):
                json_string = json.dumps(data, ensure_ascii=False)
            else:
                json_string = str(data)

            # Шифруем
            encrypted = self.cipher.encrypt(json_string.encode('utf-8'))
            return encrypted

        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return None

    def decrypt(self, encrypted_data: Optional[bytes]) -> Any:
        """
        Дешифрует данные

        Args:
            encrypted_data: Зашифрованные байты

        Returns:
            Расшифрованные данные (str, list, dict) или None при ошибке
        """
        if not encrypted_data:
            return None

        try:
            # Дешифруем
            decrypted_bytes = self.cipher.decrypt(encrypted_data)
            decrypted_string = decrypted_bytes.decode('utf-8')

            # Пытаемся распарсить как JSON
            try:
                return json.loads(decrypted_string)
            except json.JSONDecodeError:
                # Если не JSON, возвращаем строку
                return decrypted_string

        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None

    def encrypt_str(self, text: str) -> Optional[bytes]:
        """Шифрует строку"""
        if not text:
            return None
        return self.encrypt(text)

    def decrypt_str(self, encrypted_data: Optional[bytes]) -> Optional[str]:
        """Дешифрует в строку"""
        if not encrypted_data:
            return None
        result = self.decrypt(encrypted_data)
        return str(result) if result is not None else None

    def encrypt_list(self, items: list) -> Optional[bytes]:
        """Шифрует список"""
        if not items:
            return None
        return self.encrypt(items)

    def decrypt_list(self, encrypted_data: Optional[bytes]) -> Optional[list]:
        """Дешифрует в список"""
        if not encrypted_data:
            return None
        result = self.decrypt(encrypted_data)
        return result if isinstance(result, list) else None

    def encrypt_dict(self, data: dict) -> Optional[bytes]:
        """Шифрует словарь"""
        if not data:
            return None
        return self.encrypt(data)

    def decrypt_dict(self, encrypted_data: Optional[bytes]) -> Optional[dict]:
        """Дешифрует в словарь"""
        if not encrypted_data:
            return None
        result = self.decrypt(encrypted_data)
        return result if isinstance(result, dict) else None


# Глобальный экземпляр сервиса
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Получить глобальный экземпляр сервиса шифрования"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


# Вспомогательные функции для удобства
def encrypt_data(data: Any) -> Optional[bytes]:
    """Быстрое шифрование данных"""
    return get_encryption_service().encrypt(data)


def decrypt_data(encrypted_data: Optional[bytes]) -> Any:
    """Быстрое дешифрование данных"""
    return get_encryption_service().decrypt(encrypted_data)
