import flet as ft
import db  # <- Это импортирует pandas, numpy и создаст БД


def main(page: ft.Page):
    page.title = "CoreMetric Test"
    page.padding = 20

    # Проверяем, что БД создалась
    db_status = "ОК" if os.path.exists(db.DB_PATH) else "ОШИБКА"

    page.add(
        ft.Text("✅ Зависимости и БД работают!", size=24, color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        ft.Text(f"Путь к БД: {db.DB_PATH}", size=12, color=ft.Colors.GREY),
        ft.Text(f"Статус БД: {db_status}", size=14, color=ft.Colors.GREEN if db_status == "ОК" else ft.Colors.RED),
        ft.Divider(),
        ft.ElevatedButton(
            "Проверить запись в БД",
            icon=ft.Icons.SAVE,
            on_click=lambda e: check_db_write(page)
        ),
    )


def check_db_write(page):
    try:
        # Пробуем записать тестовую запись
        db.upsert_entry({"date": "2026-06-20", "resting_hr": 65.0})
        data = db.get_all()
        page.add(ft.Text(f"✅ Успешно записано! Всего записей в БД: {len(data)}", color=ft.Colors.BLUE))
    except Exception as e:
        page.add(ft.Text(f"❌ Ошибка записи: {e}", color=ft.Colors.RED))


import os

ft.app(target=main)