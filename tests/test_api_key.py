"""Тест API ключа с разными форматами аутентификации."""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def main():
    """Основная функция теста."""
    api_key = os.getenv("EVOLUTION_API_KEY") or os.getenv("API_KEY")
    url = "https://foundation-models.api.cloud.ru/v1"
    
    print(f"API Key (первые 20 символов): {api_key[:20] if api_key else 'НЕ УСТАНОВЛЕН'}...")
    print(f"URL: {url}")
    print()
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=url
        )
        
        print("Попытка подключения к API...")
        response = client.chat.completions.create(
            model="Qwen/Qwen3-235B-A22B-Instruct-2507",
            max_tokens=100,
            temperature=0.5,
            presence_penalty=0,
            top_p=0.95,
            messages=[
                {
                    "role": "user",
                    "content": "Привет! Ответь одним словом."
                }
            ]
        )
        
        print("OK УСПЕХ!")
        print(f"Ответ: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"ERROR ОШИБКА: {str(e)}")
        print()
        print("Возможные причины:")
        print("1. API ключ неверный или истек")
        print("2. API ключ имеет неправильный формат")
        print("3. Нужна другая форма аутентификации")
        print()
        print("Проверьте:")
        print("- Что ключ скопирован полностью (включая точку)")
        print("- Что ключ получен для сервиса 'Foundation Models'")
        print("- Что ключ не истек")
        return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)


