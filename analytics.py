import pandas as pd
import numpy as np
import db

pd.set_option('future.no_silent_downcasting', True)

WEIGHTS = {
    "resting_hr": -0.18, "sys_bp": -0.07, "dia_bp": -0.07,
    "sleep_quality": 0.18, "mood": 0.12, "physical_state": 0.10,
    "spo2": 0.10, "rpe": -0.08,
}

THRESHOLDS = {
    "resting_hr": {"low_crit": 30, "high_warn": 80, "high_crit": 90, "low_normal": 50, "high_normal": 75},
    "sys_bp": {"high_warn": 135, "high_crit": 140, "low_normal": 110, "high_normal": 130},
    "dia_bp": {"high_warn": 85, "high_crit": 90, "low_normal": 70, "high_normal": 85},
    "sleep_quality": {"low_warn": 40, "low_crit": 30, "low_normal": 60, "high_normal": 80},
    "mood": {"low_warn": 30, "low_crit": 20, "low_normal": 50, "high_normal": 75},
    "spo2": {"low_warn": 95, "low_crit": 92, "low_normal": 96, "high_normal": 99},
    "weight": {"change_warn": 1.0},
    "physical_state": {"low_warn": 40, "low_normal": 60, "high_normal": 80},
}


def load_df(days=90):
    data = db.get_all(days)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)
    return df


def calc_acwr(df):
    load = df["calories"] if "calories" in df.columns and df["calories"].notna().any() else (
        df["rpe"] if "rpe" in df.columns and df["rpe"].notna().any() else None
    )
    if load is None:
        return pd.Series(dtype=float)
    acute = load.rolling(7, min_periods=3).mean()
    chronic = load.rolling(28, min_periods=14).mean()
    return ((acute / chronic).dropna()).round(2)


def calc_monotony(df):
    load = df["calories"] if "calories" in df.columns and df["calories"].notna().any() else (
        df["rpe"] if "rpe" in df.columns and df["rpe"].notna().any() else None
    )
    if load is None:
        return pd.Series(dtype=float)
    mean_load = load.rolling(7, min_periods=3).mean()
    std_load = load.rolling(7, min_periods=3).std().replace(0, np.nan)
    return ((mean_load / std_load).dropna()).round(2)


def calc_orthostatic_index(df):
    if "ortho_lying" not in df.columns or "ortho_standing" not in df.columns:
        return pd.Series(dtype=float)
    lying = df["ortho_lying"].replace(0, np.nan)
    standing = df["ortho_standing"]
    idx = ((standing - lying) / lying) * 100
    return idx.replace([np.inf, -np.inf], np.nan).round(1)


def calc_readiness(df):
    scores = []
    if "sleep_quality" in df.columns:
        scores.append(df["sleep_quality"].fillna(50) * 0.3)
    if "mood" in df.columns:
        scores.append(df["mood"].fillna(50) * 0.2)
    if "physical_state" in df.columns:
        scores.append(df["physical_state"].fillna(50) * 0.2)
    if "resting_hr" in df.columns:
        min_hr = df["resting_hr"].min() if df["resting_hr"].notna().any() else 60
        hr_score = (100 - (df["resting_hr"] - min_hr) * 3).clip(0, 100).fillna(50)
        scores.append(hr_score * 0.3)
    if not scores:
        return pd.Series([50], index=df.index)
    return sum(scores).round(1)


def calc_coremetric_index(df):
    if df.empty:
        return df
    cols = [c for c in WEIGHTS if c in df.columns]
    df_num = df[cols].copy()
    roll_mean = df_num.rolling(30, min_periods=7).mean()
    roll_std = df_num.rolling(30, min_periods=7).std().fillna(1).replace(0, 1)
    z = (df_num - roll_mean) / roll_std
    for c, w in WEIGHTS.items():
        if w < 0 and c in z.columns:
            z[c] *= -1
    raw = pd.Series(0.0, index=df.index)
    for c in cols:
        raw += (z[c] * WEIGHTS[c]).fillna(0)
    df["coremetric_index"] = (((raw + 1.5) / 3.0 * 100).clip(0, 100)).round(1)
    return df


def enrich_df(df):
    if df.empty:
        return df
    df = calc_coremetric_index(df)
    df["readiness"] = calc_readiness(df)
    df["acwr"] = calc_acwr(df)
    df["monotony"] = calc_monotony(df)
    df["orthostatic_index"] = calc_orthostatic_index(df)
    return df


def _safe_get(series, key, default=0):
    if key not in series.index:
        return default
    val = series[key]
    if val is None:
        return default
    if isinstance(val, float) and np.isnan(val):
        return default
    if pd.isna(val):
        return default
    return val


def check_missing_data(df):
    """Проверяет, каких данных не хватает для расчёта индексов."""
    recs = []

    # Если данных очень мало — общее сообщение
    if df.empty or len(df) < 3:
        recs.append({
            "level": "missing",
            "title": "📊 Недостаточно данных для анализа",
            "text": f"В базе всего {len(df)} записей. Для полноценного анализа рекомендуется вести дневник минимум 30 дней.",
            "actions": [
                "Ежедневно заполняйте поля на вкладке 'Ввод'",
                "Особое внимание: ЧСС покоя, качество сна, настроение, калории или RPE"
            ],
            "sources": ["CoreMetric"]
        })
        return recs

    # ACWR требует 14 дней chronic
    cal_count = df["calories"].notna().sum() if "calories" in df.columns else 0
    rpe_count = df["rpe"].notna().sum() if "rpe" in df.columns else 0
    has_acwr = cal_count >= 14 or rpe_count >= 14
    if not has_acwr:
        recs.append({
            "level": "missing",
            "title": "⚖️ Недостаточно данных для ACWR",
            "text": f"Для расчёта ACWR требуется минимум 14 дней данных о нагрузке. Сейчас заполнено: калории={cal_count} дн., RPE={rpe_count} дн.",
            "actions": [
                "Ежедневно указывайте калории или RPE (воспринимаемую нагрузку)",
                "ACWR покажет соотношение острой и хронической нагрузки"
            ],
            "sources": ["Gabbett TJ. BJSM 2016"]
        })

    # Monotony требует 7 дней
    has_mono = cal_count >= 7 or rpe_count >= 7
    if not has_mono:
        recs.append({
            "level": "missing",
            "title": "🔄 Недостаточно данных для монотонности нагрузки",
            "text": "Для расчёта монотонности требуется минимум 7 дней данных о нагрузке (калории или RPE).",
            "actions": ["Заполняйте калории или RPE ежедневно в течение недели"],
            "sources": ["Foster C. JSSR 2001"]
        })

    # Orthostatic index
    has_ortho = False
    ortho_both = 0
    if "ortho_lying" in df.columns and "ortho_standing" in df.columns:
        ortho_both = (df["ortho_lying"].notna() & df["ortho_standing"].notna()).sum()
        if ortho_both >= 3:
            has_ortho = True
    if not has_ortho:
        recs.append({
            "level": "missing",
            "title": "🫀 Недостаточно данных для ортостатического индекса",
            "text": f"Для расчёта ортостатического индекса требуется заполнять оба поля: 'ЧСС лёжа' и 'ЧСС стоя' (сейчас совпадений: {ortho_both}).",
            "actions": [
                "Утром, до подъёма с кровати, измерьте ЧСС лёжа (1 минута)",
                "Затем встаньте и измерьте ЧСС стоя (1 минута)",
                "Заполните оба поля в дневнике"
            ],
            "sources": ["Sports Medicine"]
        })

    # Readiness — нужно минимум 2 из 4 ключевых полей
    key_fields = ["sleep_quality", "mood", "physical_state", "resting_hr"]
    field_names = {
        "sleep_quality": "качество сна",
        "mood": "настроение",
        "physical_state": "физ. самочувствие",
        "resting_hr": "ЧСС покоя"
    }
    available = [f for f in key_fields if f in df.columns and df[f].notna().sum() >= 3]
    if len(available) < 2:
        missing_fields = [f for f in key_fields if f not in df.columns or df[f].notna().sum() < 3]
        missing_names = ", ".join([field_names.get(f, f) for f in missing_fields])
        available_names = ", ".join([field_names.get(f, f) for f in available]) or "ничего"
        recs.append({
            "level": "missing",
            "title": "💪 Недостаточно данных для индекса готовности",
            "text": f"Для расчёта индекса готовности заполните хотя бы 2 из 4 ключевых полей. Сейчас заполнены: {available_names}. Не хватает: {missing_names}.",
            "actions": [f"Начните регулярно заполнять: {missing_names}"],
            "sources": ["CoreMetric"]
        })

    # CoreMetric Index — нужно минимум 3 параметра по 7+ дней
    cm_fields = [c for c in WEIGHTS if c in df.columns]
    filled_cm = sum(1 for c in cm_fields if df[c].notna().sum() >= 7)
    if filled_cm < 3:
        recs.append({
            "level": "missing",
            "title": "🎯 Недостаточно данных для индекса CoreMetric",
            "text": f"Для расчёта интегрального индекса требуется минимум 7 дней данных по 3+ параметрам. Сейчас достаточно данных по {filled_cm} параметрам.",
            "actions": [
                "Ежедневно заполняйте ЧСС покоя, сон, настроение, физ. самочувствие",
                "Чем больше параметров заполнено — тем точнее индекс"
            ],
            "sources": ["CoreMetric Algorithm"]
        })

    return recs


def generate_recommendations(df):
    return generate_detailed_recommendations(df)


def generate_detailed_recommendations(df):
    if df.empty:
        return [{
            "level": "missing",
            "title": "📊 Нет данных",
            "text": "Начните заполнять дневник на вкладке 'Ввод'.",
            "actions": ["Заполните дату и хотя бы несколько параметров", "Сохраните запись"],
            "sources": ["CoreMetric"]
        }]

    recs = []

    # 1. Проверяем нехватку данных
    missing_recs = check_missing_data(df)
    recs.extend(missing_recs)

    # 2. Если есть данные — генерируем обычные рекомендации
    df_clean = df.dropna(subset=["resting_hr", "sys_bp"], how="all")
    if df_clean.empty:
        return recs

    latest = df_clean.iloc[-1]
    resting_hr = _safe_get(latest, "resting_hr", 0)
    sys_bp = _safe_get(latest, "sys_bp", 0)
    dia_bp = _safe_get(latest, "dia_bp", 0)
    sleep_quality = _safe_get(latest, "sleep_quality", 100)
    mood = _safe_get(latest, "mood", 100)
    calories = _safe_get(latest, "calories", 0)
    rpe = _safe_get(latest, "rpe", 0)
    spo2 = _safe_get(latest, "spo2", 98)
    physical_state = _safe_get(latest, "physical_state", 50)

    # --- АЛЕРТЫ ---
    if resting_hr > THRESHOLDS["resting_hr"]["high_crit"]:
        recs.append({"level": "danger", "title": "🔴 Тахикардия покоя",
                     "text": f"ЧСС {resting_hr:.0f} уд/мин — выше критической границы.",
                     "actions": ["Измерьте температуру", "Исключите тренировку", "Увеличьте гидратацию"],
                     "sources": ["ACSM Guidelines 2023", "BJSM: HR Monitoring"]})
    if sys_bp > THRESHOLDS["sys_bp"]["high_crit"] or dia_bp > THRESHOLDS["dia_bp"]["high_crit"]:
        recs.append({"level": "danger", "title": "🔴 Повышенное АД",
                     "text": f"АД {sys_bp:.0f}/{dia_bp:.0f} — выше 140/90.",
                     "actions": ["Перемерьте через 15 минут", "Консультация врача при сохранении",
                                 "Ограничьте соль и кофеин"],
                     "sources": ["РФ Клинические рекомендации по АГ 2023"]})
    if sleep_quality < THRESHOLDS["sleep_quality"]["low_warn"]:
        recs.append({"level": "warning", "title": "🌙 Низкое качество сна",
                     "text": f"Оценка сна {sleep_quality:.0f}/100 — критично для восстановления.",
                     "actions": ["Без гаджетов за 1 час до сна", "Температура 18-20°C", "Дыхание 4-7-8 или медитация"],
                     "sources": ["ACSM Sleep Consensus 2023", "ESSA Recovery Guidelines"]})
    if mood < THRESHOLDS["mood"]["low_warn"]:
        recs.append({"level": "warning", "title": "😔 Сниженное настроение",
                     "text": f"Настроение {mood:.0f}/100 — маркер накопленного стресса.",
                     "actions": ["Лёгкая активность на свежем воздухе", "Дыхательные практики", "Социальный контакт"],
                     "sources": ["BJSM: Mental Health in Athletes"]})
    if spo2 < THRESHOLDS["spo2"]["low_warn"]:
        recs.append({"level": "warning", "title": "💨 Сниженная сатурация",
                     "text": f"SpO₂ {spo2:.0f}% — ниже нормы.",
                     "actions": ["Дыхательные упражнения", "Проветрите помещение", "Консультация врача при < 92%"],
                     "sources": ["ACSM Guidelines"]})

    acwr = calc_acwr(df)
    if not acwr.empty:
        val = acwr.iloc[-1]
        if val > 1.5:
            recs.append({"level": "danger", "title": f"⚠️ ACWR={val:.2f} — риск травмы",
                         "text": "Резкий скачок нагрузки относительно фона.",
                         "actions": ["Снизьте объём на 30-50%", "Добавьте день отдыха", "Фокус на технике"],
                         "sources": ["Gabbett TJ. BJSM 2016"]})
        elif val < 0.8:
            recs.append({"level": "info", "title": f" ACWR={val:.2f} — недотренированность",
                         "text": "Нагрузка ниже привычного уровня.",
                         "actions": ["Постепенно увеличивайте объём +10%/нед", "Вернитесь к регулярным тренировкам"],
                         "sources": ["Gabbett TJ. BJSM 2016"]})

    mono = calc_monotony(df)
    if not mono.empty and mono.iloc[-1] > 2.0:
        recs.append({"level": "warning", "title": f"🔄 Монотонность={mono.iloc[-1]:.1f}",
                     "text": "Однообразные нагрузки повышают риск OTS.",
                     "actions": ["Смените вид активности", "Добавьте интервалы", "Восстановительный день"],
                     "sources": ["Foster C. JSSR 2001"]})

    rd = calc_readiness(df).iloc[-1] if not calc_readiness(df).empty else 50
    if rd > 75 and (calories < 2000 or rpe < 3):
        recs.append({"level": "success", "title": " Высокая готовность",
                     "text": "Организм восстановлен — идеальное окно для нагрузки.",
                     "actions": ["Интенсивная или длительная тренировка", "Попробуйте личный рекорд",
                                 "Работа в зоне 2 пульса"],
                     "sources": ["CoreMetric Algorithm"]})

    # --- СТАТУСЫ ПО ПАРАМЕТРАМ ---
    if THRESHOLDS["resting_hr"]["low_normal"] <= resting_hr <= THRESHOLDS["resting_hr"]["high_normal"]:
        recs.append({"level": "success", "title": "❤️ ЧСС покоя в норме",
                     "text": f"{resting_hr:.0f} уд/мин — оптимальный уровень.",
                     "actions": ["Продолжайте мониторинг", "Поддерживайте текущий режим"],
                     "sources": ["ACSM Guidelines"]})
    elif resting_hr < THRESHOLDS["resting_hr"]["low_normal"] and resting_hr > THRESHOLDS["resting_hr"]["low_crit"]:
        recs.append({"level": "info", "title": "❤️ ЧСС покоя ниже среднего",
                     "text": f"{resting_hr:.0f} уд/мин — возможно, признак хорошей тренированности.",
                     "actions": ["Убедитесь в отсутствии симптомов", "Контроль АД"],
                     "sources": ["BJSM"]})
    elif resting_hr > THRESHOLDS["resting_hr"]["high_normal"] and resting_hr <= THRESHOLDS["resting_hr"]["high_warn"]:
        recs.append({"level": "info", "title": "❤️ ЧСС покоя повышена",
                     "text": f"{resting_hr:.0f} уд/мин — выше оптимального диапазона.",
                     "actions": ["Проверьте качество сна", "Снизьте нагрузку", "Контроль гидратации"],
                     "sources": ["ACSM"]})

    if sleep_quality >= THRESHOLDS["sleep_quality"]["high_normal"]:
        recs.append({"level": "success", "title": "🌙 Отличное качество сна",
                     "text": f"{sleep_quality:.0f}/100 — восстановление на высоком уровне.",
                     "actions": ["Поддерживайте режим", "Соблюдайте гигиену сна"],
                     "sources": ["ACSM Sleep Consensus"]})
    elif THRESHOLDS["sleep_quality"]["low_normal"] <= sleep_quality < THRESHOLDS["sleep_quality"]["high_normal"]:
        recs.append({"level": "info", "title": "🌙 Сон в пределах нормы",
                     "text": f"{sleep_quality:.0f}/100 — приемлемый уровень.",
                     "actions": ["Попробуйте улучшить: затемнение, прохлада", "Ограничьте кофеин после 14:00"],
                     "sources": ["ESSA"]})

    if mood >= THRESHOLDS["mood"]["high_normal"]:
        recs.append({"level": "success", "title": "😊 Хорошее настроение",
                     "text": f"{mood:.0f}/100 — позитивный психологический статус.",
                     "actions": ["Поддерживайте социальную активность", "Продолжайте тренироваться в удовольствие"],
                     "sources": ["BJSM Mental Health"]})
    elif THRESHOLDS["mood"]["low_normal"] <= mood < THRESHOLDS["mood"]["high_normal"]:
        recs.append({"level": "info", "title": "😊 Настроение умеренное",
                     "text": f"{mood:.0f}/100 — в пределах нормы, но есть потенциал роста.",
                     "actions": ["Добавьте лёгкую активность", "Практики осознанности"],
                     "sources": ["BJSM"]})

    if spo2 >= THRESHOLDS["spo2"]["high_normal"]:
        recs.append({"level": "success", "title": "💨 Сатурация отличная",
                     "text": f"SpO₂ {spo2:.0f}% — оптимальное насыщение крови кислородом.",
                     "actions": ["Продолжайте дыхательные практики", "Регулярные аэробные нагрузки"],
                     "sources": ["ACSM"]})
    elif THRESHOLDS["spo2"]["low_normal"] <= spo2 < THRESHOLDS["spo2"]["high_normal"]:
        recs.append({"level": "info", "title": "💨 Сатурация в норме",
                     "text": f"SpO₂ {spo2:.0f}% — допустимый уровень.",
                     "actions": ["Дыхательные упражнения", "Кардио в зоне 2"],
                     "sources": ["ACSM"]})

    if physical_state >= THRESHOLDS["physical_state"]["high_normal"]:
        recs.append({"level": "success", "title": "🏃 Отличное самочувствие",
                     "text": f"{physical_state:.0f}/100 — организм готов к нагрузке.",
                     "actions": ["Можно планировать интенсивную тренировку"],
                     "sources": ["CoreMetric"]})
    elif THRESHOLDS["physical_state"]["low_normal"] <= physical_state < THRESHOLDS["physical_state"]["high_normal"]:
        recs.append({"level": "info", "title": " Самочувствие умеренное",
                     "text": f"{physical_state:.0f}/100 — приемлемый уровень.",
                     "actions": ["Средняя интенсивность", "Добавьте разминку"],
                     "sources": ["CoreMetric"]})

    if not acwr.empty:
        val = acwr.iloc[-1]
        if 0.8 <= val <= 1.3:
            recs.append({"level": "success", "title": f"⚖️ ACWR={val:.2f} — оптимальная нагрузка",
                         "text": "Соотношение острой и хронической нагрузки в безопасной зоне.",
                         "actions": ["Продолжайте текущий режим", "Постепенная прогрессия"],
                         "sources": ["Gabbett TJ. BJSM 2016"]})

    if not mono.empty:
        val = mono.iloc[-1]
        if val < 1.5:
            recs.append({"level": "success", "title": f"🔄 Монотонность={val:.2f} — разнообразная нагрузка",
                         "text": "Хорошее разнообразие тренировок снижает риск OTS.",
                         "actions": ["Поддерживайте вариативность", "Чередуйте интенсивность"],
                         "sources": ["Foster C. JSSR 2001"]})
        elif 1.5 <= val <= 2.0:
            recs.append({"level": "info", "title": f"🔄 Монотонность={val:.2f} — умеренная",
                         "text": "Допустимый уровень, но есть потенциал улучшения.",
                         "actions": ["Добавьте кросс-тренинг", "Включите интервалы"],
                         "sources": ["Foster C. JSSR 2001"]})

    ortho = calc_orthostatic_index(df)
    if not ortho.empty and pd.notna(ortho.iloc[-1]):
        val = ortho.iloc[-1]
        if 10 <= val <= 20:
            recs.append({"level": "success", "title": f"🫀 Ортост. индекс={val:.1f}% — норма",
                         "text": "Вегетативная регуляция в оптимальном диапазоне.",
                         "actions": ["Продолжайте мониторинг", "Поддерживайте режим восстановления"],
                         "sources": ["Sports Medicine"]})
        elif 5 <= val < 10 or 20 < val <= 28:
            recs.append({"level": "info", "title": f"🫀 Ортост. индекс={val:.1f}% — пограничный",
                         "text": "Возможно накопление утомления или стресса.",
                         "actions": ["Добавьте день отдыха", "Контроль сна и гидратации"],
                         "sources": ["Sports Medicine"]})
        elif val > 28:
            recs.append({"level": "warning", "title": f"🫀 Ортост. индекс={val:.1f}% — повышен",
                         "text": "Признак симпатической перегрузки.",
                         "actions": ["Снизьте нагрузку", "Техники релаксации", "Консультация врача при сохранении"],
                         "sources": ["Sports Medicine"]})

    if rd >= 70:
        recs.append({"level": "success", "title": f"💪 Готовность={rd:.0f} — высокая",
                     "text": "Организм хорошо восстановлен.",
                     "actions": ["Можно планировать высокую нагрузку"],
                     "sources": ["CoreMetric"]})
    elif 40 <= rd < 70:
        recs.append({"level": "info", "title": f"💪 Готовность={rd:.0f} — умеренная",
                     "text": "Средний уровень восстановления.",
                     "actions": ["Умеренная интенсивность", "Фокус на технике"],
                     "sources": ["CoreMetric"]})
    elif rd < 40:
        recs.append({"level": "warning", "title": f" Готовность={rd:.0f} — низкая",
                     "text": "Организм не восстановился.",
                     "actions": ["День отдыха или активное восстановление", "Сон и питание в приоритете"],
                     "sources": ["CoreMetric"]})

    # Сортировка: missing → danger → warning → info → success
    priority = {"missing": -1, "danger": 0, "warning": 1, "info": 2, "success": 3}
    return sorted(recs, key=lambda x: priority.get(x["level"], 9))