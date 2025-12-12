"""Пакет для интеграции с Битрикс24."""

from .client import Bitrix24Client, bitrix24_client
from .models import BitrixDeal, BitrixTask, BitrixContact, BitrixProduct, BitrixDealProductRow
from .sync import SyncManager, sync_manager
from .advanced import BitrixWarehouseManager, warehouse_manager

__version__ = "2.0.0"
__all__ = [
    "Bitrix24Client", 
    "bitrix24_client", 
    "BitrixDeal", 
    "BitrixTask", 
    "BitrixContact",
    "BitrixProduct",
    "BitrixDealProductRow",
    "SyncManager", 
    "sync_manager",
    "BitrixWarehouseManager",
    "warehouse_manager"
]