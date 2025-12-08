"""База данных для хранения заявок на пополнение."""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Путь к базе данных
DB_PATH = os.getenv("WAREHOUSE_DB_PATH", "warehouse.db")


def init_database():
    """Инициализация базы данных и создание таблиц."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица товаров
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_sku TEXT PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    current_quantity INTEGER NOT NULL DEFAULT 0,
                    min_quantity INTEGER NOT NULL DEFAULT 0,
                    max_quantity INTEGER NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT 'шт',
                    category TEXT,
                    warehouse_id TEXT DEFAULT 'WH001',
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    description TEXT
                )
            """)
            
            # Индексы для товаров
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_name 
                ON products(product_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_category 
                ON products(category)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_warehouse 
                ON products(warehouse_id)
            """)
            
            # Таблица заявок на пополнение
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reorder_requests (
                    request_id TEXT PRIMARY KEY,
                    product_sku TEXT NOT NULL,
                    requested_quantity INTEGER NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    warehouse_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    notes TEXT
                )
            """)
            
            # Индекс для быстрого поиска
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reorder_requests_status 
                ON reorder_requests(status)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reorder_requests_product_sku 
                ON reorder_requests(product_sku)
            """)
            
            # Миграция существующих товаров из памяти в БД (если таблица пустая)
            cursor.execute("SELECT COUNT(*) FROM products")
            if cursor.fetchone()[0] == 0:
                _migrate_initial_products(cursor)
            
            conn.commit()
            logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        raise


def _migrate_initial_products(cursor):
    """Миграция начальных товаров в БД."""
    from .mcp_tools import _inventory_storage
    import datetime
    
    initial_products = [
        ("MORK-001", "Морковь", 150, 50, 500, "кг", "овощи", "WH001"),
        ("KART-001", "Картофель", 200, 100, 1000, "кг", "овощи", "WH001"),
        ("KAPU-001", "Капуста", 80, 50, 300, "кг", "овощи", "WH001"),
        ("LUK-001", "Лук репчатый", 120, 50, 400, "кг", "овощи", "WH001"),
        ("POM-001", "Помидоры", 60, 30, 200, "кг", "овощи", "WH001"),
    ]
    
    now = datetime.datetime.utcnow().isoformat() + "Z"
    for sku, name, qty, min_qty, max_qty, unit, category, wh_id in initial_products:
        cursor.execute("""
            INSERT OR IGNORE INTO products 
            (product_sku, product_name, current_quantity, min_quantity, max_quantity, 
             unit, category, warehouse_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sku, name, qty, min_qty, max_qty, unit, category, wh_id, now, now))
    
    logger.info(f"Мигрировано {len(initial_products)} товаров в БД")


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с базой данных."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_reorder_request(
    request_id: str,
    product_sku: str,
    requested_quantity: int,
    priority: str,
    warehouse_id: Optional[str] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Создание заявки на пополнение в базе данных."""
    try:
        created_at = datetime.utcnow().isoformat() + "Z"
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reorder_requests 
                (request_id, product_sku, requested_quantity, priority, status, 
                 warehouse_id, created_at, updated_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id,
                product_sku,
                requested_quantity,
                priority,
                "pending",
                warehouse_id or "WH001",
                created_at,
                created_at,
                notes
            ))
            conn.commit()
        
        logger.info(f"Заявка {request_id} создана в базе данных")
        
        return {
            "request_id": request_id,
            "product_sku": product_sku,
            "requested_quantity": requested_quantity,
            "priority": priority,
            "status": "pending",
            "warehouse_id": warehouse_id or "WH001",
            "created_at": created_at,
            "notes": notes
        }
    except sqlite3.IntegrityError:
        raise ValueError(f"Заявка с ID {request_id} уже существует")
    except Exception as e:
        logger.error(f"Ошибка при создании заявки в БД: {str(e)}")
        raise


def get_reorder_request(request_id: str) -> Optional[Dict[str, Any]]:
    """Получение заявки на пополнение по ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM reorder_requests WHERE request_id = ?
            """, (request_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении заявки из БД: {str(e)}")
        raise


def update_reorder_request_status(
    request_id: str,
    status: str,
    notes: Optional[str] = None
) -> bool:
    """Обновление статуса заявки."""
    try:
        updated_at = datetime.utcnow().isoformat() + "Z"
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if notes:
                cursor.execute("""
                    UPDATE reorder_requests 
                    SET status = ?, updated_at = ?, notes = ?
                    WHERE request_id = ?
                """, (status, updated_at, notes, request_id))
            else:
                cursor.execute("""
                    UPDATE reorder_requests 
                    SET status = ?, updated_at = ?
                    WHERE request_id = ?
                """, (status, updated_at, request_id))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса заявки: {str(e)}")
        raise


def list_reorder_requests(
    status: Optional[str] = None,
    product_sku: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Получение списка заявок с фильтрацией."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM reorder_requests WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if product_sku:
                query += " AND product_sku = ?"
                params.append(product_sku)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении списка заявок: {str(e)}")
        raise


# Функции для работы с товарами
def create_product(
    product_sku: str,
    product_name: str,
    current_quantity: int = 0,
    min_quantity: int = 0,
    max_quantity: int = 0,
    unit: str = "шт",
    category: Optional[str] = None,
    warehouse_id: str = "WH001",
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Создание нового товара в базе данных."""
    try:
        created_at = datetime.utcnow().isoformat() + "Z"
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products 
                (product_sku, product_name, current_quantity, min_quantity, max_quantity,
                 unit, category, warehouse_id, created_at, updated_at, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_sku,
                product_name,
                current_quantity,
                min_quantity,
                max_quantity,
                unit,
                category,
                warehouse_id,
                created_at,
                created_at,
                description
            ))
            conn.commit()
        
        logger.info(f"Товар {product_sku} ({product_name}) создан в БД")
        
        return {
            "product_sku": product_sku,
            "product_name": product_name,
            "current_quantity": current_quantity,
            "min_quantity": min_quantity,
            "max_quantity": max_quantity,
            "unit": unit,
            "category": category,
            "warehouse_id": warehouse_id,
            "created_at": created_at,
            "description": description
        }
    except sqlite3.IntegrityError:
        raise ValueError(f"Товар с SKU {product_sku} уже существует")
    except Exception as e:
        logger.error(f"Ошибка при создании товара в БД: {str(e)}")
        raise


def get_product(product_sku: str) -> Optional[Dict[str, Any]]:
    """Получение товара по SKU."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE product_sku = ?", (product_sku,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении товара из БД: {str(e)}")
        raise


def update_product_quantity(
    product_sku: str,
    new_quantity: int
) -> bool:
    """Обновление количества товара."""
    try:
        updated_at = datetime.utcnow().isoformat() + "Z"
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE products 
                SET current_quantity = ?, updated_at = ?
                WHERE product_sku = ?
            """, (new_quantity, updated_at, product_sku))
            
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при обновлении количества товара: {str(e)}")
        raise


def delete_product(product_sku: str) -> bool:
    """Удаление товара из базы данных."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE product_sku = ?", (product_sku,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении товара: {str(e)}")
        raise


def search_products_db(
    product_name: Optional[str] = None,
    category: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Поиск товаров в базе данных."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM products WHERE 1=1"
            params = []
            
            if product_name:
                query += " AND (product_name LIKE ? OR product_sku LIKE ?)"
                search_term = f"%{product_name}%"
                params.extend([search_term, search_term])
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if warehouse_id:
                query += " AND warehouse_id = ?"
                params.append(warehouse_id)
            
            query += " ORDER BY product_name LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при поиске товаров: {str(e)}")
        raise


def list_all_products(limit: int = 1000) -> List[Dict[str, Any]]:
    """Получение списка всех товаров."""
    return search_products_db(limit=limit)


def update_product(
    product_sku: str,
    product_name: Optional[str] = None,
    min_quantity: Optional[int] = None,
    max_quantity: Optional[int] = None,
    unit: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None
) -> bool:
    """Обновление информации о товаре."""
    try:
        updated_at = datetime.utcnow().isoformat() + "Z"
        
        updates = []
        params = []
        
        if product_name is not None:
            updates.append("product_name = ?")
            params.append(product_name)
        
        if min_quantity is not None:
            updates.append("min_quantity = ?")
            params.append(min_quantity)
        
        if max_quantity is not None:
            updates.append("max_quantity = ?")
            params.append(max_quantity)
        
        if unit is not None:
            updates.append("unit = ?")
            params.append(unit)
        
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if not updates:
            return False
        
        updates.append("updated_at = ?")
        params.append(updated_at)
        params.append(product_sku)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = f"UPDATE products SET {', '.join(updates)} WHERE product_sku = ?"
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при обновлении товара: {str(e)}")
        raise


# Инициализация базы данных при импорте
init_database()

