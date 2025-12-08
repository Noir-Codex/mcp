"""AI-Агент для управления складом и запасами с интеграцией Evolution Foundation Models."""

import os
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.tools import Tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_community.chat_message_histories import ChatMessageHistory
import httpx

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Конфигурация
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY") or os.getenv("API_KEY")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://foundation-models.api.cloud.ru/v1")
EVOLUTION_MODEL = os.getenv("EVOLUTION_MODEL", "Qwen/Qwen3-235B-A22B-Instruct-2507")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")


class MCPTool:
    """Обертка для вызова инструментов MCP-сервера."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
    
    def call_tool_sync(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Синхронный вызов инструмента MCP-сервера."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.server_url}/mcp/tools/{tool_name}",
                    json=params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка при вызове MCP инструмента {tool_name}: {str(e)}")
            raise
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Асинхронный вызов инструмента MCP-сервера."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/mcp/tools/{tool_name}",
                    json=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка при вызове MCP инструмента {tool_name}: {str(e)}")
            raise


class WarehouseAgent:
    """AI-Агент для управления складом и запасами."""
    
    def __init__(self):
        """Инициализация агента."""
        if not EVOLUTION_API_KEY:
            raise ValueError("EVOLUTION_API_KEY должен быть установлен в переменных окружения")
        
        # Инициализация OpenAI клиента для Evolution Foundation Models
        self.client = OpenAI(
            api_key=EVOLUTION_API_KEY,
            base_url=EVOLUTION_API_URL,
            timeout=60.0,  # Увеличенный таймаут для стабильности
            max_retries=3  # Количество повторных попыток
        )
        
        # Инициализация MCP клиента
        self.mcp_client = MCPTool(MCP_SERVER_URL)
        
        # Создание инструментов
        self.tools = self._create_tools()
        
        # Инициализация памяти разговора
        self.chat_history = ChatMessageHistory()
        
        # Системный промпт
        self.system_prompt = (
            "Ты - AI-ассистент для управления складом и запасами. "
            "Твоя задача - помогать пользователям управлять складскими запасами, "
            "отслеживать состояние товаров, создавать и удалять товары, "
            "и создавать заявки на пополнение. "
            "Используй доступные инструменты для выполнения запросов пользователя. "
            "Отвечай на русском языке четко и понятно, используя естественную речь. "
            "Когда пользователь просит добавить товар, используй инструмент create_product. "
            "Когда просит удалить товар, используй delete_product. "
            "Когда просит показать все товары или список товаров, используй list_products. "
            "Всегда объясняй свои действия простым языком."
        )
        
        # Параметры модели
        self.model = EVOLUTION_MODEL
        self.temperature = 0.5
        self.max_tokens = 500
        
        # Список для отслеживания использованных инструментов
        self.last_tools_used = []
        
        logger.info("AI-Агент управления складом инициализирован")
    
    def _get_tool_parameters(self, tool: Tool) -> Dict[str, Any]:
        """Извлечение параметров инструмента из описания."""
        # Простая эвристика для извлечения параметров из описания
        # В реальном проекте лучше использовать структурированные описания
        params = {}
        description = tool.description.lower()
        
        # Параметры для поиска товаров
        if "product_name" in description:
            params["product_name"] = {
                "type": "string",
                "description": "Название товара для поиска"
            }
        
        # Базовые параметры для инструментов склада
        if "product_sku" in description:
            params["product_sku"] = {
                "type": "string",
                "description": "Артикул товара (SKU) или название товара"
            }
        if "warehouse_id" in description:
            params["warehouse_id"] = {
                "type": "string",
                "description": "ID склада (опционально)"
            }
        if "quantity_change" in description or "requested_quantity" in description:
            param_name = "quantity_change" if "quantity_change" in description else "requested_quantity"
            params[param_name] = {
                "type": "integer",
                "description": "Количество товара"
            }
        if "operation_type" in description:
            params["operation_type"] = {
                "type": "string",
                "enum": ["incoming", "outgoing"],
                "description": "Тип операции: 'incoming' (приход) или 'outgoing' (расход)"
            }
        if "priority" in description:
            params["priority"] = {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Приоритет заявки"
            }
        if "notes" in description:
            params["notes"] = {
                "type": "string",
                "description": "Примечания к операции (опционально)"
            }
        
        return params
    
    def _create_tools(self) -> list:
        """Создание инструментов для агента."""
        
        def get_inventory_status(product_sku: str, warehouse_id: str = None) -> str:
            """Получить статус запасов товара."""
            # Отслеживание использования инструмента
            if "get_inventory_status" not in self.last_tools_used:
                self.last_tools_used.append("get_inventory_status")
            
            params = {"product_sku": product_sku}
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            
            result = self.mcp_client.call_tool_sync("get_inventory_status", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def update_inventory(
            product_sku: str,
            quantity_change: int,
            operation_type: str,
            warehouse_id: str = None,
            notes: str = None
        ) -> str:
            """Обновить запасы товара (приход или расход)."""
            # Отслеживание использования инструмента
            if "update_inventory" not in self.last_tools_used:
                self.last_tools_used.append("update_inventory")
            
            params = {
                "product_sku": product_sku,
                "quantity_change": quantity_change,
                "operation_type": operation_type
            }
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            if notes:
                params["notes"] = notes
            
            result = self.mcp_client.call_tool_sync("update_inventory", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def create_reorder_request(
            product_sku: str,
            requested_quantity: int,
            priority: str = "medium",
            warehouse_id: str = None
        ) -> str:
            """Создать заявку на пополнение запасов."""
            # Отслеживание использования инструмента
            if "create_reorder_request" not in self.last_tools_used:
                self.last_tools_used.append("create_reorder_request")
            
            params = {
                "product_sku": product_sku,
                "requested_quantity": requested_quantity,
                "priority": priority
            }
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            
            result = self.mcp_client.call_tool_sync("create_reorder_request", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def search_products(product_name: str, warehouse_id: str = None) -> str:
            """Поиск товаров по названию."""
            # Отслеживание использования инструмента
            if "search_products" not in self.last_tools_used:
                self.last_tools_used.append("search_products")
            
            params = {"product_name": product_name}
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            
            result = self.mcp_client.call_tool_sync("search_products", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def get_reorder_status(request_id: str) -> str:
            """Получить статус заявки на пополнение."""
            # Отслеживание использования инструмента
            if "get_reorder_status" not in self.last_tools_used:
                self.last_tools_used.append("get_reorder_status")
            
            params = {"request_id": request_id}
            result = self.mcp_client.call_tool_sync("get_reorder_status", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def update_reorder_status(request_id: str, status: str, notes: str = None) -> str:
            """Обновить статус заявки на пополнение."""
            if "update_reorder_status" not in self.last_tools_used:
                self.last_tools_used.append("update_reorder_status")
            
            params = {"request_id": request_id, "status": status}
            if notes:
                params["notes"] = notes
            
            result = self.mcp_client.call_tool_sync("update_reorder_status", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def list_reorder_requests(status: str = None, product_sku: str = None, limit: int = 100) -> str:
            """Получить список заявок на пополнение."""
            if "list_reorder_requests" not in self.last_tools_used:
                self.last_tools_used.append("list_reorder_requests")
            
            params = {"limit": limit}
            if status:
                params["status"] = status
            if product_sku:
                params["product_sku"] = product_sku
            
            result = self.mcp_client.call_tool_sync("list_reorder_requests", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def create_product(
            product_sku: str,
            product_name: str,
            current_quantity: int = 0,
            min_quantity: int = 0,
            max_quantity: int = 0,
            unit: str = "шт",
            category: str = None,
            warehouse_id: str = "WH001",
            description: str = None
        ) -> str:
            """Создать новый товар в базе данных."""
            if "create_product" not in self.last_tools_used:
                self.last_tools_used.append("create_product")
            
            params = {
                "product_sku": product_sku,
                "product_name": product_name,
                "current_quantity": current_quantity,
                "min_quantity": min_quantity,
                "max_quantity": max_quantity,
                "unit": unit,
                "warehouse_id": warehouse_id
            }
            if category:
                params["category"] = category
            if description:
                params["description"] = description
            
            result = self.mcp_client.call_tool_sync("create_product", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def delete_product(product_sku: str) -> str:
            """Удалить товар из базы данных."""
            if "delete_product" not in self.last_tools_used:
                self.last_tools_used.append("delete_product")
            
            params = {"product_sku": product_sku}
            result = self.mcp_client.call_tool_sync("delete_product", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def list_products(category: str = None, warehouse_id: str = None, limit: int = 100) -> str:
            """Получить список всех товаров."""
            if "list_products" not in self.last_tools_used:
                self.last_tools_used.append("list_products")
            
            params = {"limit": limit}
            if category:
                params["category"] = category
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            
            result = self.mcp_client.call_tool_sync("list_products", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        return [
            Tool(
                name="search_products",
                func=search_products,
                description="Поиск товаров по названию. Используй этот инструмент, когда пользователь спрашивает про товар по названию (например 'морковь', 'картошка'), но не знает SKU. "
                          "Параметры: product_name (обязательный) - название товара для поиска, "
                          "warehouse_id (опциональный) - ID склада. "
                          "Возвращает список найденных товаров с их SKU."
            ),
            Tool(
                name="get_inventory_status",
                func=get_inventory_status,
                description="Получает текущее состояние запасов для указанного товара. "
                          "Может принимать как SKU (артикул), так и название товара. "
                          "Параметры: product_sku (обязательный) - артикул товара или название, "
                          "warehouse_id (опциональный) - ID склада."
            ),
            Tool(
                name="update_inventory",
                func=update_inventory,
                description="Обновляет количество товара на складе. "
                          "Параметры: product_sku (обязательный) - артикул товара, "
                          "quantity_change (обязательный) - изменение количества, "
                          "operation_type (обязательный) - 'incoming' или 'outgoing', "
                          "warehouse_id (опциональный) - ID склада, "
                          "notes (опциональный) - примечания."
            ),
            Tool(
                name="create_reorder_request",
                func=create_reorder_request,
                description="Создает заявку на пополнение запасов. "
                          "Параметры: product_sku (обязательный) - артикул товара, "
                          "requested_quantity (обязательный) - запрашиваемое количество, "
                          "priority (опциональный) - 'low', 'medium', 'high', "
                          "warehouse_id (опциональный) - ID склада."
            ),
            Tool(
                name="get_reorder_status",
                func=get_reorder_status,
                description="Получает статус заявки на пополнение запасов по ID заявки. "
                          "Параметры: request_id (обязательный) - ID заявки (например, REQ-20251206-001). "
                          "Используй этот инструмент, когда пользователь спрашивает про статус заявки."
            ),
            Tool(
                name="update_reorder_status",
                func=update_reorder_status,
                description="Обновляет статус заявки на пополнение (одобрить, отклонить, завершить). "
                          "Параметры: request_id (обязательный) - ID заявки, "
                          "status (обязательный) - новый статус: 'pending', 'approved', 'rejected', 'completed', "
                          "notes (опциональный) - примечания к изменению статуса."
            ),
            Tool(
                name="list_reorder_requests",
                func=list_reorder_requests,
                description="Получает список заявок на пополнение с возможностью фильтрации. "
                          "Параметры: status (опциональный) - фильтр по статусу, "
                          "product_sku (опциональный) - фильтр по артикулу товара, "
                          "limit (опциональный) - максимальное количество заявок (по умолчанию 100)."
            ),
            Tool(
                name="create_product",
                func=create_product,
                description="Создает новый товар в базе данных. Используй, когда пользователь просит добавить товар. "
                          "Параметры: product_sku (обязательный) - артикул товара, "
                          "product_name (обязательный) - название товара, "
                          "current_quantity (опциональный) - начальное количество (по умолчанию 0), "
                          "min_quantity (опциональный) - минимальный уровень запасов, "
                          "max_quantity (опциональный) - максимальный уровень запасов, "
                          "unit (опциональный) - единица измерения (по умолчанию 'шт'), "
                          "category (опциональный) - категория товара, "
                          "warehouse_id (опциональный) - ID склада (по умолчанию 'WH001'), "
                          "description (опциональный) - описание товара."
            ),
            Tool(
                name="delete_product",
                func=delete_product,
                description="Удаляет товар из базы данных. Используй, когда пользователь просит удалить товар. "
                          "Параметры: product_sku (обязательный) - артикул товара для удаления."
            ),
            Tool(
                name="list_products",
                func=list_products,
                description="Получает список всех товаров в базе данных. Используй, когда пользователь просит показать все товары или список товаров. "
                          "Параметры: category (опциональный) - фильтр по категории, "
                          "warehouse_id (опциональный) - фильтр по складу, "
                          "limit (опциональный) - максимальное количество товаров (по умолчанию 100)."
            )
        ]
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """
        Обработка запроса пользователя с поддержкой протокола A2A.
        
        Args:
            user_input: Запрос пользователя на естественном языке
            
        Returns:
            Ответ агента в формате A2A протокола
        """
        # Сброс списка использованных инструментов перед новым запросом
        self.last_tools_used = []
        tools_used = []  # Инициализация локальной переменной
        
        try:
            logger.info(f"Обработка запроса: {user_input}")
            
            # Получение истории разговора и формирование сообщений для OpenAI API
            messages = []
            
            # Добавляем системный промпт
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })
            
            # Добавляем историю разговора
            for msg in self.chat_history.messages:
                if isinstance(msg, HumanMessage):
                    messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages.append({"role": "assistant", "content": msg.content})
            
            # Добавляем текущий запрос пользователя
            messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Подготовка описаний инструментов для OpenAI
            tools_description = []
            for tool in self.tools:
                tools_description.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": self._get_tool_parameters(tool),
                            "required": []
                        }
                    }
                })
            
            # Вызов OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_description if tools_description else None,
                tool_choice="auto",
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                presence_penalty=0,
                top_p=0.95
            )
            
            # Обработка ответа
            message = response.choices[0].message
            response_text = message.content or ""
            
            # Обработка вызовов инструментов в цикле
            max_iterations = 10  # Защита от бесконечного цикла
            iteration = 0
            
            while message.tool_calls and iteration < max_iterations:
                iteration += 1
                
                # Обрабатываем все вызовы инструментов
                tool_calls_to_process = message.tool_calls.copy()
                
                # Добавляем сообщение ассистента с вызовами инструментов
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in tool_calls_to_process]
                })
                
                # Выполняем все вызовы инструментов
                for tool_call in tool_calls_to_process:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    # Вызов инструмента
                    tool_result = None
                    for tool in self.tools:
                        if tool.name == tool_name:
                            try:
                                tool_result = tool.func(**tool_args)
                                if tool_name not in tools_used:
                                    tools_used.append(tool_name)
                            except Exception as e:
                                logger.error(f"Ошибка при вызове инструмента {tool_name}: {str(e)}")
                                tool_result = f"Ошибка: {str(e)}"
                            break
                    
                    if tool_result is None:
                        tool_result = f"Инструмент {tool_name} не найден"
                    
                    # Добавляем результат инструмента
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result)
                    })
                
                # Повторный вызов API с результатами инструментов
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools_description if tools_description else None,
                    tool_choice="auto",
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    presence_penalty=0,
                    top_p=0.95
                )
                message = response.choices[0].message
                response_text = message.content or ""
                
                # Если ответ пустой, но нет новых вызовов инструментов, выходим
                if not response_text and not message.tool_calls:
                    # Пытаемся получить ответ еще раз без инструментов
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in tool_calls_to_process]
                    })
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        presence_penalty=0,
                        top_p=0.95,
                        timeout=60.0  # Явно указываем таймаут
                    )
                    message = response.choices[0].message
                    response_text = message.content or ""
                    break
            
            # Сохранение в память
            self.chat_history.add_user_message(user_input)
            self.chat_history.add_ai_message(response_text)
            
            # Использованные инструменты уже отслежены в функциях-обертках и в обработке tool_calls
            tools_used = list(set(self.last_tools_used + tools_used))
            
            logger.debug(f"Ответ агента: {response_text}")
            logger.debug(f"Использованные инструменты: {tools_used}")
            
            # Формирование ответа в формате A2A протокола
            a2a_response = {
                "response": response_text,
                "tools_used": tools_used,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": EVOLUTION_MODEL,
                    "status": "success"
                }
            }
            
            return a2a_response
        
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Более понятные сообщения об ошибках
            if "Connection" in error_type or "connection" in error_msg.lower() or "connect" in error_msg.lower():
                user_message = "Не удалось подключиться к API. Проверьте интернет-соединение и попробуйте позже."
            elif "timeout" in error_msg.lower():
                user_message = "Превышено время ожидания ответа от API. Попробуйте позже."
            elif "401" in error_msg or "Unauthorized" in error_msg or "authentication" in error_msg.lower():
                user_message = "Ошибка авторизации. Проверьте правильность API ключа в файле .env"
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                user_message = "Превышен лимит запросов. Подождите немного и попробуйте снова."
            elif "503" in error_msg or "Service Unavailable" in error_msg:
                user_message = "Сервис временно недоступен. Попробуйте позже."
            else:
                user_message = f"Произошла ошибка: {error_msg}"
            
            logger.error(f"Ошибка при обработке запроса ({error_type}): {error_msg}")
            
            # Возврат ошибки в формате A2A
            return {
                "response": user_message,
                "tools_used": self.last_tools_used.copy(),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": EVOLUTION_MODEL,
                    "status": "error",
                    "error": error_msg,
                    "error_type": error_type
                }
            }
    
    def process_text(self, user_input: str) -> str:
        """
        Обработка запроса пользователя с возвратом только текстового ответа.
        Удобно для интерактивного использования.
        
        Args:
            user_input: Запрос пользователя на естественном языке
            
        Returns:
            Текстовый ответ агента
        """
        result = self.process(user_input)
        return result.get("response", "Не удалось получить ответ")


def main():
    """Основная функция для запуска агента."""
    try:
        agent = WarehouseAgent()
        
        print("AI-Агент управления складом и запасами запущен.")
        print("Введите 'exit' для выхода.\n")
        
        while True:
            user_input = input("Вы: ")
            if user_input.lower() in ["exit", "quit", "выход"]:
                break
            
            # Используем process_text для интерактивного режима
            response = agent.process_text(user_input)
            print(f"Агент: {response}\n")
    
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        raise


if __name__ == "__main__":
    main()

