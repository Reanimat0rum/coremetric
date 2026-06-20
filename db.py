import sqlite3
import os
import shutil
from datetime import datetime

# ✅ ПРАВИЛЬНЫЙ ПУТЬ ДЛЯ ANDROID И ПК
# На Android Flet кладёт скрипты в /data/user/0/.../files/flet/app/
# Эта папка доступна на запись нашему приложению.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "coremetric.db")
BACKUP_DIR = os.path.join(APP_DIR, "backups")


def init_db():
    try:
        # Убеждаемся, что папка бэкапов существует
        os.makedirs(BACKUP_DIR, exist_ok=True)

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
        # Если не удалось создать БД, запишем ошибку в файл рядом
        try:
            with open(os.path.join(APP_DIR, "db_init_error.txt"), "w") as f:
                f.write(str(e))
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


# Инициализация при импорте
init_db()