"""Тест агента с поиском товаров по названию."""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("ТЕСТ АГЕНТА С ПОИСКОМ ТОВАРОВ ПО НАЗВАНИЮ")
print("=" * 60)

try:
    print("\n1. Импорт модуля агента...")
    from agent.agent import WarehouseAgent
    print("   ✓ Модуль импортирован")
    
    print("\n2. Инициализация агента...")
    agent = WarehouseAgent()
    print("   ✓ Агент инициализирован")
    
    print("\n3. Тест: Поиск товара по названию...")
    result = agent.process_text("Найди товар морковь")
    print(f"   Запрос: Найди товар морковь")
    print(f"   Ответ: {result[:300]}...")
    
    print("\n4. Тест: Проверка остатков по названию...")
    result = agent.process_text("Сколько осталось морковки на складе?")
    print(f"   Запрос: Сколько осталось морковки на складе?")
    print(f"   Ответ: {result[:300]}...")
    
    print("\n5. Тест: Проверка нескольких товаров...")
    result = agent.process_text("Проверь сколько осталось морковки и картошки на складе")
    print(f"   Запрос: Проверь сколько осталось морковки и картошки на складе")
    print(f"   Ответ: {result[:400]}...")
    
    print("\n" + "=" * 60)
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ ОШИБКА: {str(e)}")
    import traceback
    traceback.print_exc()


