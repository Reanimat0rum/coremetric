import flet as ft


def main(page: ft.Page):
    page.title = "CoreMetric Minimal"
    page.padding = 20

    page.add(
        ft.Text("✅ Flet работает на Android!", size=24, color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        ft.Text("Это минимальный тест без зависимостей", size=14),
        ft.Text(f"Версия Flet: {ft.__version__ if hasattr(ft, '__version__') else 'unknown'}", size=12,
                color=ft.Colors.GREY),
        ft.Divider(),
        ft.ElevatedButton(
            "Нажми меня",
            icon=ft.Icons.CHECK,
            on_click=lambda e: page.add(ft.Text("Кнопка работает!", color=ft.Colors.BLUE))
        ),
    )


ft.app(target=main)