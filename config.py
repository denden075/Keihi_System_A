import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "keihi.db")


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"db_path": DEFAULT_DB_PATH}


def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_db_path() -> str:
    return load_settings().get("db_path", DEFAULT_DB_PATH)
