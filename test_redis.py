"""
Проверка подключения к Redis
"""
import redis

try:
    # Подключаемся к Redis
    r = redis.from_url('redis://localhost:6379/0')

    # Проверяем связь
    if r.ping():
        print("✅ Redis работает!")

        # Получаем информацию
        info = r.info("server")
        print(f"✅ Версия Redis: {info['redis_version']}")
        print(f"✅ Порт: {info['tcp_port']}")
        print(f"✅ Uptime: {info['uptime_in_seconds']} секунд")

        # Тестируем операции
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        print(f"✅ Тест записи/чтения: OK")
        r.delete('test_key')

        print("\n🎉 Redis полностью работоспособен!")
    else:
        print("❌ Redis не отвечает")

except redis.ConnectionError as e:
    print(f"❌ Ошибка подключения к Redis: {e}")
    print("\nПроверьте:")
    print("  1. Запущен ли процесс redis-server.exe")
    print("  2. Доступен ли порт 6379")
    print("  3. Настройки брандмауэра Windows")

except Exception as e:
    print(f"❌ Неожиданная ошибка: {e}")
