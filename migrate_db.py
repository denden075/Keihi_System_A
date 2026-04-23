"""
既存の keihi.db を新しいスキーマへ移行するスクリプト。
初回のみ実行してください。
  python migrate_db.py
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

new_columns = [
    ("amount_ex_tax",        "INTEGER"),
    ("amount_inc_tax",       "INTEGER"),
    ("invoice_processed_at", "DATE"),
    ("arrival_date",         "DATE"),
    ("supplier",             "TEXT"),
    ("payment_method",       "TEXT"),
    ("order_number",         "TEXT"),
    ("person_in_charge",     "TEXT"),
    ("arrival_status",       "TEXT NOT NULL DEFAULT '未発注'"),
    ("accounting_processed", "INTEGER NOT NULL DEFAULT 0"),
]

for col_name, col_def in new_columns:
    try:
        cursor.execute(f"ALTER TABLE expenses ADD COLUMN {col_name} {col_def}")
        print(f"  追加: {col_name}")
    except sqlite3.OperationalError as e:
        print(f"  スキップ（既存）: {col_name} — {e}")

cursor.execute("UPDATE expenses SET amount_ex_tax = amount WHERE amount_ex_tax IS NULL")
print(f"  amount → amount_ex_tax コピー: {cursor.rowcount} 件")

conn.commit()
conn.close()
print("マイグレーション完了。")
