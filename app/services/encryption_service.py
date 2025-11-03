"""
Сервис шифрования персональных данных (152-ФЗ)

Использует симметричное шифрование (Fernet) для защиты
всех персональных данных пользователей
"""

import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Any, Optional, List
from loguru import logger


class EncryptionService:
    """Сервис для шифрования/дешифрования персональных данных"""

    _cipher: Optional[Fernet] = None

    @classmethod
    def _get_cipher(cls) -> Fernet:
        """Получить экземпляр Fernet cipher"""
        if cls._cipher is None:
            # Получаем ключ из переменных окружения или генерируем из SECRET_KEY
            encryption_key = os.getenv("ENCRYPTION_KEY")

            if not encryption_key:
                # Используем SECRET_KEY из settings
                from app.config import settings

                logger.info("ENCRYPTION_KEY not found, deriving from SECRET_KEY using PBKDF2HMAC")

                # Генерируем ключ из SECRET_KEY используя PBKDF2HMAC
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'nutriai_encryption_salt_v1',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
                cls._cipher = Fernet(key)
            else:
                # Используем предоставленный ключ
                if isinstance(encryption_key, str):
                    encryption_key = encryption_key.encode()
                cls._cipher = Fernet(encryption_key)

        return cls._cipher

    @classmethod
    def encrypt_string(cls, value: Optional[str]) -> Optional[str]:
        """
        Зашифровать строку

        Args:
            value: Строка для шифрования

        Returns:
            Зашифрованная строка (base64) или None
        """
        if value is None or value == "":
            return None

        try:
            cipher = cls._get_cipher()
            encrypted_bytes = cipher.encrypt(value.encode('utf-8'))
            # Возвращаем как строку (base64)
            return encrypted_bytes.decode('ascii')
        except Exception as e:
            logger.error(f"Encryption error: {repr(e)}")
            raise

    @classmethod
    def decrypt_string(cls, encrypted_value: Optional[str]) -> Optional[str]:
        """
        Расшифровать строку

        Args:
            encrypted_value: Зашифрованная строка (base64)

        Returns:
            Расшифрованная строка или None
        """
        if encrypted_value is None or encrypted_value == "":
            return None

        try:
            cipher = cls._get_cipher()
            # Конвертируем из строки в bytes
            decrypted_bytes = cipher.decrypt(encrypted_value.encode('ascii'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.warning(f"Decryption error (possibly unencrypted data): {repr(e)}")
            # Возвращаем None при ошибке (данные могут быть не зашифрованы)
            return None

    @classmethod
    def encrypt_int(cls, value: Optional[int]) -> Optional[str]:
        """Зашифровать целое число"""
        if value is None:
            return None
        return cls.encrypt_string(str(value))

    @classmethod
    def decrypt_int(cls, encrypted_value: Optional[str]) -> Optional[int]:
        """Расшифровать целое число"""
        if encrypted_value is None:
            return None

        decrypted_str = cls.decrypt_string(encrypted_value)
        if decrypted_str is None:
            return None

        try:
            return int(decrypted_str)
        except ValueError:
            logger.error(f"Failed to convert to int: {decrypted_str}")
            return None

    @classmethod
    def encrypt_float(cls, value: Optional[float]) -> Optional[str]:
        """Зашифровать число с плавающей точкой"""
        if value is None:
            return None
        return cls.encrypt_string(str(value))

    @classmethod
    def decrypt_float(cls, encrypted_value: Optional[str]) -> Optional[float]:
        """Расшифровать число с плавающей точкой"""
        if encrypted_value is None:
            return None

        decrypted_str = cls.decrypt_string(encrypted_value)
        if decrypted_str is None:
            return None

        try:
            return float(decrypted_str)
        except ValueError:
            logger.error(f"Failed to convert to float: {decrypted_str}")
            return None

    @classmethod
    def encrypt_list(cls, value: Optional[List[Any]]) -> Optional[str]:
        """Зашифровать список"""
        if value is None or len(value) == 0:
            return None

        json_str = json.dumps(value, ensure_ascii=False)
        return cls.encrypt_string(json_str)

    @classmethod
    def decrypt_list(cls, encrypted_value: Optional[str]) -> Optional[List[Any]]:
        """Расшифровать список"""
        if encrypted_value is None:
            return None

        decrypted_str = cls.decrypt_string(encrypted_value)
        if decrypted_str is None:
            return None

        try:
            return json.loads(decrypted_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON: {decrypted_str}")
            return None
