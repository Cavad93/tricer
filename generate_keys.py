#!/usr/bin/env python3
"""
Генератор безопасных ключей для шифрования персональных данных

Использование:
    python generate_keys.py
"""
import secrets
import base64


def generate_secret_key(length: int = 64) -> str:
    """Генерация безопасного SECRET_KEY"""
    return secrets.token_urlsafe(length)


def generate_encryption_key() -> str:
    """Генерация ключа Fernet для шифрования"""
    # Генерируем 32 байта (256 бит) случайных данных
    key = secrets.token_bytes(32)
    # Кодируем в base64 URL-safe формат (как Fernet)
    return base64.urlsafe_b64encode(key).decode()


if __name__ == "__main__":
    print("=" * 70)
    print("🔐 ГЕНЕРАТОР КЛЮЧЕЙ ШИФРОВАНИЯ")
    print("=" * 70)
    print()

    # Генерируем SECRET_KEY
    secret_key = generate_secret_key()
    print("1️⃣  SECRET_KEY (для JWT токенов и общей безопасности):")
    print(f"   {secret_key}")
    print()

    # Генерируем ENCRYPTION_KEY
    encryption_key = generate_encryption_key()
    print("2️⃣  ENCRYPTION_KEY (для шифрования персональных данных):")
    print(f"   {encryption_key}")
    print()

    print("=" * 70)
    print("📝 КАК ИСПОЛЬЗОВАТЬ:")
    print("=" * 70)
    print()
    print("ВАРИАНТ 1 (Рекомендуется - максимальная безопасность):")
    print("-" * 70)
    print("Скопируйте ОБА ключа в файл .env:")
    print()
    print(f"SECRET_KEY={secret_key}")
    print(f"ENCRYPTION_KEY={encryption_key}")
    print()
    print("✅ Используется отдельный ключ для шифрования данных")
    print()

    print("ВАРИАНТ 2 (Упрощенный - один ключ для всего):")
    print("-" * 70)
    print("Скопируйте ТОЛЬКО SECRET_KEY в файл .env:")
    print()
    print(f"SECRET_KEY={secret_key}")
    print("# ENCRYPTION_KEY не указан - будет использован SECRET_KEY через PBKDF2")
    print()
    print("✅ Ключ для шифрования будет автоматически сгенерирован из SECRET_KEY")
    print("✅ Достаточно безопасно для большинства случаев")
    print()

    print("=" * 70)
    print("⚠️  ВАЖНО:")
    print("=" * 70)
    print("• Храните эти ключи в СЕКРЕТЕ!")
    print("• НЕ коммитьте файл .env в git!")
    print("• Если потеряете ключи - зашифрованные данные НЕВОЗМОЖНО восстановить!")
    print("• Сделайте резервную копию ключей в безопасном месте")
    print()
    print("=" * 70)
