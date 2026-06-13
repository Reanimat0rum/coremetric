import sqlite3
import os
import shutil
from datetime import datetime
import flet as ft

# ✅ Путь к БД: на Android используем app.files.dir, на ПК — папку скрипта
def _get_app_dir():
    """Возвращает папку для хранения данных приложения."""
    try:
        # Flet 0.25.2+: app.files.dir указывает в writable папку приложения
        if hasattr(ft, 'FLET_APP_STORAGE_DATA'):
            return ft.FLET_APP_STORAGE_DATA
        # Альтернатива: домашняя папка пользователя
        home = os.path.expanduser("~")
        app_dir = os.path.join(home, ".coremetric")
        os.makedirs(app_dir, exist_ok=True)
        return app_dir
    except Exception:
        # Фолбэк: папка скрипта (для разработки на ПК)
        return os.path.dirname(os.path.abspath(__file__))

APP_DIR = _get_app_dir()
DB_PATH = os.path.join(APP_DIR, "coremetric.db")
BACKUP_DIR = os.path.join(APP_DIR, "backups")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            resting_hr REAL, sys_bp REAL, dia_bp REAL,
            mood REAL, sleep_quality REAL, physical_state REAL,
            calories REAL, weight REAL,
            ortho_lying REAL, ortho_standing REAL,
            spo2 REAL, rpe REAL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_logs(date)")
        conn.execute("""CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY, value TEXT
        )""")
        conn.execute("INSERT OR IGNORE INTO app_settings VALUES ('theme', 'light')")
        conn.execute("INSERT OR IGNORE INTO app_settings VALUES ('lang', 'ru')")

def get_setting(key):
    with sqlite3.connect(DB_PATH) as conn:
        res = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return res[0] if res else "ru"

def set_setting(key, value):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (key, value))

def upsert_entry(data):
    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    values = [data[c] for c in cols]
    update = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "date"])
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"""
            INSERT INTO daily_logs ({", ".join(cols)}) VALUES ({placeholders})
            ON CONFLICT(date) DO UPDATE SET {update}
        """, values)

def get_all(limit_days=365):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        q = f"SELECT * FROM daily_logs WHERE date >= date('now', '-{limit_days} days') ORDER BY date"
        return [dict(r) for r in conn.execute(q).fetchall()]

def delete_entry(date_str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM daily_logs WHERE date=?", (date_str,))

def clear_all():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM daily_logs")

def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"coremetric_{ts}.db")
    shutil.copy2(DB_PATH, dest)
    return dest

def export_csv():
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM daily_logs ORDER BY date", sqlite3.connect(DB_PATH))
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "export.csv")
    df.to_csv(path, index=False)
    return path

init_db()