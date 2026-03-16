# database_setup.py
"""
SQLite数据库创建模块
可以在其他Python代码中导入使用
"""

import sqlite3
import os

def create_csgo_database(db_path='csgo_items.db'):
    """
    创建SQLite数据库和表
    
    参数:
        db_path: 数据库文件路径
    
    返回:
        bool: 成功返回True，失败返回False
    """
    
    # SQL创建语句 - SQLite版本
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS items (
        url VARCHAR(500) NOT NULL,
        itemSetName VARCHAR(100),
        rarityName VARCHAR(50),
        itemName VARCHAR(250) NOT NULL,
        marketHashName VARCHAR(200),
        itemId BIGINT UNSIGNED NOT NULL PRIMARY KEY,
        grade VARCHAR(50),
        minPrice DECIMAL(10,2),
        minwear DECIMAL(5,4),
        maxwear DECIMAL(5,4),
        lastModified TIMESTAMP NULL
    )
    """
    
    # 创建索引的SQL语句
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_itemName ON items (itemName)",
        "CREATE INDEX IF NOT EXISTS idx_wear_range ON items (minwear, maxwear)",
        "CREATE INDEX IF NOT EXISTS idx_url ON items (url)",
        "CREATE INDEX IF NOT EXISTS idx_minPrice ON items (minPrice)"
    ]
    
    try:
        # 创建数据库连接
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        # 执行创建表语句
        cursor.execute(create_table_sql)
        
        # 执行创建索引语句
        for sql in create_indexes_sql:
            cursor.execute(sql)
        
        connection.commit()
        
        print("✅ 数据库创建成功")
        print(f"📊 数据库文件: {os.path.abspath(db_path)}")
        print("📋 表: items")
        print("📝 列顺序: url, itemSetName, rarityName, itemName, marketHashName, itemId, grade, minPrice, minwear, maxwear, lastModified")
        
        # 显示表结构
        cursor.execute("PRAGMA table_info(items)")
        columns = cursor.fetchall()
        print("\n📋 表结构:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULLABLE'}")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库创建失败: {e}")
        return False

def check_database_exists(db_path='csgo_items.db'):
    """
    检查数据库是否已存在
    
    参数:
        db_path: 数据库文件路径
    
    返回:
        bool: 存在返回True，不存在返回False
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(db_path):
            return False
        
        # 尝试连接并检查表是否存在
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        exists = cursor.fetchone() is not None
        
        cursor.close()
        connection.close()
        
        return exists
        
    except Exception:
        return False

def get_connection(db_path='csgo_items.db'):
    """
    获取数据库连接（供其他模块使用）
    
    参数:
        db_path: 数据库文件路径
    
    返回:
        connection: SQLite连接对象
    """
    try:
        # 设置row_factory以返回字典格式的结果
        def dict_factory(cursor, row):
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d
        
        connection = sqlite3.connect(db_path)
        connection.row_factory = dict_factory  # 设置为字典格式
        
        # 启用外键约束
        connection.execute("PRAGMA foreign_keys = ON")
        
        return connection
    except Exception as e:
        print(f"❌ 连接数据库失败: {e}")
        return None

def check_table_structure(db_path='csgo_items.db'):
    """
    检查表结构
    
    参数:
        db_path: 数据库文件路径
    
    返回:
        list: 列信息列表
    """
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        cursor.execute("PRAGMA table_info(items)")
        columns = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return columns
        
    except Exception as e:
        print(f"❌ 检查表结构失败: {e}")
        return None

# 如果直接运行此文件，则创建数据库
if __name__ == "__main__":
    # 这里可以修改数据库文件路径
    create_csgo_database()