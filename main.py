import flet as ft
from datetime import date, datetime, timedelta
import db, analytics, i18n, test_data
import pandas as pd
import numpy as np

METRIC_KEYS = [
    "coremetric_index", "readiness", "acwr", "monotony", "orthostatic_index",
    "resting_hr", "sys_bp", "dia_bp", "mood", "sleep_quality",
    "physical_state", "calories", "weight", "ortho_lying", "ortho_standing",
    "spo2", "rpe",
]

METRIC_REFS = {
    "coremetric_index": "<40 низкий | 40-70 норма | >70 высокий",
    "readiness": "<40 низкая | 40-70 умеренная | >70 высокая",
    "acwr": "<0.5 риск | 0.5-0.8 низкая | 0.8-1.3 оптимум | 1.3-1.5 повышен | >1.5 высокий риск",
    "monotony": "<1.5 хорошо | 1.5-2.0 умеренно | >2.0 риск OTS",
    "orthostatic_index": "<5% низкий | 5-10% погран. | 10-20% оптимум | 20-28% погран. | >28% высокий",
    "resting_hr": "<50 низкий | 50-75 оптимум | 75-90 повышен | >90 высокий",
    "sys_bp": "<110 низкое | 110-130 оптимум | 130-140 повышенное | >140 высокое",
    "dia_bp": "<70 низкое | 70-85 оптимум | 85-90 повышенное | >90 высокое",
    "mood": "<30 низкое | 30-50 умеренное | 50-75 хорошее | >75 отличное",
    "sleep_quality": "<30 критично | 30-60 низкое | 60-80 норма | >80 отличное",
    "physical_state": "<40 низкое | 40-60 умеренное | 60-80 хорошее | >80 отличное",
    "calories": "зависит от целей",
    "weight": "индивидуально",
    "ortho_lying": "индивидуально",
    "ortho_standing": "индивидуально",
    "spo2": "<92 критично | 92-96 низкая | 96-99 норма | 99-100 отличная",
    "rpe": "1-3 лёгкая | 4-6 умеренная | 7-8 тяжёлая | 9-10 максимальная",
}


class CoreMetricApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.lang = db.get_setting("lang") or "ru"
        self.theme = db.get_setting("theme") or "light"
        self.page.title = "CoreMetric"
        self.page.theme_mode = ft.ThemeMode.DARK if self.theme == "dark" else ft.ThemeMode.LIGHT
        self.page.padding = 12
        self.page.window.min_width = 400
        self.page.window.min_height = 700
        self.fields = {}
        self.chart = None
        self.rec_list = None
        self.table_data = None
        self.period_dd = None
        self.metric_dd = None
        self.index_text = None
        self.index_ref_text = None
        self.date_text = None
        self.date_picker = None
        self.ind_readiness = None
        self.ind_acwr = None
        self.ind_monotony = None
        self.ind_ortho = None
        self.zoom_factor = 1.0
        self.zoom_text = None
        self.build_ui()
        self.refresh_all()

    def t(self, key):
        return i18n.t(key, self.lang)

    def build_ui(self):
        # --- DATE PICKER ---
        self.date_picker = ft.DatePicker(
            first_date=datetime.now() - timedelta(days=365),
            last_date=datetime.now() + timedelta(days=365),
            current_date=datetime.now(),
        )
        self.date_picker.on_change = self._on_date_changed
        self.page.overlay.append(self.date_picker)
        self.date_text = ft.Text(date.today().isoformat(), size=14, weight=ft.FontWeight.W_500)

        # --- INPUT TAB ---
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

        # --- DASHBOARD TAB ---
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
            options=[ft.dropdown.Option(k, self.t(f"metric_{k}")) for k in METRIC_KEYS],
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
        self.index_ref_text = ft.Text(METRIC_REFS["coremetric_index"], size=10, color=ft.Colors.GREY_600, italic=True)

        self.ind_readiness = self._make_indicator_card("ind_readiness", "--", METRIC_REFS["readiness"])
        self.ind_acwr = self._make_indicator_card("ind_acwr", "--", METRIC_REFS["acwr"])
        self.ind_monotony = self._make_indicator_card("ind_monotony", "--", METRIC_REFS["monotony"])
        self.ind_ortho = self._make_indicator_card("ind_ortho", "--", METRIC_REFS["orthostatic_index"])

        self.zoom_text = ft.Text("1.0x", size=14, weight=ft.FontWeight.BOLD)
        zoom_controls = ft.Row([
            ft.Text(" Масштаб Y:", size=12),
            ft.IconButton(ft.Icons.ZOOM_OUT, on_click=self._zoom_out, tooltip="Уменьшить"),
            self.zoom_text,
            ft.IconButton(ft.Icons.ZOOM_IN, on_click=self._zoom_in, tooltip="Увеличить"),
            ft.IconButton(ft.Icons.FIT_SCREEN, on_click=self._zoom_reset, tooltip="Сбросить"),
        ], spacing=4)

        self.tab_dashboard = ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text(self.t("index_label"), size=12, color=ft.Colors.GREY_600),
                    self.index_text,
                    self.index_ref_text,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                padding=16, border=ft.border.all(2, ft.Colors.BLUE_GREY_200), border_radius=12,
            ),
            ft.Row([self.ind_readiness, self.ind_acwr], spacing=8, wrap=True),
            ft.Row([self.ind_monotony, self.ind_ortho], spacing=8, wrap=True),
            ft.Row([ft.Text(self.t("period")), self.period_dd, ft.Text(self.t("metric")), self.metric_dd], wrap=True),
            zoom_controls,
            self.chart,
        ], scroll=ft.ScrollMode.AUTO, spacing=10)

        # --- RECOMMENDATIONS TAB ---
        self.rec_list = ft.ListView(height=600, spacing=10, padding=10)
        self.tab_recs = ft.Column([self.rec_list], scroll=ft.ScrollMode.AUTO)

        # --- SETTINGS TAB ---
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
            ft.ElevatedButton(self.t("btn_backup"), on_click=self.do_backup),
            ft.ElevatedButton(self.t("btn_csv"), on_click=self.do_export),
            ft.ElevatedButton(
                "🧪 Создать тестовые данные",
                icon=ft.Icons.SCIENCE,
                on_click=self.do_seed_test_data,
            ),
            ft.ElevatedButton(self.t("btn_clear"), color=ft.Colors.RED, on_click=self.clear_db),
            ft.Divider(),
            ft.Text("History", size=14, weight=ft.FontWeight.BOLD),
            ft.Container(content=self.table_data, height=250),
        ], scroll=ft.ScrollMode.AUTO, spacing=8)

        # --- TABS ---
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

    def _make_indicator_card(self, title_key, value, ref_text):
        title_txt = ft.Text(self.t(title_key), size=11, color=ft.Colors.GREY_600)
        value_txt = ft.Text(value, size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY)
        ref_txt = ft.Text(ref_text, size=9, color=ft.Colors.GREY_500, italic=True)
        return ft.Container(
            content=ft.Column(
                [title_txt, value_txt, ref_txt],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border=ft.border.all(1, ft.Colors.GREY_300), border_radius=8,
            width=180,
            data={"title": title_txt, "value": value_txt, "ref": ref_txt},
        )

    def _update_indicator(self, card, value, color=ft.Colors.GREY):
        if card is None:
            return
        value_txt = card.data["value"]
        value_txt.value = str(value)
        value_txt.color = color
        try:
            card.update()
        except Exception:
            pass

    def _on_date_changed(self, e):
        if self.date_picker.value:
            val = self.date_picker.value
            if isinstance(val, (datetime, date)):
                self.date_text.value = val.strftime("%Y-%m-%d")
            else:
                self.date_text.value = str(val)[:10]
            self.page.update()

    def _on_period_or_metric_changed(self, e):
        self.update_dashboard()
        self.update_chart()
        self.page.update()

    def _zoom_in(self, e):
        self.zoom_factor = max(0.25, self.zoom_factor / 1.5)
        self.zoom_text.value = f"{self.zoom_factor:.2f}x"
        self.update_chart()
        self.page.update()

    def _zoom_out(self, e):
        self.zoom_factor = min(4.0, self.zoom_factor * 1.5)
        self.zoom_text.value = f"{self.zoom_factor:.2f}x"
        self.update_chart()
        self.page.update()

    def _zoom_reset(self, e):
        self.zoom_factor = 1.0
        self.zoom_text.value = "1.00x"
        self.update_chart()
        self.page.update()

    def on_save(self, e):
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
        self.update_dashboard()
        self.update_chart()
        self.update_recommendations()
        self.update_table()
        self.page.update()

    def update_dashboard(self):
        df = analytics.load_df(180)
        if df.empty:
            self._reset_indicators()
            return
        df = analytics.enrich_df(df)
        period = self.period_dd.value if self.period_dd else "D"
        agg = df.resample(period).mean()
        if agg.empty:
            self._reset_indicators()
            return
        last = agg.iloc[-1]
        idx = last.get("coremetric_index", np.nan)
        if pd.notna(idx):
            self.index_text.value = f"{idx:.1f}"
            self.index_text.color = (
                ft.Colors.GREEN if idx > 70
                else ft.Colors.RED if idx < 40
                else ft.Colors.AMBER
            )
        else:
            self.index_text.value = "--"
            self.index_text.color = ft.Colors.GREY

        rd = last.get("readiness", np.nan)
        self._update_indicator(
            self.ind_readiness,
            f"{rd:.1f}" if pd.notna(rd) else "--",
            ft.Colors.GREEN if pd.notna(rd) and rd > 70 else ft.Colors.RED if pd.notna(
                rd) and rd < 40 else ft.Colors.GREY
        )
        acwr = last.get("acwr", np.nan)
        if pd.notna(acwr):
            acwr_color = ft.Colors.GREEN if 0.8 <= acwr <= 1.3 else ft.Colors.RED if acwr > 1.5 or acwr < 0.5 else ft.Colors.AMBER
            self._update_indicator(self.ind_acwr, f"{acwr:.2f}", acwr_color)
        else:
            self._update_indicator(self.ind_acwr, "--")
        mono = last.get("monotony", np.nan)
        if pd.notna(mono):
            mono_color = ft.Colors.GREEN if mono < 1.5 else ft.Colors.AMBER if mono < 2.0 else ft.Colors.RED
            self._update_indicator(self.ind_monotony, f"{mono:.2f}", mono_color)
        else:
            self._update_indicator(self.ind_monotony, "--")
        ortho = last.get("orthostatic_index", np.nan)
        if pd.notna(ortho):
            ortho_color = ft.Colors.GREEN if 10 <= ortho <= 20 else ft.Colors.AMBER if 5 <= ortho < 10 or 20 < ortho <= 28 else ft.Colors.RED
            self._update_indicator(self.ind_ortho, f"{ortho:.1f}%", ortho_color)
        else:
            self._update_indicator(self.ind_ortho, "--")

    def _reset_indicators(self):
        self.index_text.value = "--"
        self.index_text.color = ft.Colors.GREY
        for card in [self.ind_readiness, self.ind_acwr, self.ind_monotony, self.ind_ortho]:
            self._update_indicator(card, "--")

    def update_chart(self, e=None):
        df = analytics.load_df(180)
        if df.empty or not self.period_dd or not self.metric_dd:
            self.chart.data_series = []
            self.chart.bottom_axis.labels = []
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
            self.chart.bottom_axis.labels = []
            self.page.update()
            return
        agg_valid.index = agg_valid.index.strftime("%Y-%m-%d")

        pts = []
        values = []
        for i, (idx, row) in enumerate(agg_valid.iterrows()):
            v = row[metric]
            if pd.notna(v):
                rounded = round(float(v), 1)
                # ✅ Tooltip с датой и значением (без кавычек и кириллицы)
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

        center_y = (min_v + max_v) / 2
        half_range = (max_v - min_v) / 2 + base_margin
        new_half_range = half_range * self.zoom_factor

        self.chart.min_y = center_y - new_half_range
        self.chart.max_y = center_y + new_half_range
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
                # ✅ Добавлен уровень "missing" — серый цвет
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
                ref_text = self._get_ref_for_recommendation(r["title"])
                controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text(r["title"], weight=ft.FontWeight.BOLD, size=15, color=text_color),
                        ft.Text(r["text"], color=text_color),
                        ft.Text(actions, size=12, color=text_color),
                        ft.Divider(color=border_color),
                        ft.Text(f"{self.t('rec_src')} {sources}", size=10,
                                color=ft.Colors.GREY_400 if is_dark else ft.Colors.GREY_600, italic=True),
                        ft.Text(ref_text, size=10, color=ft.Colors.GREY_500, italic=True) if ref_text else ft.Container(
                            height=0),
                    ]),
                    padding=12, border_radius=8, border=ft.border.all(1, border_color), bgcolor=bg,
                ))
        self.rec_list.controls = controls
        self.page.update()

    def _get_ref_for_recommendation(self, title):
        title_lower = title.lower()
        if "чсс" in title_lower or "тахикард" in title_lower:
            return "Референс: <50 низкий | 50-75 оптимум | 75-90 повышен | >90 высокий"
        if "ад" in title_lower or "давлен" in title_lower:
            return "Референс: <110/70 низкое | 110-130/70-85 оптимум | 130-140/85-90 повышенное | >140/90 высокое"
        if "сон" in title_lower:
            return "Референс: <30 критично | 30-60 низкое | 60-80 норма | >80 отличное"
        if "настроен" in title_lower or "настроени" in title_lower:
            return "Референс: <30 низкое | 30-50 умеренное | 50-75 хорошее | >75 отличное"
        if "сатурац" in title_lower or "spo" in title_lower.lower():
            return "Референс: <92 критично | 92-96 низкая | 96-99 норма | 99-100 отличная"
        if "acwr" in title_lower:
            return "Референс: <0.5 риск | 0.5-0.8 низкая | 0.8-1.3 оптимум | 1.3-1.5 повышен | >1.5 высокий риск"
        if "монотонн" in title_lower:
            return "Референс: <1.5 хорошо | 1.5-2.0 умеренно | >2.0 риск OTS"
        if "ортост" in title_lower:
            return "Референс: <5% низкий | 5-10% погран. | 10-20% оптимум | 20-28% погран. | >28% высокий"
        if "готовност" in title_lower or "readiness" in title_lower:
            return "Референс: <40 низкая | 40-70 умеренная | >70 высокая"
        if "самочувств" in title_lower or "физич" in title_lower:
            return "Референс: <40 низкое | 40-60 умеренное | 60-80 хорошее | >80 отличное"
        return ""

    def update_table(self):
        data = db.get_all(30)
        df = analytics.load_df(30)
        df = analytics.enrich_df(df) if not df.empty else df
        rows = []
        for row in data:
            idx_val = (df.loc[row["date"], "coremetric_index"]
                       if not df.empty and row["date"] in df.index else "--")
            idx_str = f"{idx_val:.1f}" if isinstance(idx_val, (int, float)) and not pd.isna(idx_val) else "--"
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(row["date"])[:10])),
                ft.DataCell(ft.Text(idx_str)),
                ft.DataCell(ft.IconButton(ft.Icons.DELETE,
                                          on_click=lambda e, d=row["date"]: self.delete_row(d))),
            ]))
        self.table_data.rows = rows
        self.page.update()

    def delete_row(self, d):
        def confirmed(e):
            db.delete_entry(d)
            dlg.open = False
            self.refresh_all()

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text(self.t("q_delete").format(d[:10])),
            actions=[
                ft.TextButton(self.t("cancel"), on_click=lambda _: self.close_dlg(dlg)),
                ft.TextButton(self.t("confirm"), on_click=confirmed),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def close_dlg(self, dlg):
        dlg.open = False
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

    def do_backup(self, e):
        path = db.create_backup()
        self.page.show_snack_bar(ft.SnackBar(ft.Text(f"{self.t('msg_backup')}\n{path}")))

    def do_seed_test_data(self, e):
        """Запускает test_data.seed_database() для заполнения БД тестовыми данными."""
        test_data.seed_database()
        self.refresh_all()
        self.page.show_snack_bar(ft.SnackBar(ft.Text("✅ Тестовые данные созданы (60 дней)")))

    def do_export(self, e):
        path = db.export_csv()
        self.page.show_snack_bar(ft.SnackBar(ft.Text(f"{self.t('msg_csv')}\n{path}")))

    def clear_db(self, e):
        def confirmed(e):
            db.clear_all()
            dlg.open = False
            self.zoom_factor = 1.0
            if self.zoom_text:
                self.zoom_text.value = "1.00x"
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


def main(page: ft.Page):
    CoreMetricApp(page)


ft.app(target=main)