import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


# モジュールレベルで保持するエンジン・セッション（reconfigure() で差し替え可能）
engine = None
SessionLocal = None


def _make_engine(db_path: str):
    abs_path = os.path.abspath(db_path)
    return create_engine(f"sqlite:///{abs_path}", connect_args={"check_same_thread": False})


def reconfigure(db_path: str) -> None:
    """DBパスを切り替えてエンジンを再構築する。新規ファイルの場合はテーブルも作成する。"""
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    engine = _make_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)
    init_db()


def init_db() -> None:
    from models import Customer, Project, Expense  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 起動時に設定ファイルのパスで初期化
def _bootstrap():
    from config import get_db_path
    reconfigure(get_db_path())


_bootstrap()
