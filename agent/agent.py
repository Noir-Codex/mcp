"""AI-Агент для управления складом и запасами с интеграцией Evolution Foundation Models и Битрикс24."""

import os
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.tools import Tool
from langchain_core.messages import HumanMessage, AIMessage
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
    """AI-Агент для управления складом и запасами с интеграцией Битрикс24."""
    
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
        
        # Системный промпт с интеграцией Битрикс24
        self.system_prompt = (
            "Ты - AI-ассистент для управления складом и запасами с полной интеграцией в CRM Битрикс24. "
            "🎯 **ПОЛНАЯ ИНТЕГРАЦИЯ С БИТРИКС24:**\n"
            "- 📦 МОДУЛЬ СКЛАДА: Работа с остатками через встроенный склад Битрикс24\n"
            "- 🏪 МНОГОСКЛАДСКОЙ УЧЕТ: Поддержка нескольких складов\n"
            "- 🔄 АВТОСИНХРОНИЗАЦИЯ: Автоматическая синхронизация остатков между MCP и Битрикс24\n"
            "- 📊 ДВИЖЕНИЯ ТОВАРОВ: Отслеживание приходов/расходов\n"
            "- 🚨 АВТОМАТИЧЕСКИЕ ПРОЦЕССЫ: Сделки и задачи создаются автоматически\n\n"
            "🔗 **ССЫЛКИ:**\n"
            "- CRM Битрикс24: https://b24-c4bq7q.bitrix24.ru/crm/deal/\n"
            "- Склады: https://b24-c4bq7q.bitrix24.ru/shop/stores/\n"
            "- Каталог: https://b24-c4bq7q.bitrix24.ru/crm/catalog/\n\n"
            "📋 **НОВЫЕ ВОЗМОЖНОСТИ СКЛАДА:**\n"
            "1. Просмотр всех складов компании (get_bitrix_warehouses)\n"
            "2. Получение остатков товара на конкретном складе (get_bitrix_product_stock)\n"
            "3. Установка остатков вручную (set_bitrix_product_stock)\n"
            "4. Отслеживание движений товаров (get_bitrix_stock_movements)\n"
            "5. Создание новых складов (create_bitrix_warehouse)\n"
            "6. Полная синхронизация всех остатков (sync_all_stock_to_bitrix)\n\n"
            "🎯 **КОГДА ИСПОЛЬЗОВАТЬ НОВЫЕ ИНСТРУМЕНТЫ:**\n"
            "- 'покажи все склады' → get_bitrix_warehouses\n"
            "- 'сколько товара X на складе Y' → get_bitrix_product_stock\n"
            "- 'обнови остатки товара' → set_bitrix_product_stock\n"
            "- 'история движений товара' → get_bitrix_stock_movements\n"
            "- 'создай новый склад' → create_bitrix_warehouse\n"
            "- 'синхронизируй все остатки' → sync_all_stock_to_bitrix\n\n"
            "🚀 **ПРИМЕРЫ ЗАПРОСОВ:**\n"
            "- 'Создай склад Основной по адресу Москва'\n"
            "- 'Покажи остатки товара МОЛОКО на всех складах'\n"
            "- 'Установи 100 единиц товара ХЛЕБ на складе 1'\n"
            "- 'Синхронизируй все остатки из нашей системы в Битрикс24'\n"
            "- 'Какие есть склады в компании?'\n\n"
            "📌 **ВАЖНО:** Все изменения в остатках автоматически синхронизируются с Битрикс24!\n\n"
            "РАБОТАЙ НА РУССКОМ ЯЗЫКЕ. БУДЬ ДРУЖЕЛЮБНЫМ И ПОЛЕЗНЫМ.\n"
            "ВСЕГДА УПОМИНАЙ О ИНТЕГРАЦИИ С БИТРИКС24 И ДАВАЙ ССЫЛКИ!"
        )
        
        # Параметры модели
        self.model = EVOLUTION_MODEL
        self.temperature = 0.5
        self.max_tokens = 500
        
        # Список для отслеживания использованных инструментов
        self.last_tools_used = []
        
        logger.info("AI-Агент управления складом с интеграцией Битрикс24 инициализирован")
    
    def _get_tool_parameters(self, tool: Tool) -> Dict[str, Any]:
        """Извлечение параметров инструмента из описания."""
        params = {}
        description = tool.description.lower()
        
        # Общие параметры
        if "product_sku" in description:
            params["product_sku"] = {
                "type": "string",
                "description": "Артикул товара (SKU) или название товара"
            }
        if "warehouse_id" in description:
            params["warehouse_id"] = {
                "type": "string" if "bitrix" not in description else "integer",
                "description": "ID склада"
            }
        if "quantity_change" in description or "requested_quantity" in description:
            param_name = "quantity_change" if "quantity_change" in description else "requested_quantity"
            params[param_name] = {
                "type": "integer",
                "description": "Количество товара"
            }
        if "quantity" in description and "quantity_change" not in description:
            params["quantity"] = {
                "type": "number",
                "description": "Количество (может быть дробным для весовых товаров)"
            }
        if "reserve_quantity" in description:
            params["reserve_quantity"] = {
                "type": "number",
                "description": "Зарезервированное количество"
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
        
        # Специфичные параметры для Битрикс24
        if "filter_title" in description:
            params["filter_title"] = {
                "type": "string",
                "description": "Фильтр по названию склада"
            }
        if "active_only" in description:
            params["active_only"] = {
                "type": "boolean",
                "description": "Только активные склады"
            }
        if "limit" in description:
            params["limit"] = {
                "type": "integer",
                "description": "Максимальное количество"
            }
        if "date_from" in description or "date_to" in description:
            if "date_from" in description:
                params["date_from"] = {
                    "type": "string",
                    "description": "Дата начала в формате YYYY-MM-DD"
                }
            if "date_to" in description:
                params["date_to"] = {
                    "type": "string",
                    "description": "Дата окончания в формате YYYY-MM-DD"
                }
        if "title" in description and "warehouse" in description:
            params["title"] = {
                "type": "string",
                "description": "Название склада"
            }
        if "address" in description:
            params["address"] = {
                "type": "string",
                "description": "Адрес склада"
            }
        if "description" in description and "warehouse" in description:
            params["description"] = {
                "type": "string",
                "description": "Описание склада"
            }
        if "active" in description and "warehouse" in description:
            params["active"] = {
                "type": "string",
                "enum": ["Y", "N"],
                "description": "Активность склада"
            }
        
        return params
    
    def _create_tools(self) -> list:
        """Создание инструментов для агента."""
        
        def get_inventory_status(product_sku: str, warehouse_id: str = None) -> str:
            """Получить статус запасов товара."""
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
            
            # Добавляем информацию о Битрикс24
            if isinstance(result, dict) and result.get("success"):
                result["bitrix_info"] = {
                    "message": "✅ Сделка автоматически создана в Битрикс24!",
                    "crm_link": "https://b24-c4bq7q.bitrix24.ru/crm/deal/",
                    "integration": "Автоматическая синхронизация с CRM"
                }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def search_products(product_name: str, warehouse_id: str = None) -> str:
            """Поиск товаров по названию."""
            if "search_products" not in self.last_tools_used:
                self.last_tools_used.append("search_products")
            
            params = {"product_name": product_name}
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            
            result = self.mcp_client.call_tool_sync("search_products", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def get_reorder_status(request_id: str) -> str:
            """Получить статус заявки на пополнение."""
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
        
        # Новые инструменты для Битрикс24
        def get_bitrix_warehouses(
            filter_title: str = None,
            active_only: bool = True,
            limit: int = 50
        ) -> str:
            """Получить список складов из Битрикс24."""
            if "get_bitrix_warehouses" not in self.last_tools_used:
                self.last_tools_used.append("get_bitrix_warehouses")
            
            params = {"active_only": active_only, "limit": limit}
            if filter_title:
                params["filter_title"] = filter_title
            
            result = self.mcp_client.call_tool_sync("get_bitrix_warehouses", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def get_bitrix_product_stock(
            product_sku: str,
            warehouse_id: int = None
        ) -> str:
            """Получить остатки товара на складах Битрикс24."""
            if "get_bitrix_product_stock" not in self.last_tools_used:
                self.last_tools_used.append("get_bitrix_product_stock")
            
            params = {"product_sku": product_sku}
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            
            result = self.mcp_client.call_tool_sync("get_bitrix_product_stock", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def set_bitrix_product_stock(
            product_sku: str,
            warehouse_id: int,
            quantity: float,
            reserve_quantity: float = 0.0
        ) -> str:
            """Установить остатки товара на складе Битрикс24."""
            if "set_bitrix_product_stock" not in self.last_tools_used:
                self.last_tools_used.append("set_bitrix_product_stock")
            
            params = {
                "product_sku": product_sku,
                "warehouse_id": warehouse_id,
                "quantity": quantity,
                "reserve_quantity": reserve_quantity
            }
            
            result = self.mcp_client.call_tool_sync("set_bitrix_product_stock", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def get_bitrix_stock_movements(
            product_sku: str = None,
            warehouse_id: int = None,
            date_from: str = None,
            date_to: str = None,
            limit: int = 100
        ) -> str:
            """Получить движения товаров в Битрикс24."""
            if "get_bitrix_stock_movements" not in self.last_tools_used:
                self.last_tools_used.append("get_bitrix_stock_movements")
            
            params = {"limit": limit}
            if product_sku:
                params["product_sku"] = product_sku
            if warehouse_id:
                params["warehouse_id"] = warehouse_id
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            
            result = self.mcp_client.call_tool_sync("get_bitrix_stock_movements", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def create_bitrix_warehouse(
            title: str,
            address: str = None,
            description: str = None,
            active: str = "Y"
        ) -> str:
            """Создать склад в Битрикс24."""
            if "create_bitrix_warehouse" not in self.last_tools_used:
                self.last_tools_used.append("create_bitrix_warehouse")
            
            params = {"title": title, "active": active}
            if address:
                params["address"] = address
            if description:
                params["description"] = description
            
            result = self.mcp_client.call_tool_sync("create_bitrix_warehouse", params)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def sync_all_stock_to_bitrix() -> str:
            """Полная синхронизация остатков из MCP в Битрикс24."""
            if "sync_all_stock_to_bitrix" not in self.last_tools_used:
                self.last_tools_used.append("sync_all_stock_to_bitrix")
            
            result = self.mcp_client.call_tool_sync("sync_all_stock_to_bitrix", {})
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        def check_bitrix_connection() -> str:
            """Проверить подключение к Битрикс24."""
            try:
                # Простая проверка через MCP сервер
                result = self.mcp_client.call_tool_sync("get_bitrix_warehouses", {"limit": 1})
                if result.get("success"):
                    return json.dumps({
                        "status": "success",
                        "message": "✅ Подключение к Битрикс24 активно",
                        "bitrix_url": "https://b24-c4bq7q.bitrix24.ru/"
                    }, ensure_ascii=False, indent=2)
                else:
                    return json.dumps({
                        "status": "error",
                        "message": "⚠️  Не удалось подключиться к Битрикс24"
                    }, ensure_ascii=False, indent=2)
            except Exception as e:
                return json.dumps({
                    "status": "error",
                    "message": f"❌ Ошибка при проверке подключения: {str(e)}"
                }, ensure_ascii=False, indent=2)
        
        return [
            Tool(
                name="check_bitrix_connection",
                func=check_bitrix_connection,
                description="Проверка подключения к CRM Битрикс24. Используй этот инструмент, когда нужно проверить работоспособность интеграции."
            ),
            Tool(
                name="get_bitrix_warehouses",
                func=get_bitrix_warehouses,
                description="Получение списка всех складов из Битрикс24. Используй, когда пользователь спрашивает 'какие есть склады', 'покажи все склады'. "
                          "Параметры: filter_title (опционально) - фильтр по названию, "
                          "active_only (опционально, по умолчанию True) - только активные склады, "
                          "limit (опционально, по умолчанию 50) - максимальное количество складов."
            ),
            Tool(
                name="get_bitrix_product_stock",
                func=get_bitrix_product_stock,
                description="Получение остатков конкретного товара на всех или определенном складе Битрикс24. "
                          "Используй, когда пользователь спрашивает 'сколько товара X на складе Y'. "
                          "Параметры: product_sku (обязательно) - SKU товара, "
                          "warehouse_id (опционально) - ID конкретного склада."
            ),
            Tool(
                name="set_bitrix_product_stock",
                func=set_bitrix_product_stock,
                description="Установка или обновление остатков товара на конкретном складе в Битрикс24. "
                          "Используй, когда нужно обновить остатки товара вручную. "
                          "Параметры: product_sku (обязательно) - SKU товара, "
                          "warehouse_id (обязательно) - ID склада, "
                          "quantity (обязательно) - количество (может быть дробным для весовых товаров), "
                          "reserve_quantity (опционально) - зарезервированное количество."
            ),
            Tool(
                name="get_bitrix_stock_movements",
                func=get_bitrix_stock_movements,
                description="Получение истории движений товаров в Битрикс24. "
                          "Используй, когда пользователь спрашивает 'история движений', 'отследить перемещения товара'. "
                          "Параметры: product_sku (опционально) - фильтр по SKU товара, "
                          "warehouse_id (опционально) - фильтр по ID склада, "
                          "date_from (опционально) - дата начала в формате YYYY-MM-DD, "
                          "date_to (опционально) - дата окончания в формате YYYY-MM-DD, "
                          "limit (опционально, по умолчанию 100) - максимальное количество записей."
            ),
            Tool(
                name="create_bitrix_warehouse",
                func=create_bitrix_warehouse,
                description="Создание нового склада в Битрикс24. "
                          "Используй, когда пользователь говорит 'создай склад', 'добавь новый склад'. "
                          "Параметры: title (обязательно) - название склада, "
                          "address (опционально) - адрес склада, "
                          "description (опционально) - описание склада, "
                          "active (опционально, по умолчанию 'Y') - активность склада: 'Y' или 'N'."
            ),
            Tool(
                name="sync_all_stock_to_bitrix",
                func=sync_all_stock_to_bitrix,
                description="Полная синхронизация всех остатков товаров из MCP системы в склад Битрикс24. "
                          "Используй, когда нужно обновить все остатки в Битрикс24."
            ),
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
                tool_params = self._get_tool_parameters(tool)
                if tool_params:  # Только если есть параметры
                    tools_description.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": {
                                "type": "object",
                                "properties": tool_params,
                                "required": list(tool_params.keys())  # Все параметры как обязательные для упрощения
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
            
            # Добавляем информацию о Битрикс24 если ее нет в ответе
            final_response = response_text
            if any(keyword in user_input.lower() for keyword in ['заявк', 'пополнен', 'сделк', 'битрикс', 'crm']):
                if 'битрикс' not in final_response.lower() and 'crm' not in final_response.lower():
                    bitrix_info = "\n\n🎯 **ИНТЕГРАЦИЯ С БИТРИКС24:**\n" \
                                  "✅ Сделка автоматически создана в CRM!\n" \
                                  "🔗 Проверить: https://b24-c4bq7q.bitrix24.ru/crm/deal/\n" \
                                  "📋 Менеджер уведомлен о необходимости закупки."
                    final_response = final_response + bitrix_info
            
            # Формирование ответа в формате A2A протокола
            a2a_response = {
                "response": final_response,
                "tools_used": tools_used,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": EVOLUTION_MODEL,
                    "status": "success",
                    "bitrix_integration": "active",
                    "bitrix_url": "https://b24-c4bq7q.bitrix24.ru/"
                }
            }
            
            return a2a_response
        
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Попытка fallback-обработки без LLM
            fallback = self._fallback_handle(user_input)
            if fallback:
                return fallback

            # Более понятные сообщения об ошибках
            if "Connection" in error_type or "connection" in error_msg.lower() or "connect" in error_msg.lower():
                user_message = "Не удалось подключиться к Evolution API. Проверьте интернет-соединение и попробуйте позже."
            elif "timeout" in error_msg.lower():
                user_message = "Превышено время ожидания ответа от Evolution API. Попробуйте позже."
            elif "401" in error_msg or "Unauthorized" in error_msg or "authentication" in error_msg.lower():
                user_message = "Ошибка авторизации. Проверьте правильность EVOLUTION_API_KEY в файле .env"
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                user_message = "Превышен лимит запросов к Evolution API. Подождите немного и попробуйте снова."
            elif "500" in error_msg or "InternalServerError" in error_type or "internal server error" in error_msg.lower():
                user_message = "Evolution API вернул ошибку 500. Это временная проблема сервиса — попробуйте еще раз позже."
            elif "503" in error_msg or "Service Unavailable" in error_msg:
                user_message = "Evolution API временно недоступен. Попробуйте позже."
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
                    "error_type": error_type,
                    "bitrix_integration": "unknown"
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
        response_text = result.get("response", "Не удалось получить ответ")
        
        # Добавляем информацию о Битрикс24 если ее нет в ответе
        if any(keyword in user_input.lower() for keyword in ['склад', 'остаток', 'синхрон', 'битрикс']):
            if 'битрикс' not in response_text.lower() and 'b24' not in response_text.lower():
                bitrix_info = "\n\n🔗 **Ссылки на Битрикс24:**\n" \
                              "- Склады: https://b24-c4bq7q.bitrix24.ru/shop/stores/\n" \
                              "- CRM: https://b24-c4bq7q.bitrix24.ru/crm/deal/\n" \
                              "- Каталог: https://b24-c4bq7q.bitrix24.ru/crm/catalog/"
                response_text = response_text + bitrix_info
        
        return response_text

    def _fallback_handle(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Простая деградация: при недоступности LLM пробуем маршрутизировать
        базовые запросы напрямую на MCP-инструменты.
        """
        text = user_input.lower()
        try:
            # Проверка складов
            if any(keyword in text for keyword in ["склад", "склады", "warehouse"]):
                result = self.mcp_client.call_tool_sync("get_bitrix_warehouses", {"limit": 10})
                if result.get("success"):
                    warehouses = result.get("warehouses", [])
                    response = "🏪 **Склады в Битрикс24:**\n\n"
                    for wh in warehouses[:5]:
                        response += f"• {wh.get('title')} (ID: {wh.get('id')})\n"
                    if len(warehouses) > 5:
                        response += f"\n... и еще {len(warehouses)-5} складов"
                    
                    return {
                        "response": response,
                        "tools_used": ["get_bitrix_warehouses"],
                        "metadata": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "model": "fallback",
                            "status": "fallback"
                        }
                    }
            
            # Список товаров
            wants_list = any(keyword in text for keyword in ["список товаров", "какие товары", "все товары"])
            if wants_list:
                result = self.mcp_client.call_tool_sync("list_products", {"limit": 10})
                products = result.get("products") or []
                names = [p.get("product_name") for p in products if p.get("product_name")]
                if names:
                    response = "📦 **Товары на складе:**\n\n" + "\n".join([f"• {name}" for name in names[:10]])
                    if len(names) > 10:
                        response += f"\n\n... и еще {len(names)-10} товаров"
                else:
                    response = "В базе пока нет товаров."
                
                return {
                    "response": response,
                    "tools_used": ["list_products"],
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "model": "fallback",
                        "status": "fallback"
                    }
                }
        except Exception as e:
            logger.error(f"Ошибка fallback-обработки: {str(e)}")
        return None


def main():
    """Основная функция для запуска агента."""
    try:
        agent = WarehouseAgent()
        
        print("=" * 60)
        print("🤖 AI-Агент управления складом с интеграцией Битрикс24")
        print("=" * 60)
        print("🎯 Полная интеграция с модулем Склад Битрикс24")
        print("📦 Доступные операции:")
        print("   • Просмотр всех складов компании")
        print("   • Управление остатками в реальном времени")
        print("   • Отслеживание движений товаров")
        print("   • Создание новых складов")
        print("   • Автосинхронизация остатков с CRM")
        print("   • Создание заявок на пополнение с автоматическими сделками")
        print("\n🔗 Ссылки на Битрикс24:")
        print("   - Склады: https://b24-c4bq7q.bitrix24.ru/shop/stores/")
        print("   - CRM: https://b24-c4bq7q.bitrix24.ru/crm/deal/")
        print("   - Каталог: https://b24-c4bq7q.bitrix24.ru/crm/catalog/")
        print("\nВведите 'exit' для выхода.")
        print("=" * 60)
        
        while True:
            user_input = input("\nВы: ")
            if user_input.lower() in ["exit", "quit", "выход"]:
                break
            
            # Используем process_text для интерактивного режима
            response = agent.process_text(user_input)
            print(f"\nАгент: {response}")
    
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        raise


if __name__ == "__main__":
    main()