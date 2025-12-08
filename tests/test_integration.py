"""Скрипт для проверки интеграции всех компонентов системы."""

import os
import sys
import json
import asyncio
from dotenv import load_dotenv
import httpx

# Загрузка переменных окружения
load_dotenv()

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_success(message):
    """Вывод успешного сообщения."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_error(message):
    """Вывод сообщения об ошибке."""
    print(f"{RED}✗ {message}{RESET}")


def print_info(message):
    """Вывод информационного сообщения."""
    print(f"{BLUE}ℹ {message}{RESET}")


def print_warning(message):
    """Вывод предупреждения."""
    print(f"{YELLOW}⚠ {message}{RESET}")


def test_env_variables():
    """Проверка переменных окружения."""
    print("\n" + "="*60)
    print("1. ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
    print("="*60)
    
    required_vars = {
        "EVOLUTION_API_KEY": os.getenv("EVOLUTION_API_KEY"),
        "EVOLUTION_API_URL": os.getenv("EVOLUTION_API_URL", "https://foundation-models.api.cloud.ru/v1"),
        "EVOLUTION_MODEL": os.getenv("EVOLUTION_MODEL", "DeepSeek-R1-Distill-Llama-70B"),
        "MCP_SERVER_URL": os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
    }
    
    all_ok = True
    for var_name, var_value in required_vars.items():
        if var_value:
            print_success(f"{var_name}: установлена")
            if var_name == "EVOLUTION_API_KEY":
                # Показываем только первые и последние символы ключа
                masked_key = var_value[:10] + "..." + var_value[-10:] if len(var_value) > 20 else "***"
                print_info(f"  Значение: {masked_key}")
        else:
            print_error(f"{var_name}: не установлена")
            all_ok = False
    
    return all_ok


def test_evolution_api():
    """Проверка подключения к Evolution Foundation Models API."""
    print("\n" + "="*60)
    print("2. ПРОВЕРКА EVOLUTION FOUNDATION MODELS API")
    print("="*60)
    
    api_key = os.getenv("EVOLUTION_API_KEY")
    api_url = os.getenv("EVOLUTION_API_URL", "https://foundation-models.api.cloud.ru/v1")
    model = os.getenv("EVOLUTION_MODEL", "DeepSeek-R1-Distill-Llama-70B")
    
    if not api_key:
        print_error("EVOLUTION_API_KEY не установлен")
        return False
    
    try:
        print_info(f"Подключение к: {api_url}")
        print_info(f"Модель: {model}")
        
        # Cloud.ru использует OpenAI-совместимый API
        # Аутентификация через заголовок Authorization с Bearer токеном
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Привет! Ответь одним словом: 'Работает'"}
            ],
            "max_tokens": 10
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{api_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                print_success(f"API отвечает корректно")
                print_info(f"Ответ модели: {content.strip()}")
                return True
            else:
                print_error(f"Ошибка API: {response.status_code}")
                print_error(f"Ответ: {response.text}")
                return False
                
    except httpx.TimeoutException:
        print_error("Таймаут при подключении к API")
        return False
    except httpx.ConnectError:
        print_error("Не удалось подключиться к API (проверьте интернет-соединение)")
        return False
    except Exception as e:
        print_error(f"Ошибка при проверке API: {str(e)}")
        return False


def test_mcp_server():
    """Проверка доступности MCP-сервера."""
    print("\n" + "="*60)
    print("3. ПРОВЕРКА MCP-СЕРВЕРА")
    print("="*60)
    
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    
    try:
        print_info(f"Проверка доступности: {mcp_url}")
        
        # Проверка health endpoint (если есть)
        with httpx.Client(timeout=5.0) as client:
            try:
                response = client.get(f"{mcp_url}/health")
                if response.status_code == 200:
                    print_success("MCP-сервер доступен (health check)")
                    return True
            except:
                pass
            
            # Проверка через вызов инструмента
            print_info("Проверка через вызов инструмента...")
            response = client.post(
                f"{mcp_url}/mcp/tools/get_inventory_status",
                json={"product_sku": "ABC123"},
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print_success("MCP-сервер отвечает корректно")
                print_info(f"Ответ: {json.dumps(result, ensure_ascii=False, indent=2)[:100]}...")
                return True
            else:
                print_warning(f"MCP-сервер вернул код: {response.status_code}")
                print_warning("Убедитесь, что MCP-сервер запущен: python -m mcp_server.server")
                return False
                
    except httpx.ConnectError:
        print_error("MCP-сервер недоступен")
        print_warning("Запустите MCP-сервер: python -m mcp_server.server")
        return False
    except httpx.TimeoutException:
        print_error("Таймаут при подключении к MCP-серверу")
        return False
    except Exception as e:
        print_error(f"Ошибка при проверке MCP-сервера: {str(e)}")
        return False


def test_agent_initialization():
    """Проверка инициализации агента."""
    print("\n" + "="*60)
    print("4. ПРОВЕРКА ИНИЦИАЛИЗАЦИИ АГЕНТА")
    print("="*60)
    
    try:
        print_info("Импорт модуля агента...")
        from agent.agent import WarehouseAgent
        
        print_info("Инициализация агента...")
        agent = WarehouseAgent()
        
        print_success("Агент успешно инициализирован")
        print_info(f"Количество инструментов: {len(agent.tools)}")
        print_info(f"Инструменты: {[tool.name for tool in agent.tools]}")
        
        return True
        
    except ImportError as e:
        print_error(f"Ошибка импорта: {str(e)}")
        print_warning("Установите зависимости: pip install -r requirements.txt")
        return False
    except ValueError as e:
        print_error(f"Ошибка инициализации: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Неожиданная ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_a2a_format():
    """Проверка формата ответа A2A."""
    print("\n" + "="*60)
    print("5. ПРОВЕРКА ФОРМАТА ОТВЕТА A2A")
    print("="*60)
    
    try:
        from agent.agent import WarehouseAgent
        
        print_info("Инициализация агента...")
        agent = WarehouseAgent()
        
        print_info("Тестовый запрос (без вызова MCP)...")
        # Простой запрос, который не требует вызова инструментов
        test_query = "Привет! Как дела?"
        
        result = agent.process(test_query)
        
        # Проверка структуры ответа
        required_fields = ["response", "tools_used", "metadata"]
        all_fields_present = all(field in result for field in required_fields)
        
        if all_fields_present:
            print_success("Формат ответа A2A корректен")
            print_info(f"Поля ответа: {list(result.keys())}")
            print_info(f"Использованные инструменты: {result['tools_used']}")
            print_info(f"Статус: {result['metadata'].get('status', 'unknown')}")
            return True
        else:
            missing = [f for f in required_fields if f not in result]
            print_error(f"Отсутствуют обязательные поля: {missing}")
            return False
            
    except Exception as e:
        print_error(f"Ошибка при проверке формата A2A: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция проверки."""
    print("\n" + "="*60)
    print("ПРОВЕРКА ИНТЕГРАЦИИ СИСТЕМЫ")
    print("="*60)
    
    results = {
        "Переменные окружения": test_env_variables(),
        "Evolution API": test_evolution_api(),
        "MCP-сервер": test_mcp_server(),
        "Инициализация агента": test_agent_initialization(),
        "Формат A2A": test_agent_a2a_format(),
    }
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ПРОВЕРКИ")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name}: ПРОЙДЕН")
        else:
            print_error(f"{test_name}: НЕ ПРОЙДЕН")
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print_success("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print_error("НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ")
        print_warning("Исправьте ошибки и запустите проверку снова")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

