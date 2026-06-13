import sqlite3
import os
import shutil
from datetime import datetime


def _get_app_dir():
    """Возвращает writable папку для хранения данных приложения."""
    # 1. Пробуем переменную окружения Flet (Android)
    android_data = os.environ.get("FLET_APP_STORAGE_DATA")
    if android_data and os.path.isdir(android_data):
        return android_data

    # 2. Папка рядом с main.py (на Android это /data/user/0/com.flet.coremetric/files/flet/app/)
    # Этот путь writable на Android
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.access(script_dir, os.W_OK):
        return script_dir

    # 3. HOME на Android (обычно writable)
    home = os.environ.get("HOME") or os.path.expanduser("~")
    if home and os.path.isdir(home) and os.access(home, os.W_OK):
        app_dir = os.path.join(home, ".coremetric")
        try:
            os.makedirs(app_dir, exist_ok=True)
            return app_dir
        except:
            pass

    # 4. Фолбэк: временная папка (всегда writable)
    import tempfile
    return tempfile.gettempdir()


APP_DIR = _get_app_dir()
DB_PATH = os.path.join(APP_DIR, "coremetric.db")
BACKUP_DIR = os.path.join(APP_DIR, "backups")


def init_db():
    try:
        os.makedirs(APP_DIR, exist_ok=True)
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
    except Exception as e:
        # Логируем ошибку
        try:
            log_path = os.path.join(APP_DIR, "db_error.log")
            with open(log_path, "w") as f:
                f.write(f"Error: {str(e)}\n")
                f.write(f"APP_DIR: {APP_DIR}\n")
                f.write(f"DB_PATH: {DB_PATH}\n")
        except:
            pass


def get_setting(key):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            res = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
            return res[0] if res else "ru"
    except:
        return "ru"


def set_setting(key, value):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (key, value))
    except:
        pass


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
    path = os.path.join(APP_DIR, "export.csv")
    df.to_csv(path, index=False)
    return path


init_db()