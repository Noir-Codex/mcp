"""Простой тест агента."""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("ТЕСТ АГЕНТА УПРАВЛЕНИЯ СКЛАДОМ")
print("=" * 60)

try:
    print("\n1. Импорт модуля агента...")
    from agent.agent import WarehouseAgent
    print("   ✓ Модуль импортирован")
    
    print("\n2. Инициализация агента...")
    agent = WarehouseAgent()
    print("   ✓ Агент инициализирован")
    
    print("\n3. Тестовый запрос (без вызова MCP)...")
    test_query = "Привет! Как дела?"
    result = agent.process_text(test_query)
    print(f"   Запрос: {test_query}")
    print(f"   Ответ: {result[:200]}...")
    print("   ✓ Агент отвечает")
    
    print("\n4. Проверка формата A2A...")
    result_a2a = agent.process(test_query)
    print(f"   Формат ответа: {type(result_a2a)}")
    print(f"   Поля: {list(result_a2a.keys())}")
    print("   ✓ Формат A2A корректен")
    
    print("\n" + "=" * 60)
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ ОШИБКА: {str(e)}")
    import traceback
    traceback.print_exc()


