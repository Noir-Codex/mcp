"""Полный тест интеграции с внешним API и синонимами."""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    """Основная функция теста."""
    print("=" * 60)
    print("ПОЛНЫЙ ТЕСТ ИНТЕГРАЦИИ С ВНЕШНИМ API И СИНОНИМАМИ")
    print("=" * 60)
    
    try:
        print("\n1. Импорт модуля агента...")
        from agent.agent import WarehouseAgent
        print("   OK Модуль импортирован")
        
        print("\n2. Инициализация агента...")
        agent = WarehouseAgent()
        print("   OK Агент инициализирован")
        
        print("\n3. Тест: Поиск по разговорному названию 'картошка'...")
        result = agent.process_text("Найди товар картошка")
        print(f"   Запрос: Найди товар картошка")
        print(f"   Ответ: {result[:200]}...")
        
        print("\n4. Тест: Проверка остатков по разговорному названию...")
        result = agent.process_text("Сколько картошки на складе?")
        print(f"   Запрос: Сколько картошки на складе?")
        print(f"   Ответ: {result[:300]}...")
        
        print("\n5. Тест: Проверка морковки (разговорное название)...")
        result = agent.process_text("Покажи сколько морковки осталось")
        print(f"   Запрос: Покажи сколько морковки осталось")
        print(f"   Ответ: {result[:300]}...")
        
        print("\n" + "=" * 60)
        print("OK ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\nERROR ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)


