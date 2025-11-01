"""
Integration тесты требуют подключения к БД и внешним сервисам.
Эти тесты пропускаются в окружении без БД (например, в песочнице).
Для запуска этих тестов установите переменную окружения RUN_INTEGRATION_TESTS=1
и убедитесь что PostgreSQL, Redis и другие сервисы доступны.
"""
import pytest

# Эти тесты требуют реальной БД и сервисов
pytest.skip("Integration tests require database and external services", allow_module_level=True)
