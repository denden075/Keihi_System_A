# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

会社のプロジェクト一覧管理と費用管理を行うローカルWebアプリ。Flask + SQLite 構成。

## 技術スタック

- **Backend**: Python / Flask / SQLAlchemy
- **Database**: SQLite（単一ファイル）
- **Frontend**: HTML / Bootstrap / JavaScript（SPA不使用、サーバーサイドレンダリング）
- **通貨**: 日本円のみ

## 想定するディレクトリ構成

```
Project_Keihi/
├── app.py              # Flaskアプリエントリポイント・ルーティング
├── models.py           # SQLAlchemyモデル（Project, Expense）
├── database.py         # DB初期化・セッション管理
├── keihi.db            # SQLiteデータベースファイル（自動生成）
├── templates/          # Jinja2テンプレート
│   ├── base.html
│   ├── dashboard.html
│   ├── projects/
│   └── expenses/
├── static/             # CSS / JS
└── requirements.txt
```

## 開発コマンド

```bash
# 依存インストール
pip install -r requirements.txt

# 開発サーバー起動（http://localhost:5000）
python app.py

# DBの初期化（初回・リセット時）
python -c "from database import init_db; init_db()"
```

## データモデル

**projects**：id, name, description, start_date, end_date, status, budget（予算上限・NULL可）, created_at, updated_at  
**expenses**：id, project_id(FK), name, category, amount（円・整数）, occurred_at, note, created_at, updated_at

- `status` は `'進行中' | '完了' | '保留'` の固定値
- `category` は `'人件費' | '外注費' | '備品' | '交通費' | 'その他'` の固定値
- `budget` は NULL のとき予算未設定扱い

## 主要な仕様

- 費用合計が `budget` を超過した場合、一覧・詳細画面で警告表示する
- プロジェクト削除時は紐づく expenses も CASCADE 削除する
- CSV出力はプロジェクト別（`/projects/<id>/export`）
- 認証なし・シングルユーザー前提
