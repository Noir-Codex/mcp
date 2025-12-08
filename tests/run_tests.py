"""Основной скрипт для запуска всех тестов."""

import sys
import os

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_all_tests():
    """Запуск всех тестов."""
    print("=" * 60)
    print("ЗАПУСК ВСЕХ ТЕСТОВ")
    print("=" * 60)
    
    test_files = [
        "test_integration",
        "test_system",
        "test_mcp_server",
        "test_agent_simple",
        "test_agent_with_names",
        "test_api_key",
        "test_fixes",
        "test_full_integration",
    ]
    
    results = {}
    
    for test_module in test_files:
        print(f"\n{'='*60}")
        print(f"Запуск: {test_module}")
        print('='*60)
        try:
            module = __import__(test_module)
            if hasattr(module, 'main'):
                module.main()
                results[test_module] = True
            else:
                print(f"⚠ {test_module} не имеет функции main()")
                results[test_module] = None
        except Exception as e:
            print(f"✗ Ошибка при запуске {test_module}: {str(e)}")
            results[test_module] = False
    
    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    print(f"Пройдено: {passed}")
    print(f"Провалено: {failed}")
    print(f"Пропущено: {skipped}")
    print(f"Всего: {len(results)}")
    
    if failed == 0:
        print("\n✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        print(f"\n✗ {failed} ТЕСТОВ ПРОВАЛЕНО")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

