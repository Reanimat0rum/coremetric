import sqlite3
from datetime import datetime, timedelta
import random
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coremetric.db")


def generate_test_data(days=60):
    """Генерирует реалистичные тестовые данные с паттернами"""
    data = []
    base_date = datetime.now() - timedelta(days=days)

    # Базовые значения для спортсмена
    base_hr = 60
    base_sys_bp = 120
    base_dia_bp = 75
    base_weight = 78.0

    for i in range(days):
        current_date = base_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")

        # Добавляем вариативность и тренды
        day_of_week = current_date.weekday()

        # Имитация тренировочных циклов (недельные микроциклы)
        week_num = i // 7
        if week_num % 3 == 2 and day_of_week >= 4:
            # Неделя разгрузки (каждый 3-й недели)
            load_factor = 0.6
            recovery_bonus = 10
        else:
            # Обычные тренировочные недели
            load_factor = 1.0 + (day_of_week * 0.05)
            recovery_bonus = 0

        # ЧСС покоя (растет при утомлении, падает при восстановлении)
        resting_hr = base_hr + random.uniform(-3, 3)
        if day_of_week >= 4 and week_num % 3 != 2:
            resting_hr += 5 * load_factor  # Накопление утомления к концу недели
        resting_hr = round(resting_hr, 1)

        # Артериальное давление
        sys_bp = round(base_sys_bp + random.uniform(-5, 5) + (load_factor - 1) * 10, 0)
        dia_bp = round(base_dia_bp + random.uniform(-3, 3) + (load_factor - 1) * 5, 0)

        # Качество сна (хуже после тяжелых дней)
        sleep_quality = round(75 + random.uniform(-15, 15) - (load_factor - 1) * 20 + recovery_bonus, 0)
        sleep_quality = max(20, min(95, sleep_quality))

        # Настроение
        mood = round(70 + random.uniform(-20, 20) - (load_factor - 1) * 15 + recovery_bonus, 0)
        mood = max(25, min(95, mood))

        # Физическое самочувствие
        physical_state = round(72 + random.uniform(-18, 18) - (load_factor - 1) * 18 + recovery_bonus, 0)
        physical_state = max(30, min(95, physical_state))

        # Калории (зависят от дня недели и цикла)
        base_calories = 2500
        if day_of_week < 2:
            calories = base_calories * 0.9  # Легкие дни
        elif day_of_week < 5:
            calories = base_calories * (1.1 + load_factor * 0.2)  # Тяжелые дни
        else:
            calories = base_calories * 0.85  # Выходные

        calories = round(calories + random.uniform(-200, 200), 0)

        # Вес (медленные колебания)
        weight = round(base_weight + random.uniform(-0.5, 0.5) + (i * 0.01), 1)

        # Ортостатическая проба
        ortho_lying = round(resting_hr + random.uniform(-2, 2), 0)
        ortho_standing = round(ortho_lying * 1.25 + random.uniform(-5, 5) + (load_factor - 1) * 8, 0)

        # Сатурация
        spo2 = round(97 + random.uniform(-2, 1), 0)
        if load_factor > 1.3:
            spo2 -= 1  # Легкое снижение при переутомлении
        spo2 = max(93, min(99, spo2))

        # RPE (воспринимаемая нагрузка)
        if day_of_week < 2:
            rpe = round(3 + random.uniform(-1, 1), 0)
        elif day_of_week < 5:
            rpe = round(6 + load_factor * 2 + random.uniform(-1, 1), 0)
        else:
            rpe = round(2 + random.uniform(-1, 1), 0)
        rpe = max(1, min(10, rpe))

        row = {
            "date": date_str,
            "resting_hr": resting_hr,
            "sys_bp": sys_bp,
            "dia_bp": dia_bp,
            "mood": mood,
            "sleep_quality": sleep_quality,
            "physical_state": physical_state,
            "calories": calories,
            "weight": weight,
            "ortho_lying": ortho_lying,
            "ortho_standing": ortho_standing,
            "spo2": spo2,
            "rpe": rpe,
        }
        data.append(row)

    return data


def seed_database():
    print(f"🔗 Подключение к БД: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print("❌ Файл БД не найден. Сначала запусти приложение один раз.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Очищаем существующие данные
        print("🗑️ Очистка существующих данных...")
        conn.execute("DELETE FROM daily_logs")

        # Генерируем данные
        print("📊 Генерация тестовых данных за 60 дней...")
        test_data = generate_test_data(60)

        # Вставляем данные
        for row in test_data:
            cols = list(row.keys())
            placeholders = ", ".join(["?"] * len(cols))
            values = [row[c] for c in cols]

            conn.execute(f"""
                INSERT INTO daily_logs ({", ".join(cols)}) 
                VALUES ({placeholders})
            """, values)

        conn.commit()

        # Статистика
        result = conn.execute("SELECT COUNT(*) as cnt FROM daily_logs").fetchone()["cnt"]
        print(f"✅ Добавлено {result} записей")

        # Показываем последние 5 записей
        print("\n📋 Последние 5 записей:")
        print("-" * 100)
        rows = conn.execute("""
            SELECT date, resting_hr, sys_bp, sleep_quality, mood, calories, rpe 
            FROM daily_logs 
            ORDER BY date DESC 
            LIMIT 5
        """).fetchall()
        for row in rows:
            print(f"  {row['date']} | ЧСС: {row['resting_hr']} | АД: {row['sys_bp']} | "
                  f"Сон: {row['sleep_quality']} | Настр: {row['mood']} | Ккал: {row['calories']} | RPE: {row['rpe']}")

        # Показываем первые 5 записей
        print("\n📋 Первые 5 записей:")
        print("-" * 100)
        rows = conn.execute("""
            SELECT date, resting_hr, sys_bp, sleep_quality, mood, calories, rpe 
            FROM daily_logs 
            ORDER BY date ASC 
            LIMIT 5
        """).fetchall()
        for row in rows:
            print(f"  {row['date']} | ЧСС: {row['resting_hr']} | АД: {row['sys_bp']} | "
                  f"Сон: {row['sleep_quality']} | Настр: {row['mood']} | Ккал: {row['calories']} | RPE: {row['rpe']}")

        print("\n🎯 Теперь открой приложение и проверь:")
        print("  1. Вкладка 'Дашборд' — переключи период на 'Месяц' и 'Год'")
        print("  2. Графики должны показывать 60 дней данных")
        print("  3. Вкладка 'Рекомендации' — должны появиться разные алерты")
        print("  4. Вкладка 'Настройки' — таблица должна показать все 60 записей")
        print("  5. Индекс CoreMetric должен колебаться в зависимости от состояния")


if __name__ == "__main__":
    seed_database()
'''
def main(page: ft.Page):
    CoreMetricApp(page)
def main(page: ft.Page):
    try:
        CoreMetricApp(page)
    except Exception as e:
        page.add(
            ft.Text("❌ Ошибка запуска приложения", size=20, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(f"Ошибка: {str(e)}", size=14, color=ft.Colors.RED),
            ft.Text(f"Тип: {type(e).__name__}", size=12, color=ft.Colors.GREY),
            ft.Divider(),
            ft.Text("Traceback:", size=12, weight=ft.FontWeight.BOLD),
            ft.Text(traceback.format_exc(), size=10, color=ft.Colors.GREY),
        )
        page.update()'''