import streamlit as st
import openrouteservice
import folium
from streamlit_folium import st_folium
import pandas as pd

# ---------------------------------------------------------
# 1. 기본 설정 및 데이터
# ---------------------------------------------------------
st.set_page_config(page_title="캄보디아/베트남 물류 운송 시뮬레이터", layout="wide")

# 좌표 데이터 (캄보디아 + 베트남)
LOCATIONS = {
    # 🇰🇭 캄보디아 (Cambodia)
    "[KH] Phnom Penh (프놈펜/수도)": (104.9282, 11.5564),
    "[KH] Sihanoukville (시아누크빌/메인항구)": (103.5299, 10.6253),
    "[KH] Siem Reap (씨엠립)": (103.8552, 13.3633),
    "[KH] Battambang (바탐방)": (103.0605, 13.0957),
    "[KH] Kampot (캄포트)": (104.1819, 10.6148),
    "[KH] Kratie (크라체)": (106.0167, 12.4886),
    "[KH] Stung Treng (스퉁트렝)": (105.9699, 13.5258),
    "[KH] Poipet (포이펫/태국국경)": (102.5636, 13.6565),
    "[KH] Bavet (바벳/베트남국경)": (106.1132, 11.0722),

    # 🇻🇳 베트남 (Vietnam)
    "[VN] Ho Chi Minh (호치민)": (106.6297, 10.8231),
    "[VN] Hanoi (하노이)": (105.8542, 21.0285),
    "[VN] Da Nang (다낭)": (108.2022, 16.0544),
    "[VN] Haiphong (하이퐁 항구)": (106.6881, 20.8449),
    "[VN] Vung Tau (붕따우/Cai Mep 항구)": (107.0843, 10.3460),
    "[VN] Moc Bai (목바이/캄보디아국경)": (106.1755, 11.0792),
    "[VN] Quy Nhon (퀴논)": (109.2197, 13.7830)
}

# ---------------------------------------------------------
# 2. 사이드바 (입력창)
# ---------------------------------------------------------
st.sidebar.header("🛠️ 상세 견적 조건")

# API Key 설정 (로컬/클라우드 자동 호환 모드)
api_key = ""

# 1. 시크릿 파일이 있는지 먼저 확인
try:
    if 'ORS_KEY' in st.secrets:
        api_key = st.secrets['ORS_KEY']
except Exception:
    pass

# 2. 없으면 입력창 표시
if not api_key:
    api_key = st.sidebar.text_input("API Key (직접 입력)", type="password")

st.sidebar.subheader("📍 경로 설정 (3단계)")

location_list = list(LOCATIONS.keys())

# 1. 출발지
start_name = st.sidebar.selectbox("1. 출발지", location_list, index=1)

# 2. 경유지
stopover_options = ["(경유지 없음)"] + location_list
stopover_name = st.sidebar.selectbox("2. 경유지 (국경/검문소)", stopover_options, index=0)

# 3. 도착지
end_name = st.sidebar.selectbox("3. 도착지", location_list, index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 단가 설정")
rental_fee_per_day = st.sidebar.number_input("트럭 일대료 ($/day)", value=250)
fuel_cost_per_km = st.sidebar.number_input("km당 운행비 ($/km)", value=0.8)

run_btn = st.sidebar.button("🚀 경로 및 비용 산출")

# ---------------------------------------------------------
# 3. 메인 로직
# ---------------------------------------------------------
st.title("🚛 국제 물류 운송 시뮬레이터 (경유지 포함)")

if 'calculated' not in st.session_state:
    st.session_state['calculated'] = False

if run_btn:
    st.session_state['calculated'] = True

if st.session_state['calculated']:
    if not api_key:
        st.error("API Key가 필요합니다.")
    elif start_name == end_name:
        st.warning("출발지와 도착지가 같습니다.")
    else:
        # 좌표 리스트 구성
        coords = [LOCATIONS[start_name]] # 출발
        
        # 경유지가 있는 경우 중간에 추가
        if stopover_name != "(경유지 없음)":
            coords.append(LOCATIONS[stopover_name])
            
        coords.append(LOCATIONS[end_name]) # 도착
        
        try:
            client = openrouteservice.Client(key=api_key)
            
            with st.spinner('최적 경로 분석 중...'):
                routes = client.directions(
                    coordinates=coords,
                    profile='driving-hgv',
                    format='geojson',
                    extra_info=['surface']
                )

            # 결과 데이터 추출
            summary = routes['features'][0]['properties']['summary']
            total_dist_km = summary['distance'] / 1000
            total_duration_hr = summary['duration'] / 3600
            
            # 비용 계산
            days_needed = total_duration_hr / 8 
            if days_needed < 0.5: days_needed = 0.5
            else: days_needed = round(days_needed, 1)
            
            labor_cost = days_needed * rental_fee_per_day
            driving_cost = total_dist_km * fuel_cost_per_km
            total_est_cost = labor_cost + driving_cost

            # --- 결과 표시 ---
            st.success("✅ 경로 분석 완료")
            
            path_text = f"**{start_name}**"
            if stopover_name != "(경유지 없음)":
                path_text += f" → *{stopover_name}* (경유)"
            path_text += f" → **{end_name}**"
            st.markdown(f"🚩 운행 구간: {path_text}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("총 이동 거리", f"{total_dist_km:.1f} km")
            c2.metric("예상 소요 시간", f"{total_duration_hr:.1f} 시간")
            c3.metric("총 예상 비용", f"${total_est_cost:,.0f}")
            c4.metric("필요 일수", f"{days_needed}일")

            # 상세 내역 표
            cost_df = pd.DataFrame({
                "항목": ["고정비 (일대료)", "변동비 (유류/소모품)", "총 합계"],
                "상세": [f"{days_needed}일 × ${rental_fee_per_day}", f"{total_dist_km:.1f}km × ${fuel_cost_per_km}", "-"],
                "금액": [f"${labor_cost:,.0f}", f"${driving_cost:,.0f}", f"${total_est_cost:,.0f}"]
            })
            st.table(cost_df)

            # 지도 시각화
            if stopover_name != "(경유지 없음)":
                center_loc = [LOCATIONS[stopover_name][1], LOCATIONS[stopover_name][0]]
            else:
                center_loc = [(coords[0][1]+coords[-1][1])/2, (coords[0][0]+coords[-1][0])/2]

            m = folium.Map(location=center_loc, zoom_start=7)

            folium.GeoJson(
                routes, name='운송 경로',
                style_function=lambda x: {'color': 'blue', 'weight': 5, 'opacity': 0.7}
            ).add_to(m)

            # 마커 추가
            folium.Marker([coords[0][1], coords[0][0]], popup="출발", icon=folium.Icon(color='green', icon='play')).add_to(m)
            
            if stopover_name != "(경유지 없음)":
                stop_coord = LOCATIONS[stopover_name]
                folium.Marker([stop_coord[1], stop_coord[0]], popup="경유지", icon=folium.Icon(color='orange', icon='info-sign')).add_to(m)

            folium.Marker([coords[-1][1], coords[-1][0]], popup="도착", icon=folium.Icon(color='red', icon='stop')).add_to(m)

            st_folium(m, width=1000, height=600, returned_objects=[])

        except Exception as e:
            st.error(f"경로 계산 중 오류가 발생했습니다: {e}")
