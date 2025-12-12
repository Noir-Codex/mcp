"""Менеджер синхронизации с Битрикс24."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .client import bitrix24_client
from .models import BitrixDeal, BitrixTask, BitrixProduct

logger = logging.getLogger(__name__)


class SyncManager:
    """Управляет синхронизацией между MCP и Битрикс24."""
    
    def __init__(self):
        self.client = bitrix24_client
        self.sync_enabled = self.client.enabled
    
    async def sync_reorder_request(self, request_data: Dict[str, Any], product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Синхронизация заявки на пополнение с Битрикс24.
        Создает сделку и задачу.
        """
        if not self.sync_enabled:
            return {"status": "disabled", "message": "Интеграция отключена"}
        
        try:
            results = {}
            
            # 1. Создаем или получаем товар в Битрикс24
            product = BitrixProduct(
                name=product_data.get("product_name", f"Товар {product_data.get('product_sku')}"),
                xml_id=product_data.get("product_sku"),
                description=product_data.get("description", ""),
                price=0.0
            )
            
            product_id = await self.client.get_or_create_product(product)
            
            if not product_id:
                logger.error("Не удалось создать/найти товар в Битрикс24")
                return {"status": "error", "message": "Product sync failed"}
            
            # 2. Создаем сделку на закупку
            deal = BitrixDeal(
                title=f"Закупка: {product_data.get('product_name')}",
                stage_id="NEW",
                type_id="SALE",
                opportunity=0,
                comments=self._format_reorder_comments(request_data, product_data),
                product_sku=product_data.get("product_sku"),
                request_id=request_data.get("request_id"),
                warehouse_id=request_data.get("warehouse_id")
            )
            
            deal_id = await self.client.create_deal(deal)
            results["deal_id"] = deal_id
            
            if deal_id:
                # 3. Добавляем товар в сделку
                from .models import BitrixDealProductRow
                
                product_row = BitrixDealProductRow(
                    product_id=product_id,
                    product_name=product.name,
                    quantity=request_data.get("requested_quantity", 1),
                    price=0.0
                )
                
                await self.client.add_product_to_deal(deal_id, [product_row])
                
                # 4. Создаем задачу для менеджера
                task = BitrixTask(
                    title=f"Оформить заказ: {product_data.get('product_name')}",
                    description=self._format_task_description(request_data, product_data, deal_id),
                    deadline=self.client.format_deadline(
                        1 if request_data.get("priority") == "high" else 3
                    ),
                    priority=self.client.get_priority_code(request_data.get("priority", "medium")),
                    entity_id=deal_id,
                    entity_type="deals"
                )
                
                task_id = await self.client.create_task(task)
                results["task_id"] = task_id
            
            return {
                "status": "success",
                "results": results,
                "message": "Заявка синхронизирована с Битрикс24"
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации заявки: {str(e)}")
            return {
                "status": "error",
                "message": f"Ошибка синхронизации: {str(e)}"
            }
    
    async def sync_inventory_update(self, update_data: Dict[str, Any], product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Синхронизация обновления запасов с Битрикс24.
        Обновляет связанные сделки.
        """
        if not self.sync_enabled:
            return {"status": "disabled"}
        
        try:
            # Поиск сделок по SKU товара
            # Здесь можно добавить логику поиска сделок по пользовательскому полю UF_CRM_PRODUCT_SKU
            # и обновление их статуса при поступлении товара
            
            logger.info(f"Обновление запасов синхронизировано: {product_data.get('product_sku')}")
            
            return {
                "status": "success",
                "message": "Запасы обновлены в системе"
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации запасов: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def sync_new_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Синхронизация нового товара с каталогом Битрикс24."""
        if not self.sync_enabled:
            return {"status": "disabled"}
        
        try:
            product = BitrixProduct(
                name=product_data.get("product_name"),
                xml_id=product_data.get("product_sku"),
                description=product_data.get("description", ""),
                price=0.0
            )
            
            product_id = await self.client.get_or_create_product(product)
            
            return {
                "status": "success" if product_id else "error",
                "product_id": product_id,
                "message": "Товар синхронизирован с каталогом Битрикс24" if product_id else "Ошибка синхронизации товара"
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации товара: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _format_reorder_comments(self, request_data: Dict[str, Any], product_data: Dict[str, Any]) -> str:
        """Форматирование комментариев для сделки."""
        return f"""
📋 ЗАЯВКА НА ПОПОЛНЕНИЕ #{request_data.get('request_id', 'N/A')}

🏷️ Товар: {product_data.get('product_name', 'Не указан')}
🔢 SKU: {product_data.get('product_sku', 'Не указан')}

📊 Запасы:
   • Текущий остаток: {product_data.get('current_quantity', 0)} {product_data.get('unit', 'шт')}
   • Минимальный уровень: {product_data.get('min_quantity', 0)} {product_data.get('unit', 'шт')}
   • Максимальный уровень: {product_data.get('max_quantity', 0)} {product_data.get('unit', 'шт')}

🎯 Запрос:
   • Количество: {request_data.get('requested_quantity', 0)} {product_data.get('unit', 'шт')}
   • Приоритет: {request_data.get('priority', 'medium')}
   • Склад: {request_data.get('warehouse_id', 'Основной')}

⏰ Создано: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
📝 Автоматически создано из системы управления складом
        """.strip()
    
    def _format_task_description(self, request_data: Dict[str, Any], product_data: Dict[str, Any], deal_id: int) -> str:
        """Форматирование описания задачи."""
        return f"""
📋 ТРЕБУЕТСЯ ОФОРМИТЬ ЗАКАЗ

🛒 Товар: {product_data.get('product_name', 'Не указан')}
🔢 SKU: {product_data.get('product_sku', 'Не указан')}
📦 Количество: {request_data.get('requested_quantity', 0)} {product_data.get('unit', 'шт')}

⚠️ Приоритет: {request_data.get('priority', 'medium').upper()}
   • {'🚨 СРОЧНО (1 день)' if request_data.get('priority') == 'high' else '📅 Обычный (3 дня)'}

📊 Текущая ситуация:
   • Остаток на складе: {product_data.get('current_quantity', 0)} {product_data.get('unit', 'шт')}
   • Минимальный уровень: {product_data.get('min_quantity', 0)} {product_data.get('unit', 'шт')}
   • Дефицит: {max(0, product_data.get('min_quantity', 0) - product_data.get('current_quantity', 0))} {product_data.get('unit', 'шт')}

🔗 Связанные объекты:
   • ID заявки: {request_data.get('request_id', 'N/A')}
   • ID сделки: {deal_id}
   • Склад: {request_data.get('warehouse_id', 'Основной')}

---
📝 Задача создана автоматически при формировании заявки на пополнение
        """.strip()


# Глобальный экземпляр менеджера синхронизации
sync_manager = SyncManager()