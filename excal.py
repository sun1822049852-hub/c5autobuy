import sqlite3
import pandas as pd
import os
from datetime import datetime


def find_db_files():
    """查找当前目录下所有.db文件"""
    db_files = []
    for file in os.listdir('.'):
        if file.endswith('.db'):
            db_files.append(file)
    return db_files


def export_database_to_excel(db_path=None, output_file=None):
    """
    将数据库内容导出为Excel文件
    如果未指定数据库路径，则让用户选择当前目录下的数据库文件
    """
    # 如果没有指定数据库路径，查找当前目录下的.db文件
    if db_path is None:
        db_files = find_db_files()
        
        if not db_files:
            print("当前目录下未找到任何.db数据库文件")
            return False
        
        print("找到以下数据库文件：")
        for i, db_file in enumerate(db_files, 1):
            print(f"{i}. {db_file}")
        
        # 让用户选择数据库
        while True:
            try:
                choice = input(f"请选择要导出的数据库 (1-{len(db_files)}) 或输入 'q' 退出: ")
                if choice.lower() == 'q':
                    print("已取消导出")
                    return False
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(db_files):
                    db_path = db_files[choice_num - 1]
                    break
                else:
                    print(f"请输入 1-{len(db_files)} 之间的数字")
            except ValueError:
                print("请输入有效的数字")
    
    # 设置输出文件名
    if output_file is None:
        db_name = os.path.splitext(os.path.basename(db_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{db_name}_export_{timestamp}.xlsx"
    
    try:
        # 验证数据库文件是否存在
        if not os.path.exists(db_path):
            print(f"数据库文件不存在: {db_path}")
            return False
        
        print(f"正在导出数据库: {db_path}")
        
        # 连接数据库
        conn = sqlite3.connect(db_path)
        
        # 读取所有表
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [table[0] for table in cursor.fetchall()]
        
        if not tables:
            print("数据库中未找到任何表")
            conn.close()
            return False
        
        # 创建Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for table in tables:
                # 读取表数据
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                
                # 写入Excel工作表
                df.to_excel(writer, sheet_name=table, index=False)
                
                print(f"表 '{table}' 已导出，包含 {len(df)} 行数据")
        
        print(f"\n数据库已成功导出到: {output_file}")
        print(f"文件大小: {os.path.getsize(output_file) / 1024:.2f} KB")
        return True
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"导出失败: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass


def export_all_databases():
    """导出当前目录下所有数据库"""
    db_files = find_db_files()
    
    if not db_files:
        print("当前目录下未找到任何.db数据库文件")
        return False
    
    success_count = 0
    for db_file in db_files:
        print(f"\n{'='*50}")
        print(f"正在处理: {db_file}")
        if export_database_to_excel(db_file):
            success_count += 1
    
    print(f"\n{'='*50}")
    print(f"处理完成: 共 {len(db_files)} 个数据库，成功导出 {success_count} 个")
    return success_count > 0


# 使用方法
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='导出SQLite数据库到Excel')
    parser.add_argument('--db', '-d', help='指定数据库文件路径')
    parser.add_argument('--output', '-o', help='指定输出Excel文件名')
    parser.add_argument('--all', '-a', action='store_true', help='导出当前目录下所有数据库')
    
    args = parser.parse_args()
    
    if args.all:
        # 导出所有数据库
        export_all_databases()
    elif args.db:
        # 导出指定数据库
        export_database_to_excel(args.db, args.output)
    else:
        # 交互式选择数据库
        export_database_to_excel()