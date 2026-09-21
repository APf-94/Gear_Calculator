import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from icalendar import Calendar
from fitparse import FitFile

# --- SEITEN-SETUP ---
st.set_page_config(page_title="Trainings-Cockpit 2027", layout="wide", page_icon="🚴‍♂️")

# --- 1. SEITENLEISTE: DIAGNOSE & VERBINDUNGEN ---
st.sidebar.header("🔑 Verbindungen")

# Diagnose: Welche Schlüssel existieren wirklich in st.secrets?
vorhandene_keys = list(st.secrets.keys())
st.sidebar.caption(f"Erkannte Secrets-Keys: `{vorhandene_keys}`")

# Werte sicher abrufen (Groß-/Kleinschreibung abfedern)
sec_api = st.secrets.get("INTERVALS_API") or st.secrets.get("intervals_api", "")
sec_id = str(st.secrets.get("INTERVALS_ID") or st.secrets.get("intervals_id", "0"))
sec_gcal = st.secrets.get("GCAL_LINK") or st.secrets.get("gcal_link", "")

if sec_api and sec_gcal:
    st.sidebar.success("✅ Alle Zugangsdaten geladen")
    api_key = sec_api
    athlete_id = sec_id
    gcal_url = sec_gcal
else:
    fehlend = []
    if not sec_api: fehlend.append("INTERVALS_API")
    if not sec_gcal: fehlend.append("GCAL_LINK")
    st.sidebar.error(f"❌ Fehlt in Secrets: {', '.join(fehlend)}")
    
    api_key = st.sidebar.text_input("Intervals API Key", value=sec_api, type="password")
    athlete_id = st.sidebar.text_input("Intervals Athlete ID", value=sec_id)
    gcal_url = st.sidebar.text_input("Google Kalender iCal URL", value=sec_gcal, type="password")

st.sidebar.markdown("---")
st.sidebar.header("👤 Athletendaten")
user_weight = st.sidebar.number_input("Gewicht (kg)", value=84.0, step=0.5)
user_ftp = st.sidebar.number_input("FTP (Watt)", value=271, step=1)
# --- 2. HELPER FUNKTIONEN ---
@st.cache_data(ttl=300)
def get_intervals_activities(oldest_str, newest_str, api_key, athlete_id):
    """Holt absolvierte Aktivitäten von Intervals.icu"""
    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities"
    res = requests.get(url, auth=("API_KEY", api_key), params={"oldest": oldest_str, "newest": newest_str})
    return res.json() if res.status_code == 200 else []

@st.cache_data(ttl=300)
def get_athlete_profile(api_key, athlete_id):
    """Holt aktuelle Form- und Fitnessdaten"""
    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}"
    res = requests.get(url, auth=("API_KEY", api_key))
    return res.json() if res.status_code == 200 else None

def get_gcal_events(ics_url, start_date, end_date):
    """Liest die .ics Datei im Hintergrund aus und filtert Termine der aktuellen Woche"""
    if not ics_url:
        return []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(ics_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        cal = Calendar.from_ical(response.content)
        events = []
        
        for component in cal.walk('vevent'):
            dtstart = component.get('dtstart')
            if not dtstart:
                continue
            val = dtstart.dt
            event_date = val.date() if isinstance(val, datetime) else val
            
            # Prüfen, ob der Termin in der aktuellen Kalenderwoche liegt
            if start_date <= event_date <= end_date:
                summary = str(component.get('summary', 'Training'))
                dtend = component.get('dtend')
                duration_m = 60 # Standard-Dauer falls nicht angegeben
                if dtend:
                    end_val = dtend.dt
                    if isinstance(end_val, datetime) and isinstance(val, datetime):
                        duration_m = round((end_val - val).total_seconds() / 60)
                
                events.append({
                    "Datum": event_date,
                    "Titel": summary,
                    "Dauer (Min)": duration_m
                })
                
        return sorted(events, key=lambda x: x["Datum"])
    except Exception as e:
        st.sidebar.error(f"⚠️ Kalender-Fehler: {e}")
        return []

@st.cache_data
def load_fit_data(file_bytes):
    fitfile = FitFile(file_bytes)
    records = []
    for record in fitfile.get_messages('record'):
        record_data = {}
        for data_field in record:
            if data_field.name in ['timestamp', 'power', 'heart_rate', 'cadence']:
                record_data[data_field.name] = data_field.value
        records.append(record_data)
    df = pd.DataFrame(records)
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')
    return df

# --- 3. TABS AUFBAUEN ---
st.title("🎯 Saison 2027 Dashboard")
tab1, tab2, tab3 = st.tabs(["📅 PMC & Kalender", "📈 FIT-File Analyse", "⚙️ Übersetzungsrechner"])

# ==========================================
# TAB 1: KALENDER (iCal), INTERVALS & PMC
# ==========================================
with tab1:
    if not api_key:
        st.info("👉 Bitte gib in der Seitenleiste deinen Intervals API Key ein.")
    else:
        # Datumsbereiche (Montag bis Sonntag)
        today = date.today()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        start_90d = today - timedelta(days=90)

        # Daten laden
        profile = get_athlete_profile(api_key, athlete_id)
        activities_past = get_intervals_activities(start_90d.isoformat(), today.isoformat(), api_key, athlete_id)
        planned_events = get_gcal_events(gcal_url, start_week, end_week)

        # Metriken Header
        if profile:
            ftp = profile.get("icu_ftp", user_ftp)
            w_kg = round(ftp / user_weight, 2)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("FTP (Intervals)", f"{ftp} W", f"{w_kg} W/kg")
            c2.metric("Gewicht", f"{profile.get('icu_weight', user_weight)} kg")
            c3.metric("Fitness (CTL)", profile.get("icu_ctl", 0))
            c4.metric("Ermüdung (ATL)", profile.get("icu_atl", 0))
            c5.metric("Form (TSB)", profile.get("icu_tsb", 0))
            st.markdown("---")

        # Wochenübersicht: Geplant vs. Absolviert
        st.subheader(f"Woche: {start_week.strftime('%d.%m.')} – {end_week.strftime('%d.%m.%Y')}")
        col_plan, col_done = st.columns(2)
        
        with col_plan:
            st.markdown("#### 📝 Geplant (Google Kalender via iCal)")
            if planned_events:
                for ev in planned_events:
                    wochentag = ev["Datum"].strftime('%a, %d.%m.')
                    st.markdown(f"* **{wochentag}:** {ev['Titel']} `({ev['Dauer (Min)']} min)`")
            else:
                st.write("Keine Google-Kalender-Termine für diese Woche gefunden.")
                st.caption("Stelle sicher, dass links die geheime '.ics'-Adresse eingetragen ist.")

        with col_done:
            st.markdown("#### ✅ Absolviert (Garmin)")
            week_acts = [a for a in activities_past if pd.to_datetime(a.get("start_date_local")).date() >= start_week]
            if week_acts:
                for act in sorted(week_acts, key=lambda x: x.get("start_date_local")):
                    d = pd.to_datetime(act.get("start_date_local")).strftime('%a, %d.%m.')
                    typ = act.get("type", "Sport")
                    dur = round((act.get("moving_time") or 0) / 60)
                    load = act.get("icu_training_load") or 0
                    st.markdown(f"* **{d}:** {act.get('name')} `({typ}, {dur} min, {round(load)} TSS)`")
            else:
                st.write("Diese Woche noch keine Aktivitäten aufgezeichnet.")
        st.markdown("---")

        # Auswertungen & PMC
        if activities_past:
            df_act = pd.DataFrame([{
                "Datum": pd.to_datetime(a.get("start_date_local")),
                "Typ": a.get("type", "Sonstiges"),
                "Dauer_h": round((a.get("moving_time") or 0) / 3600, 2),
                "kJ": round((a.get("icu_joules") or 0) / 1000),
                "TSS": a.get("icu_training_load") or 0,
                "CTL": a.get("icu_ctl"),
                "ATL": a.get("icu_atl")
            } for a in activities_past]).sort_values("Datum")
            
            df_pmc = df_act.dropna(subset=["CTL", "ATL"]).copy()
            df_pmc["TSB"] = df_pmc["CTL"] - df_pmc["ATL"]

            st.subheader("📊 Auswertung & Formaufbau")
            
            # KPIs letzte 7 Tage
            last_7d = df_act[df_act["Datum"] >= pd.to_datetime(today - timedelta(days=7))]
            cx1, cx2, cx3 = st.columns(3)
            cx1.metric("Trainingszeit (letzte 7T)", f"{round(last_7d['Dauer_h'].sum(), 1)} h")
            cx2.metric("Energieumsatz Rad", f"{int(last_7d['kJ'].sum()):,} kJ".replace(",", "."))
            cx3.metric("Absolvierter TSS", int(last_7d['TSS'].sum()))
            
            col_chart1, col_chart2 = st.columns([1, 2])
            with col_chart1:
                sport_split = last_7d.groupby("Typ")["Dauer_h"].sum().reset_index()
                fig_bar = go.Figure(go.Bar(
                    x=sport_split["Typ"], y=sport_split["Dauer_h"], 
                    text=[f"{v} h" for v in sport_split["Dauer_h"]], textposition="auto",
                    marker_color=["#3498db", "#2ecc71", "#e67e22", "#9b59b6"]
                ))
                fig_bar.update_layout(title="Sportarten (7T)", yaxis_title="Stunden", template="plotly_white", height=320, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_chart2:
                fig_pmc = go.Figure()
                fig_pmc.add_trace(go.Scatter(x=df_pmc["Datum"], y=df_pmc["CTL"], name="Fitness (CTL)", line=dict(color="#2980b9", width=2)))
                fig_pmc.add_trace(go.Scatter(x=df_pmc["Datum"], y=df_pmc["ATL"], name="Ermüdung (ATL)", line=dict(color="#e74c3c", width=1.5, dash="dot")))
                fig_pmc.add_trace(go.Scatter(x=df_pmc["Datum"], y=df_pmc["TSB"], name="Form (TSB)", line=dict(color="#27ae60", width=1.5)))
                fig_pmc.update_layout(title="Performance Management Chart (90T)", hovermode="x unified", yaxis_title="Load", template="plotly_white", height=320, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_pmc, use_container_width=True)

# ==========================================
# TAB 2: FIT-FILE ANALYSE
# ==========================================
with tab2:
    uploaded_file = st.file_uploader("FIT-Datei für Detail-Analyse auswählen", type=['fit'])
    
    if uploaded_file:
        with st.spinner("Analysiere Daten..."):
            df_fit = load_fit_data(uploaded_file.getvalue())
            
            if not df_fit.empty and 'power' in df_fit.columns:
                pwr = df_fit['power'].fillna(0)
                avg_pwr, max_pwr = round(pwr.mean()), round(pwr.max())
                np_val = round((pwr.rolling(30, min_periods=1).mean()**4).mean()**0.25)
                kj = round(pwr.sum() / 1000)
                if_val = round(np_val / user_ftp, 2)
                tss = round((len(pwr) * np_val * if_val) / (user_ftp * 3600) * 100)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Ø Leistung | NP", f"{avg_pwr} W | {np_val} W")
                c2.metric("Max Leistung", f"{max_pwr} W")
                c3.metric("TSS | IF", f"{tss} | {if_val}")
                c4.metric("Arbeit (kJ)", f"{kj} kJ")
                
                zones = {
                    "Z1: Rekom (<55%)": (0, user_ftp * 0.55),
                    "Z2: GA1 (55-75%)": (user_ftp * 0.55, user_ftp * 0.75),
                    "Z3: GA2 (76-90%)": (user_ftp * 0.75, user_ftp * 0.90),
                    "Z4: Schwelle (91-105%)": (user_ftp * 0.90, user_ftp * 1.05),
                    "Z5: VO2max (106-120%)": (user_ftp * 1.05, user_ftp * 1.20),
                    "Z6: Anaerob (>120%)": (user_ftp * 1.20, 2000)
                }
                time_in_zones = {z: round(len(df_fit[(df_fit['power'] > l) & (df_fit['power'] <= u)]) / 60, 1) for z, (l, u) in zones.items()}
                
                col_plt1, col_plt2 = st.columns([2, 1])
                with col_plt1:
                    fig_line = go.Figure()
                    fig_line.add_trace(go.Scatter(x=df_fit.index, y=pwr.rolling(10).mean(), name='Leistung (10s)', line=dict(color='#3498db')))
                    if 'heart_rate' in df_fit.columns:
                        fig_line.add_trace(go.Scatter(x=df_fit.index, y=df_fit['heart_rate'], name='Puls', yaxis='y2', line=dict(color='#e74c3c')))
                    fig_line.update_layout(title="Verlauf", hovermode="x unified", yaxis=dict(title='Watt'), yaxis2=dict(title='BPM', overlaying='y', side='right'), template="plotly_white")
                    st.plotly_chart(fig_line, use_container_width=True)
                
                with col_plt2:
                    fig_z = go.Figure(go.Bar(x=list(time_in_zones.values()), y=list(time_in_zones.keys()), orientation='h', text=list(time_in_zones.values()), textposition='auto'))
                    fig_z.update_layout(title="Minuten in Zonen", template="plotly_white")
                    st.plotly_chart(fig_z, use_container_width=True)
            else:
                st.error("Keine Leistungsdaten in der FIT-Datei gefunden.")

# ==========================================
# TAB 3: ÜBERSETZUNGS-RECHNER
# ==========================================
with tab3:
    st.markdown("Berechne Geschwindigkeiten basierend auf Trittfrequenz, Radumfang und Kassette.")
    col_s1, col_s2, col_s3 = st.columns(3)
    circumference = col_s1.number_input("Radumfang (mm)", value=2110, step=10)
    cadence = col_s2.slider("Trittfrequenz (U/min)", 40, 150, 95)
    cassette_type = col_s3.selectbox("Gänge", ["11-fach", "10-fach", "12-fach"])
    
    col_c1, col_c2 = st.columns(2)
    cr_large = col_c1.number_input("Großes Blatt", value=52)
    cr_small = col_c2.number_input("Kleines Blatt", value=36)
    
    cogs_input = st.text_input("Ritzel (Kassette)", value="11, 12, 13, 14, 15, 17, 19, 21, 23, 25, 28" if cassette_type == "11-fach" else "11, 12, 13, 14, 15, 16, 17, 19, 21, 24, 27, 30")
    
    try:
        cogs = sorted([int(x.strip()) for x in cogs_input.split(",")], reverse=True)
        fig_g = go.Figure()
        table_data = {"Kassette (Zähne)": cogs}
        
        for name, teeth in [("Groß", cr_large), ("Klein", cr_small)]:
            speeds = [cadence * (teeth / c) * circumference * 60 / 1_000_000 for c in cogs]
            table_data[f"{name} ({teeth} Z)"] = [round(s, 1) for s in speeds]
            fig_g.add_trace(go.Scatter(x=[str(c) for c in cogs], y=speeds, mode='lines+markers', name=f'{name} ({teeth} Z)'))
            
        fig_g.update_layout(title="Geschwindigkeit (km/h) pro Ritzel", hovermode="x unified", xaxis_title="Kassette", yaxis_title="km/h", template="plotly_white")
        st.plotly_chart(fig_g, use_container_width=True)
        st.dataframe(pd.DataFrame(table_data).set_index("Kassette (Zähne)").T, use_container_width=True)
    except ValueError:
        st.error("Bitte Ritzel als kommagetrennte Zahlen eingeben.")
