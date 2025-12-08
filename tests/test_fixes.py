"""Тест исправлений: единицы измерения и статус заявок."""

import httpx
import json

print("=" * 60)
print("ТЕСТ ИСПРАВЛЕНИЙ")
print("=" * 60)

# Тест 1: Единицы измерения
print("\n[1] Тест единиц измерения...")
try:
    r = httpx.post(
        'http://localhost:8000/mcp/tools/get_inventory_status',
        json={'product_sku': 'KART-001'},
        timeout=3
    )
    if r.status_code == 200:
        data = r.json()
        unit = data.get('unit', 'не указана')
        print(f"✓ Статус: {r.status_code}")
        print(f"✓ Единица измерения: {unit}")
        print(f"✓ Товар: {data.get('product_name')}, Количество: {data.get('current_quantity')} {unit}")
    else:
        print(f"✗ Ошибка: {r.status_code} - {r.text}")
except Exception as e:
    print(f"✗ Ошибка: {str(e)}")

# Тест 2: Статус заявки (если заявка существует)
print("\n[2] Тест статуса заявки...")
try:
    # Сначала создадим заявку
    r = httpx.post(
        'http://localhost:8000/mcp/tools/create_reorder_request',
        json={
            'product_sku': 'MORK-001',
            'requested_quantity': 30,
            'priority': 'medium'
        },
        timeout=3
    )
    if r.status_code == 200:
        request_data = r.json()
        request_id = request_data.get('request_id')
        print(f"✓ Заявка создана: {request_id}")
        
        # Теперь получим статус
        r2 = httpx.post(
            'http://localhost:8000/mcp/tools/get_reorder_status',
            json={'request_id': request_id},
            timeout=3
        )
        if r2.status_code == 200:
            status_data = r2.json()
            print(f"✓ Статус заявки получен: {r2.status_code}")
            print(f"✓ ID заявки: {status_data.get('request_id')}")
            print(f"✓ Товар: {status_data.get('product_name')}")
            print(f"✓ Количество: {status_data.get('requested_quantity')}")
            print(f"✓ Статус: {status_data.get('status')}")
        else:
            print(f"✗ Ошибка получения статуса: {r2.status_code} - {r2.text}")
    else:
        print(f"✗ Ошибка создания заявки: {r.status_code} - {r.text}")
except Exception as e:
    print(f"✗ Ошибка: {str(e)}")

print("\n" + "=" * 60)
print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 60)


