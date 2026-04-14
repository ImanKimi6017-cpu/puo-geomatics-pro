import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import os
import ezdxf
import io
import requests

# 1. KONFIGURASI HALAMAN
st.set_page_config(page_title="PUO Geomatics Pro", layout="wide")

# 2. SISTEM LOGIN
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def login_interface():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.write("<br><br>", unsafe_allow_html=True)
        if os.path.exists("LOGO PUO.png"):
            st.image("LOGO PUO.png", use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Sistem Geomatik PUO Pro</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            u_id = st.text_input("ID Pengguna", placeholder="01DGU24F1059")
            u_pw = st.text_input("Kata Laluan", type="password")
            if st.button("Log Masuk Sekarang", use_container_width=True, type="primary"):
                if u_id in ["1", "2", "3", "01DGU24F1059", "01DGU24F1061"] and u_pw == "ADMIN1234":
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("ID atau Kata Laluan Salah!")

if not st.session_state["logged_in"]:
    login_interface()
    st.stop()

# 3. FUNGSI TEKNIKAL
@st.cache_resource
def get_transformer():
    return Transformer.from_crs("epsg:3384", "epsg:4326", always_xy=True)

def ambil_cuaca(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=weather_code,temperature_2m&timezone=auto"
        response = requests.get(url).json()
        temp = response['current']['temperature_2m']
        code = response['current']['weather_code']
        weather_map = {0: "Cerah ☀️", 1: "Cerah Berawan 🌤️", 2: "Berawan ☁️", 3: "Mendung ☁️", 45: "Berkabus 🌫️", 51: "Rintik Gerimis 🌦️", 61: "Hujan 🌧️", 80: "Hujan Lebat ⛈️"}
        desc = weather_map.get(code, "Cuaca Tidak Diketahui")
        if code in [0, 1, 2]: status = "✅ SESUAI"
        elif code in [3, 45, 51]: status = "⚠️ BERHATI-HATI"
        else: status = "❌ TIDAK SESUAI"
        return temp, desc, status
    except:
        return None, "N/A", "Tiada Data"

def kira_luas(coords):
    n = len(coords)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2.0

def export_to_dxf(df):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new(name='TEKS_KOORDINAT', dxfattribs={'color': 7})
    for _, row in df.iterrows():
        msp.add_point((row['E'], row['N']), dxfattribs={'color': 1})
        msp.add_text(f"{int(row['STN'])}", dxfattribs={'height': 1.2}).set_placement((row['E']+0.5, row['N']+0.5))
        koordinat_sahaja = f"{row['E']:.3f}, {row['N']:.3f}"
        msp.add_text(koordinat_sahaja, dxfattribs={'height': 0.7, 'layer': 'TEKS_KOORDINAT'}).set_placement((row['E']+0.5, row['N']-1.5))
    out_stream = io.StringIO()
    doc.write(out_stream)
    dxf_string = out_stream.getvalue()
    out_stream.close()
    return dxf_string.encode('utf-8')

# 4. SIDEBAR
if os.path.exists("LOGO PUO.png"):
    st.sidebar.image("LOGO PUO.png", use_container_width=True)
else:
    st.sidebar.image("https://www.puo.edu.my/wp-content/uploads/2021/08/logo-puo.png", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.title("Portal Geomatik")
file_choice = st.sidebar.radio("Pilih Data Fail:", ["Batu Sempadan (BKL)", "Control Station (CRM)"])

# 5. LOADING DATA
filename = "BKL_PROGRAMMING.csv" if "BKL" in file_choice else "CRM_PROGRAMMING.csv"
stn_col = "BKL" if "BKL" in file_choice else "CRM"

if os.path.exists(filename):
    df = pd.read_csv(filename)
    df_map = df.rename(columns={'EASTING': 'E', 'NORTHING': 'N', stn_col: 'STN'})
    df_map = df_map.sort_values(by='STN').reset_index(drop=True)
    
    tf = get_transformer()
    lons, lats = tf.transform(df_map['E'].values, df_map['N'].values)
    df_map['lat'], df_map['lon'] = lats, lons
    xy_coords = list(zip(df_map['E'], df_map['N']))
    area_m2 = kira_luas(xy_coords)

    # --- SIDEBAR KAWALAN ---
    st.sidebar.markdown("---")
    with st.sidebar.expander("🛠️ KAWALAN PETA & CARIAN", expanded=True):
        map_style = st.selectbox("Gaya Peta:", ["Google Satellite", "Google Terrain", "Dark Mode"])
        show_labels = st.checkbox("Papar Nombor Stesen", value=True)
        st.markdown("---")
        sorted_stn = sorted(df_map['STN'].astype(int).unique())
        stn_list = ["-- Pilih Stesen --"] + [str(s) for s in sorted_stn]
        search_stn = st.selectbox("Cari No. Stesen:", stn_list)

    # CUACA
    st.sidebar.markdown("---")
    st.sidebar.subheader("🌤️ Status Cuaca")
    avg_lat, avg_lon = df_map['lat'].mean(), df_map['lon'].mean()
    suhu, cuaca, status_ukur = ambil_cuaca(avg_lat, avg_lon)
    with st.sidebar.container(border=True):
        st.write(f"**Suhu:** {suhu}°C | {cuaca}")
        if "✅" in status_ukur: st.success(status_ukur)
        elif "⚠️" in status_ukur: st.warning(status_ukur)
        else: st.error(status_ukur)

    st.sidebar.markdown("---")
    st.sidebar.info("💻 **Developed by:**\n\n**PATTAYA SYNDICATE**")

    if st.sidebar.button("🚪 Log Keluar"):
        st.session_state["logged_in"] = False
        st.rerun()

    # 6. PAPARAN UTAMA
    st.subheader(f"📍 Perak Grid (3384) | Surveyor: Farizul, Iman Hakimi, Ajmal")
    st.markdown("<p style='margin-top:-15px; color: grey; font-style: italic;'>System Powered by PATTAYA SYNDICATE</p>", unsafe_allow_html=True)
    
    if map_style == "Google Satellite": tiles = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    elif map_style == "Google Terrain": tiles = "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}"
    else: tiles = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"

    center_lat, center_lon, zoom_val = avg_lat, avg_lon, 18
    if search_stn != "-- Pilih Stesen --":
        target_row = df_map[df_map['STN'].astype(int).astype(str) == search_stn].iloc[0]
        center_lat, center_lon, zoom_val = target_row['lat'], target_row['lon'], 20

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_val, tiles=tiles, attr=' ', control_scale=False)

    # --- LUKIS TITIK DAHULU (SUPAYA DI BAWAH LABEL) ---
    for _, row in df_map.iterrows():
        stn_no = int(row['STN'])
        is_target = (search_stn != "-- Pilih Stesen --" and str(stn_no) == search_stn)
        dot_color = "yellow" if is_target else "red"
        
        # Format URL Google Maps yang ringkas
        gmaps_url = f"https://www.google.com/maps?q={row['lat']},{row['lon']}"
        
        popup_html = f"""
        <div style="font-family: Arial; font-size: 10pt; min-width: 140px;">
            <b>Stesen {stn_no}</b><br>
            <b>E:</b> {row['E']:.3f}<br>
            <b>N:</b> {row['N']:.3f}<br>
            <hr style="margin: 5px 0;">
            <a href="{gmaps_url}" target="_blank" style="color: blue; font-weight: bold; text-decoration: none;">
                📍 Navigasi Google Maps
            </a>
        </div>
        """
        
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=9 if is_target else 7,
            color="white",
            weight=2,
            fill=True,
            fill_color=dot_color,
            fill_opacity=1,
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=f"Klik untuk info Stesen {stn_no}"
        ).add_to(m)

        # Lukis Label (Hanya jika ON)
        if show_labels:
            label_color = "cyan" if is_target else "yellow"
            folium.Marker(
                location=[row['lat'], row['lon']],
                icon=folium.DivIcon(html=f'<div style="font-size: 10pt; color: {label_color}; font-weight: bold; text-shadow: 2px 2px 4px black; width: 40px; pointer-events: none;">{stn_no}</div>')
            ).add_to(m)

    # Key Peta yang dinamik untuk paksa refresh bila carian berubah
    map_key = f"map_{file_choice}_{search_stn}_{map_style}"
    st_folium(m, width="100%", height=500, key=map_key)

    # 📊 JADUAL & LUAS
    st.write("---")
    st.markdown("### 📊 Jadual Koordinat Stesen")
    st.dataframe(df_map[['STN', 'E', 'N']].rename(columns={'STN': 'No. Stesen', 'E': 'Easting (m)', 'N': 'Northing (m)'}), use_container_width=True, hide_index=True)

    st.write("---")
    col_d, col_s = st.columns([1, 1])
    with col_d:
        dxf_bytes = export_to_dxf(df_map)
        st.download_button(label="💾 Muat Turun Fail DXF (AutoCAD)", data=dxf_bytes, file_name=f"Pelan_{file_choice}.dxf", mime="application/dxf", use_container_width=True)
    with col_s:
        st.success(f"Luas Keseluruhan: **{area_m2:.2f} m²** | **{area_m2/10000:.3f} Hektar**")

else:
    st.sidebar.button("🚪 Log Keluar")
    st.error(f"Fail {filename} tidak dijumpai.")

st.markdown("<br><hr><center><small>PUO Geomatics Pro | Developed by PATTAYA SYNDICATE</small></center>", unsafe_allow_html=True)