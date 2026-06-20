import flet as ft
import os

# Логируем в Downloads (доступно на Android)
LOG_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "coremetric_log.txt")


def log(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"{msg}\n")
    except:
        pass


log("=" * 50)
log("Simple test starting...")


def main(page: ft.Page):
    log("main() called")

    try:
        page.title = "CoreMetric Test"
        page.add(
            ft.Text("✅ Приложение запустилось!", size=24, color=ft.Colors.GREEN),
            ft.Divider(),
            ft.Text(f"Путь к Downloads: {os.path.expanduser('~')}/Downloads", size=14),
            ft.Text(f"Лог записан в: {LOG_PATH}", size=12, color=ft.Colors.GREY),
        )
        log("UI created successfully")
    except Exception as e:
        log(f"Error: {e}")
        page.add(ft.Text(f"❌ Ошибка: {e}", color=ft.Colors.RED))


log("Calling ft.app()...")
ft.app(target=main)
log("Done")