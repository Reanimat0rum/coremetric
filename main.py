import flet as ft

def main(page: ft.Page):
    page.title = "CoreMetric Test"
    page.padding = 20
    page.add(
        ft.Text("✅ Flet работает!", size=24, color=ft.Colors.GREEN),
        ft.ElevatedButton("Тест", on_click=lambda e: page.add(ft.Text("OK"))),
    )

ft.app(target=main)