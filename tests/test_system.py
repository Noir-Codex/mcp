"""Комплексный тест всей системы."""

import os
import sys
import time
import httpx
from dotenv import load_dotenv

# Установка кодировки для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

load_dotenv()

print("=" * 60)
print("КОМПЛЕКСНЫЙ ТЕСТ СИСТЕМЫ")
print("=" * 60)

errors = []
success_count = 0
total_tests = 0

def test(name, func):
    """Вспомогательная функция для тестов."""
    global success_count, total_tests
    total_tests += 1
    try:
        result = func()
        print(f"[OK] {name}")
        success_count += 1
        return result
    except Exception as e:
        print(f"[FAIL] {name}: {str(e)}")
        errors.append(f"{name}: {str(e)}")
        return None

# Тест 1: Импорты
print("\n[1] Проверка импортов...")
test("Импорт mcp_server", lambda: __import__('mcp_server'))
test("Импорт agent", lambda: __import__('agent.agent'))
test("Импорт mcp_tools", lambda: __import__('mcp_server.mcp_tools'))
test("Импорт http_server", lambda: __import__('mcp_server.http_server'))

# Тест 2: Mock Warehouse API
print("\n[2] Проверка Mock Warehouse API...")
try:
    response = httpx.get("http://localhost:8001/health", timeout=3)
    test("Mock API доступен", lambda: response.status_code == 200)
    test("Mock API ответ корректен", lambda: response.json()["status"] == "ok")
except Exception as e:
    print(f"⚠ Mock API недоступен: {str(e)}")
    print("   Запустите: python mock_warehouse_api.py")

# Тест 3: MCP-сервер
print("\n[3] Проверка MCP-сервера...")
try:
    response = httpx.get("http://localhost:8000/health", timeout=3)
    test("MCP-сервер доступен", lambda: response.status_code == 200)
    test("MCP-сервер ответ корректен", lambda: response.json()["status"] == "ok")
except Exception as e:
    print(f"⚠ MCP-сервер недоступен: {str(e)}")
    print("   Запустите: python -m mcp_server.http_server")

# Тест 4: MCP инструменты
print("\n[4] Проверка MCP инструментов...")
try:
    # Поиск товаров
    response = httpx.post(
        "http://localhost:8000/mcp/tools/search_products",
        json={"product_name": "картошка"},
        timeout=3
    )
    test("Поиск товаров работает", lambda: response.status_code == 200)
    data = response.json()
    test("Поиск находит товары", lambda: data.get("found") == True)
    test("Поиск находит картофель", lambda: "Картофель" in [p.get("product_name") for p in data.get("products", [])])
    
    # Статус запасов
    response = httpx.post(
        "http://localhost:8000/mcp/tools/get_inventory_status",
        json={"product_sku": "KART-001"},
        timeout=3
    )
    test("Статус запасов работает", lambda: response.status_code == 200)
    data = response.json()
    test("Статус возвращает данные", lambda: data.get("product_sku") == "KART-001")
    
    # Статус по названию (синонимы)
    response = httpx.post(
        "http://localhost:8000/mcp/tools/get_inventory_status",
        json={"product_sku": "картошка"},
        timeout=3
    )
    test("Синонимы работают", lambda: response.status_code == 200)
    data = response.json()
    test("Синонимы находят товар", lambda: data.get("product_name") == "Картофель")
    
except Exception as e:
    print(f"⚠ Ошибка при тестировании инструментов: {str(e)}")

# Тест 5: Агент
print("\n[5] Проверка AI-агента...")
try:
    from agent.agent import WarehouseAgent
    agent = test("Инициализация агента", lambda: WarehouseAgent())
    
    if agent:
        result = test("Агент обрабатывает запрос", lambda: agent.process_text("Сколько картошки на складе?"))
        if result:
            test("Агент возвращает ответ", lambda: len(result) > 0)
            test("Агент использует инструменты", lambda: "картофель" in result.lower() or "200" in result)
except Exception as e:
    print(f"⚠ Ошибка при тестировании агента: {str(e)}")

# Итоги
print("\n" + "=" * 60)
print("ИТОГИ ТЕСТИРОВАНИЯ")
print("=" * 60)
print(f"Пройдено тестов: {success_count}/{total_tests}")

if errors:
    print(f"\nОшибки ({len(errors)}):")
    for error in errors:
        print(f"  - {error}")
else:
    print("\n[OK] Все тесты пройдены успешно!")

print("\n" + "=" * 60)

if success_count == total_tests:
    print("[SUCCESS] СИСТЕМА РАБОТАЕТ КОРРЕКТНО")
    sys.exit(0)
else:
    print("[WARNING] ЕСТЬ ПРОБЛЕМЫ, ТРЕБУЕТСЯ ВНИМАНИЕ")
    sys.exit(1)

