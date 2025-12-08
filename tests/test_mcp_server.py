"""Тестовый скрипт для проверки работы MCP-сервера."""

import httpx
import json

MCP_SERVER_URL = "http://localhost:8000"


def test_get_inventory_status():
    """Тест получения статуса запасов."""
    print("Тест: get_inventory_status")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{MCP_SERVER_URL}/mcp/tools/get_inventory_status",
                json={"product_sku": "ABC123"}
            )
            response.raise_for_status()
            result = response.json()
            print(f"✓ Успешно: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return True
    except Exception as e:
        print(f"✗ Ошибка: {str(e)}")
        return False


def test_update_inventory():
    """Тест обновления запасов."""
    print("\nТест: update_inventory")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{MCP_SERVER_URL}/mcp/tools/update_inventory",
                json={
                    "product_sku": "ABC123",
                    "quantity_change": 50,
                    "operation_type": "incoming"
                }
            )
            response.raise_for_status()
            result = response.json()
            print(f"✓ Успешно: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return True
    except Exception as e:
        print(f"✗ Ошибка: {str(e)}")
        return False


def test_create_reorder_request():
    """Тест создания заявки на пополнение."""
    print("\nТест: create_reorder_request")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{MCP_SERVER_URL}/mcp/tools/create_reorder_request",
                json={
                    "product_sku": "XYZ789",
                    "requested_quantity": 100,
                    "priority": "high"
                }
            )
            response.raise_for_status()
            result = response.json()
            print(f"✓ Успешно: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return True
    except Exception as e:
        print(f"✗ Ошибка: {str(e)}")
        return False


def main():
    """Запуск всех тестов."""
    print("=" * 50)
    print("Тестирование MCP-сервера управления складом")
    print("=" * 50)
    
    results = []
    results.append(test_get_inventory_status())
    results.append(test_update_inventory())
    results.append(test_create_reorder_request())
    
    print("\n" + "=" * 50)
    print(f"Результаты: {sum(results)}/{len(results)} тестов пройдено")
    print("=" * 50)


if __name__ == "__main__":
    main()

