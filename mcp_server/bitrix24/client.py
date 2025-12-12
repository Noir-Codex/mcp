"""Клиент для работы с API Битрикс24."""

import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urlencode

from .models import BitrixDeal, BitrixTask, BitrixProduct, BitrixContact, BitrixDealProductRow

logger = logging.getLogger(__name__)


class Bitrix24Client:
    """Клиент для взаимодействия с API Битрикс24."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("BITRIX24_WEBHOOK_URL")
        self.enabled = os.getenv("BITRIX24_ENABLED", "true").lower() == "true"
        self.assigned_by_id = int(os.getenv("BITRIX24_ASSIGNED_BY_ID", "1"))
        self.pipeline_id = int(os.getenv("BITRIX24_PIPELINE_ID", "1"))
        self.task_group_id = int(os.getenv("BITRIX24_TASK_GROUP_ID", "0"))
        
        if not self.webhook_url and self.enabled:
            logger.warning("BITRIX24_WEBHOOK_URL не указан, но интеграция включена")
            self.enabled = False
        
        if self.enabled:
            logger.info(f"Клиент Битрикс24 инициализирован. Вебхук: {self.webhook_url}")
            
        # Добавляем флаг для отслеживания проверки подключения
        self._connection_tested = False
        self._connection_successful = False
    
    async def ensure_connection(self) -> bool:
        """Проверка подключения к Битрикс24."""
        if not self.enabled:
            return False
        
        try:
            user = await self.get_current_user()
            if user:
                logger.info(f"✅ Подключение к Битрикс24 успешно. Пользователь: {user.get('NAME', 'Без имени')}")
                self._connection_successful = True
            else:
                logger.warning("⚠️  Не удалось получить данные пользователя")
                self._connection_successful = False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Битрикс24: {str(e)}")
            self._connection_successful = False
        
        self._connection_tested = True
        return self._connection_successful
    
    async def _make_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Базовый метод для запросов к API Битрикс24."""
        if not self.enabled:
            logger.debug("Битрикс24 отключен, запрос пропущен")
            return {"error": "Bitrix24 integration disabled"}
        
        if params is None:
            params = {}
        
        try:
            url = f"{self.webhook_url.rstrip('/')}/{method}"
            
            logger.debug(f"📤 Bitrix24 API Request: {method}")
            logger.debug(f"   URL: {url}")
            logger.debug(f"   Params: {json.dumps(params, ensure_ascii=False, indent=2)}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=params)
                
                logger.debug(f"📥 Bitrix24 API Response status: {response.status_code}")
                logger.debug(f"   Response headers: {dict(response.headers)}")
                
                if response.status_code == 401:
                    logger.error("❌ Ошибка авторизации в Битрикс24. Проверьте вебхук")
                    return {"error": "Authentication failed", "error_description": "Invalid webhook"}
                
                if response.status_code == 404:
                    logger.error("❌ Метод API не найден")
                    return {"error": "Method not found", "error_description": f"Method {method} does not exist"}
                
                response.raise_for_status()
                result = response.json()
                
                # Логируем полный ответ для отладки
                logger.debug(f"   Full response for {method}: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                if "error" in result:
                    error_msg = result.get("error_description", result["error"])
                    logger.error(f"❌ Bitrix24 API Error ({method}): {error_msg}")
                    return result
                
                # Также логируем структуру успешного ответа
                logger.debug(f"✅ Success response for {method}. Result type: {type(result.get('result', 'No result'))}")
                
                return result
            
        except httpx.TimeoutException:
            logger.error(f"⏰ Таймаут при запросе к Bitrix24: {method}")
            return {"error": "Timeout", "error_description": "Request timeout"}
        
        except httpx.RequestError as e:
            logger.error(f"🔌 Ошибка сети при запросе к Bitrix24: {str(e)}")
            return {"error": "Network error", "error_description": str(e)}
        
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при запросе к Bitrix24: {str(e)}", exc_info=True)
            return {"error": "Unexpected error", "error_description": str(e)}
    
    # ================ USER METHODS ================
    
    async def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Получение информации о текущем пользователе."""
        result = await self._make_request("user.current")
        return result.get("result")
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе по ID."""
        result = await self._make_request("user.get", {"ID": user_id})
        return result.get("result")
    
    # ================ DEAL METHODS ================
    
    async def create_deal(self, deal: BitrixDeal) -> Optional[int]:
        """Создание сделки в Битрикс24."""
        
        # Подготовка полей
        fields = {
            "TITLE": deal.title,
            "STAGE_ID": deal.stage_id,
            "TYPE_ID": deal.type_id,
            "CATEGORY_ID": deal.category_id or self.pipeline_id,
            "ASSIGNED_BY_ID": deal.assigned_by_id or self.assigned_by_id,
            "OPPORTUNITY": deal.opportunity,
            "CURRENCY_ID": deal.currency_id,
            "COMMENTS": deal.comments,
        }
        
        # Добавляем пользовательские поля если они есть
        if deal.product_sku:
            fields["UF_CRM_PRODUCT_SKU"] = deal.product_sku
        if deal.request_id:
            fields["UF_CRM_REQUEST_ID"] = deal.request_id
        if deal.warehouse_id:
            fields["UF_CRM_WAREHOUSE_ID"] = deal.warehouse_id
        
        result = await self._make_request("crm.deal.add", {"fields": fields})
        
        if "error" not in result and "result" in result:
            deal_id = result["result"]
            logger.info(f"✅ Сделка создана: ID={deal_id}, Название='{deal.title}'")
            return deal_id
        
        return None
    
    async def get_deal(self, deal_id: int) -> Optional[Dict[str, Any]]:
        """Получение сделки по ID."""
        result = await self._make_request("crm.deal.get", {"id": deal_id})
        return result.get("result")
    
    async def update_deal(self, deal_id: int, fields: Dict[str, Any]) -> bool:
        """Обновление сделки."""
        result = await self._make_request("crm.deal.update", {
            "id": deal_id,
            "fields": fields
        })
        return "error" not in result
    
    async def update_deal_stage(self, deal_id: int, stage_id: str) -> bool:
        """Обновление стадии сделки."""
        return await self.update_deal(deal_id, {"STAGE_ID": stage_id})
    
    async def add_product_to_deal(self, deal_id: int, product_rows: List[BitrixDealProductRow]) -> bool:
        """Добавление товаров в сделку."""
        rows = []
        for row in product_rows:
            rows.append({
                "PRODUCT_ID": row.product_id,
                "PRODUCT_NAME": row.product_name,
                "QUANTITY": row.quantity,
                "PRICE": row.price,
                "DISCOUNT_RATE": row.discount_rate,
                "TAX_RATE": row.tax_rate,
                "MEASURE_CODE": row.measure_code,
                "MEASURE_NAME": row.measure_name
            })
        
        result = await self._make_request("crm.deal.productrows.set", {
            "id": deal_id,
            "rows": rows
        })
        
        return "error" not in result
    
    # ================ TASK METHODS ================
    
    async def create_task(self, task: BitrixTask) -> Optional[int]:
        """Создание задачи в Битрикс24."""
        
        fields = {
            "TITLE": task.title,
            "DESCRIPTION": task.description or "",
            "RESPONSIBLE_ID": task.responsible_id or self.assigned_by_id,
            "CREATED_BY": task.creator_id or self.assigned_by_id,
            "PRIORITY": task.priority,
            "GROUP_ID": task.group_id or self.task_group_id,
            "STATUS": task.status,
        }
        
        if task.deadline:
            fields["DEADLINE"] = task.deadline
        
        if task.entity_id and task.entity_type:
            fields[f"{task.entity_type.upper()}_ID"] = task.entity_id
        
        result = await self._make_request("tasks.task.add", {"fields": fields})
        
        if "error" not in result and "result" in result:
            task_id = result["result"]["task"]["id"]
            logger.info(f"✅ Задача создана: ID={task_id}, Название='{task.title}'")
            return task_id
        
        return None
    
    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Получение задачи по ID."""
        result = await self._make_request("tasks.task.get", {"taskId": task_id})
        return result.get("result", {}).get("task")
    
    async def update_task(self, task_id: int, fields: Dict[str, Any]) -> bool:
        """Обновление задачи."""
        result = await self._make_request("tasks.task.update", {
            "taskId": task_id,
            "fields": fields
        })
        return "error" not in result
    
    # ================ PRODUCT METHODS ================
    
    async def get_or_create_product(self, product: BitrixProduct) -> Optional[int]:
        """Поиск или создание товара в Битрикс24."""
        
        try:
            # Пробуем найти по XML_ID (SKU)
            search_result = await self._make_request("crm.product.list", {
                "filter": {"XML_ID": product.xml_id},
                "select": ["ID", "NAME", "PRICE"]
            })
            
            # Простая обработка ответа
            if "error" not in search_result:
                result_data = search_result.get("result", {})
                
                # Обрабатываем разные форматы ответа
                if isinstance(result_data, dict):
                    products = result_data.get("products", [])
                elif isinstance(result_data, list):
                    products = result_data
                else:
                    products = []
                
                # Ищем товар
                for item in products:
                    if isinstance(item, dict) and item.get("XML_ID") == product.xml_id:
                        product_id = item.get("ID")
                        if product_id:
                            logger.info(f"🔍 Товар найден: ID={product_id}")
                            return product_id
            
            # Создаем новый товар
            fields = {
                "NAME": product.name,
                "XML_ID": product.xml_id,
                "DESCRIPTION": product.description or "",
                "PRICE": product.price,
                "CURRENCY_ID": product.currency_id,
                "MEASURE": product.measure,
                "ACTIVE": product.active
            }
            
            result = await self._make_request("crm.product.add", {"fields": fields})
            
            if "error" not in result:
                product_id = result.get("result")
                if product_id:
                    logger.info(f"✅ Товар создан: ID={product_id}")
                    return product_id
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка в get_or_create_product: {str(e)}")
            return None
    
    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Получение товара по ID."""
        result = await self._make_request("crm.product.get", {"id": product_id})
        return result.get("result")
    
    # ================ CONTACT METHODS ================
    
    async def create_contact(self, contact: BitrixContact) -> Optional[int]:
        """Создание контакта в Битрикс24."""
        
        fields = {
            "NAME": contact.name,
            "LAST_NAME": contact.last_name or "",
            "SECOND_NAME": contact.second_name or "",
            "TYPE_ID": "CLIENT",  # Тип контакта
        }
        
        if contact.email:
            fields["EMAIL"] = [{"VALUE": contact.email, "VALUE_TYPE": "WORK"}]
        
        if contact.phone:
            fields["PHONE"] = [{"VALUE": contact.phone, "VALUE_TYPE": "WORK"}]
        
        if contact.company_id:
            fields["COMPANY_ID"] = contact.company_id
        
        result = await self._make_request("crm.contact.add", {"fields": fields})
        
        if "error" not in result and "result" in result:
            contact_id = result["result"]
            logger.info(f"✅ Контакт создан: ID={contact_id}, Имя='{contact.name}'")
            return contact_id
        
        return None
    
    async def get_contact(self, contact_id: int) -> Optional[Dict[str, Any]]:
        """Получение контакта по ID."""
        result = await self._make_request("crm.contact.get", {"id": contact_id})
        return result.get("result")
    
    # ================ BATCH METHODS ================
    
    async def batch_request(self, commands: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Выполнение пакетного запроса."""
        result = await self._make_request("batch", {"halt": 0, "cmd": commands})
        return result.get("result", {})
    
    # ================ UTILITY METHODS ================
    
    def format_deadline(self, days_from_now: int = 3) -> str:
        """Форматирование даты дедлайна."""
        deadline = datetime.now(timezone.utc) + timedelta(days=days_from_now)
        return deadline.strftime("%Y-%m-%d 18:00:00")
    
    def get_priority_code(self, priority: str) -> int:
        """Конвертация приоритета из строки в код."""
        priority_map = {"low": 1, "medium": 2, "high": 3}
        return priority_map.get(priority.lower(), 2)


# Глобальный экземпляр клиента
bitrix24_client = Bitrix24Client()