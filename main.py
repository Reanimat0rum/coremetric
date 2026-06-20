import flet as ft
import traceback
import os
import sys

# Логирование в файл
LOG_PATH = "/data/user/0/com.flet.coremetric/files/flet/app/startup.log"


def log(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"{msg}\n")
    except:
        pass


log("=" * 50)
log("CoreMetric starting...")

try:
    log("Step 1: Importing db...")
    import db

    log(f"Step 1 OK. APP_DIR={db.APP_DIR}")
except Exception as e:
    log(f"Step 1 FAILED: {e}")


    def main(page: ft.Page):
        page.add(ft.Text(f" Error importing db:\n{e}", color=ft.Colors.RED))


    ft.app(target=main)
    sys.exit(1)

try:
    log("Step 2: Importing analytics...")
    import analytics

    log("Step 2 OK")
except Exception as e:
    log(f"Step 2 FAILED: {e}")


    def main(page: ft.Page):
        page.add(ft.Text(f"❌ Error importing analytics:\n{e}", color=ft.Colors.RED))


    ft.app(target=main)
    sys.exit(1)

try:
    log("Step 3: Importing i18n...")
    import i18n

    log("Step 3 OK")
except Exception as e:
    log(f"Step 3 FAILED: {e}")


    def main(page: ft.Page):
        page.add(ft.Text(f"❌ Error importing i18n:\n{e}", color=ft.Colors.RED))


    ft.app(target=main)
    sys.exit(1)

try:
    log("Step 4: Importing test_data...")
    import test_data

    log("Step 4 OK")
except Exception as e:
    log(f"Step 4 FAILED: {e}")


    def main(page: ft.Page):
        page.add(ft.Text(f" Error importing test_data:\n{e}", color=ft.Colors.RED))


    ft.app(target=main)
    sys.exit(1)

log("Step 5: Defining CoreMetricApp...")


class CoreMetricApp:
    def __init__(self, page: ft.Page):
        log("CoreMetricApp.__init__ starting...")
        self.page = page
        self.lang = db.get_setting("lang") or "ru"
        self.theme = db.get_setting("theme") or "light"
        self.page.title = "CoreMetric"
        self.page.theme_mode = ft.ThemeMode.DARK if self.theme == "dark" else ft.ThemeMode.LIGHT
        self.page.padding = 12
        self.page.window.min_width = 400
        self.page.window.min_height = 700
        log("CoreMetricApp.__init__ OK")
        self.build_ui()
        self.refresh_all()

    def t(self, key):
        return i18n.t(key, self.lang)

    def build_ui(self):
        log("build_ui starting...")
        from datetime import date, datetime, timedelta

        self.date_picker = ft.DatePicker(
            first_date=datetime.now() - timedelta(days=365),
            last_date=datetime.now() + timedelta(days=365),
            current_date=datetime.now(),
        )
        self.date_picker.on_change = self._on_date_changed
        self.page.overlay.append(self.date_picker)
        self.date_text = ft.Text(date.today().isoformat(), size=14, weight=ft.FontWeight.W_500)

        input_defs = [
            ("input_hr", "resting_hr"), ("input_sys", "sys_bp"), ("input_dia", "dia_bp"),
            ("input_mood", "mood"), ("input_sleep", "sleep_quality"), ("input_phys", "physical_state"),
            ("input_cal", "calories"), ("input_wt", "weight"),
            ("input_hr_lying", "ortho_lying"), ("input_hr_stand", "ortho_standing"),
            ("input_spo2", "spo2"), ("input_rpe", "rpe"),
        ]
        self.fields = {}
        input_controls = [
            ft.Row([
                ft.ElevatedButton("📅", on_click=lambda _: self.date_picker.pick_date(), width=60),
                self.date_text,
            ], alignment=ft.MainAxisAlignment.START)
        ]
        for label_key, db_key in input_defs:
            tf = ft.TextField(label=self.t(label_key), keyboard_type=ft.KeyboardType.NUMBER, hint_text="0")
            self.fields[db_key] = tf
            input_controls.append(tf)
        input_controls.append(
            ft.ElevatedButton(self.t("btn_save"), icon=ft.Icons.SAVE, on_click=self.on_save, width=300)
        )
        self.tab_input = ft.Column(input_controls, scroll=ft.ScrollMode.AUTO, spacing=8)
        log("build_ui input tab OK")

        self.period_dd = ft.Dropdown(
            options=[
                ft.dropdown.Option("D", self.t("d")),
                ft.dropdown.Option("W", self.t("w")),
                ft.dropdown.Option("ME", self.t("m")),
                ft.dropdown.Option("YE", self.t("y")),
            ],
            value="D", width=120, on_change=self._on_period_or_metric_changed,
        )
        self.metric_dd = ft.Dropdown(
            options=[ft.dropdown.Option(k, self.t(f"metric_{k}")) for k in
                     ["coremetric_index", "readiness", "resting_hr", "sys_bp", "sleep_quality"]],
            value="coremetric_index", width=220, on_change=self._on_period_or_metric_changed,
        )

        self.chart = ft.LineChart(
            data_series=[], min_x=0, max_x=30, min_y=0, max_y=100,
            horizontal_grid_lines=ft.ChartGridLines(width=1, color=ft.Colors.GREY_400),
            vertical_grid_lines=ft.ChartGridLines(width=1, color=ft.Colors.GREY_300),
            bottom_axis=ft.ChartAxis(labels=[]),
            left_axis=ft.ChartAxis(labels_size=40),
            width=500, height=350,
        )

        self.index_text = ft.Text("--", size=36, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY)

        self.tab_dashboard = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text(self.t("index_label"), size=12, color=ft.Colors.GREY_600),
                    self.index_text,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                padding=16, border=ft.border.all(2, ft.Colors.BLUE_GREY_200), border_radius=12,
            ),
            ft.Row([ft.Text(self.t("period")), self.period_dd, ft.Text(self.t("metric")), self.metric_dd], wrap=True),
            self.chart,
        ], scroll=ft.ScrollMode.AUTO, spacing=10)
        log("build_ui dashboard tab OK")

        self.rec_list = ft.ListView(height=600, spacing=10, padding=10)
        self.tab_recs = ft.Column([self.rec_list], scroll=ft.ScrollMode.AUTO)

        self.theme_switch = ft.Switch(
            label=self.t("theme_dark"), value=(self.theme == "dark"), on_change=self.toggle_theme
        )
        self.lang_dd = ft.Dropdown(
            options=[ft.dropdown.Option("ru", "Русский"), ft.dropdown.Option("en", "English")],
            value=self.lang, width=150, on_change=self.change_lang,
        )
        self.table_data = ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text("Date")),
                ft.DataColumn(label=ft.Text("Index")),
                ft.DataColumn(label=ft.Text("")),
            ],
            column_spacing=8,
        )
        self.tab_settings = ft.Column([
            self.theme_switch,
            ft.Row([ft.Text(self.t("lang")), self.lang_dd]),
            ft.ElevatedButton("🧪 Создать тестовые данные", icon=ft.Icons.SCIENCE, on_click=self.do_seed_test_data),
            ft.ElevatedButton(self.t("btn_clear"), color=ft.Colors.RED, on_click=self.clear_db),
        ], scroll=ft.ScrollMode.AUTO, spacing=8)
        log("build_ui settings tab OK")

        self.tabs = ft.Tabs(
            selected_index=0, animation_duration=300,
            tabs=[
                ft.Tab(text=self.t("tab_input"), content=self.tab_input),
                ft.Tab(text=self.t("tab_dashboard"), content=self.tab_dashboard),
                ft.Tab(text=self.t("tab_recs"), content=self.tab_recs),
                ft.Tab(text=self.t("tab_settings"), content=self.tab_settings),
            ],
        )
        self.page.add(self.tabs)
        log("build_ui OK")

    def _on_date_changed(self, e):
        if self.date_picker.value:
            val = self.date_picker.value
            from datetime import datetime, date
            if isinstance(val, (datetime, date)):
                self.date_text.value = val.strftime("%Y-%m-%d")
            else:
                self.date_text.value = str(val)[:10]
            self.page.update()

    def _on_period_or_metric_changed(self, e):
        self.update_chart()
        self.page.update()

    def on_save(self, e):
        from datetime import date, datetime
        if self.date_picker.value:
            val = self.date_picker.value
            if isinstance(val, (datetime, date)):
                date_str = val.strftime("%Y-%m-%d")
            else:
                date_str = str(val)[:10]
        else:
            date_str = date.today().isoformat()
        self.date_text.value = date_str
        data = {"date": date_str}
        for k, tf in self.fields.items():
            val = tf.value.strip() if tf.value else ""
            data[k] = float(val) if val else None
        db.upsert_entry(data)
        self.page.show_snack_bar(ft.SnackBar(ft.Text(self.t("msg_saved"))))
        for tf in self.fields.values():
            tf.value = ""
        self.page.update()
        self.refresh_all()

    def refresh_all(self):
        log("refresh_all starting...")
        self.update_chart()
        self.update_recommendations()
        self.page.update()
        log("refresh_all OK")

    def update_chart(self, e=None):
        import pandas as pd
        import numpy as np
        df = analytics.load_df(180)
        if df.empty or not self.period_dd or not self.metric_dd:
            self.chart.data_series = []
            self.page.update()
            return
        df = analytics.enrich_df(df)
        period = self.period_dd.value
        metric = self.metric_dd.value
        if metric not in df.columns:
            self.chart.data_series = []
            self.page.update()
            return
        agg = df.resample(period).mean()
        agg_valid = agg.dropna(subset=[metric])
        if agg_valid.empty:
            self.chart.data_series = []
            self.page.update()
            return
        agg_valid.index = agg_valid.index.strftime("%Y-%m-%d")

        pts = []
        values = []
        for i, (idx, row) in enumerate(agg_valid.iterrows()):
            v = row[metric]
            if pd.notna(v):
                rounded = round(float(v), 1)
                tooltip_text = f"{idx}: {rounded}"
                pts.append(ft.LineChartDataPoint(i, rounded, tooltip=tooltip_text))
                values.append(rounded)

        if not pts:
            self.chart.data_series = []
            self.page.update()
            return

        min_v = min(values)
        max_v = max(values)
        base_margin = max((max_v - min_v) * 0.15, 1.0)
        self.chart.min_y = min_v - base_margin
        self.chart.max_y = max_v + base_margin
        self.chart.min_x = 0
        self.chart.max_x = max(30, len(pts))

        self.chart.data_series = [
            ft.LineChartData(data_points=pts, stroke_width=3, color=ft.Colors.BLUE, curved=True)
        ]
        step = max(1, len(agg_valid) // 10)
        self.chart.bottom_axis.labels = [
            ft.ChartAxisLabel(value=i, label=ft.Text(row[0][5:], size=9, rotate=45))
            for i, row in enumerate(agg_valid.iterrows()) if i % step == 0
        ]
        self.page.update()

    def update_recommendations(self):
        df = analytics.load_df(90)
        df = analytics.enrich_df(df)
        recs = analytics.generate_detailed_recommendations(df)
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK
        controls = []
        if not recs:
            controls.append(ft.Text(
                self.t("rec_empty"), italic=True,
                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600,
            ))
        else:
            for r in recs:
                if r["level"] == "missing":
                    bg = ft.Colors.GREY_200 if not is_dark else ft.Colors.GREY_800
                    text_color = ft.Colors.GREY_700 if not is_dark else ft.Colors.GREY_300
                    border_color = ft.Colors.GREY_400 if not is_dark else ft.Colors.GREY_600
                elif not is_dark:
                    bg = (ft.Colors.RED_100 if r["level"] == "danger" else
                          ft.Colors.AMBER_100 if r["level"] == "warning" else
                          ft.Colors.GREEN_100 if r["level"] == "success" else ft.Colors.BLUE_100)
                    text_color = (ft.Colors.RED_900 if r["level"] == "danger" else
                                  ft.Colors.AMBER_900 if r["level"] == "warning" else
                                  ft.Colors.GREEN_900 if r["level"] == "success" else ft.Colors.BLUE_900)
                    border_color = (ft.Colors.RED_300 if r["level"] == "danger" else
                                    ft.Colors.AMBER_300 if r["level"] == "warning" else
                                    ft.Colors.GREEN_300 if r["level"] == "success" else ft.Colors.BLUE_300)
                else:
                    bg = (ft.Colors.RED_900 if r["level"] == "danger" else
                          ft.Colors.AMBER_900 if r["level"] == "warning" else
                          ft.Colors.GREEN_900 if r["level"] == "success" else ft.Colors.BLUE_900)
                    text_color = (ft.Colors.RED_50 if r["level"] == "danger" else
                                  ft.Colors.AMBER_50 if r["level"] == "warning" else
                                  ft.Colors.GREEN_50 if r["level"] == "success" else ft.Colors.BLUE_50)
                    border_color = (ft.Colors.RED_700 if r["level"] == "danger" else
                                    ft.Colors.AMBER_700 if r["level"] == "warning" else
                                    ft.Colors.GREEN_700 if r["level"] == "success" else ft.Colors.BLUE_700)
                actions = "\n".join([f"• {a}" for a in r["actions"]])
                sources = "\n".join([f"- {s}" for s in r["sources"]])
                controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text(r["title"], weight=ft.FontWeight.BOLD, size=15, color=text_color),
                        ft.Text(r["text"], color=text_color),
                        ft.Text(actions, size=12, color=text_color),
                        ft.Divider(color=border_color),
                        ft.Text(f"{self.t('rec_src')} {sources}", size=10,
                                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600, italic=True),
                    ]),
                    padding=12, border_radius=8, border=ft.border.all(1, border_color), bgcolor=bg,
                ))
        self.rec_list.controls = controls
        self.page.update()

    def toggle_theme(self, e):
        self.theme = "dark" if e.control.value else "light"
        db.set_setting("theme", self.theme)
        self.page.theme_mode = ft.ThemeMode.DARK if self.theme == "dark" else ft.ThemeMode.LIGHT
        self.update_recommendations()
        self.page.update()

    def change_lang(self, e):
        self.lang = e.control.value
        db.set_setting("lang", self.lang)
        self.page.controls.clear()
        self.page.overlay.clear()
        self.build_ui()
        self.refresh_all()

    def do_seed_test_data(self, e):
        test_data.seed_database()
        self.refresh_all()
        self.page.show_snack_bar(ft.SnackBar(ft.Text("✅ Тестовые данные созданы (60 дней)")))

    def clear_db(self, e):
        def confirmed(e):
            db.clear_all()
            dlg.open = False
            self.refresh_all()
            self.page.show_snack_bar(ft.SnackBar(ft.Text(self.t("msg_cleared"))))

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text(self.t("q_clear")),
            actions=[
                ft.TextButton(self.t("cancel"), on_click=lambda _: self.close_dlg(dlg)),
                ft.TextButton(
                    self.t("confirm"),
                    style=ft.ButtonStyle(color=ft.Colors.RED),
                    on_click=confirmed,
                ),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def close_dlg(self, dlg):
        dlg.open = False
        self.page.update()


log("Step 6: Defining main()...")


def main(page: ft.Page):
    log("main() called")
    try:
        CoreMetricApp(page)
        log("CoreMetricApp created successfully")
    except Exception as e:
        log(f"Error in main(): {e}")
        page.add(
            ft.Text("❌ Ошибка запуска", size=20, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(f"Ошибка: {str(e)}", size=14, color=ft.Colors.RED),
            ft.Text(f"Тип: {type(e).__name__}", size=12, color=ft.Colors.GREY),
            ft.Divider(),
            ft.Text("Traceback:", size=12, weight=ft.FontWeight.BOLD),
            ft.Text(traceback.format_exc(), size=10, color=ft.Colors.GREY),
        )
        page.update()


log("Step 7: Calling ft.app()...")
ft.app(target=main)
log("ft.app() returned")