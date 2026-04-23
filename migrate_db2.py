"""
第2マイグレーション：quantity追加、category削除
  python migrate_db2.py
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import get_db_path

db_path = get_db_path()
print(f"対象DB: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# quantity 追加
try:
    cursor.execute("ALTER TABLE expenses ADD COLUMN quantity INTEGER")
    print("  追加: quantity")
except sqlite3.OperationalError as e:
    print(f"  スキップ（既存）: quantity — {e}")

# category 削除（SQLite 3.35+）
try:
    cursor.execute("ALTER TABLE expenses DROP COLUMN category")
    print("  削除: category")
except sqlite3.OperationalError as e:
    print(f"  スキップ（削除不可）: category — {e}")

conn.commit()
conn.close()
print("マイグレーション完了。")
