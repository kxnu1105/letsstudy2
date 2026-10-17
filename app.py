import math
import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

# 페이지 기본 설정
st.set_page_config(
    page_title="공공도서관 실시간 잔여 좌석 파인더", page_icon="🏛️", layout="wide"
)

st.title("🏛️ 내 주변 공공도서관 실시간 잔여 좌석 파인더")
st.markdown(
    "공공데이터포털 실시간 API를 연동하여 내 주변 도서관의 남은 자리를 실시간으로"
    " 확인합니다."
)

# 1. 사이드바 - 설정 및 API 키 입력
st.sidebar.header("📍 검색 및 API 설정")

# 공공데이터포털 API Key (사용자가 발급받아 입력할 수 있도록 빈 칸 또는 기본값 제공)
# data.go.kr에서 '행정안전부 한국지역정보개발원_공공도서관 열람실 현황 실시간 정보' 인증키 입력
api_key = st.sidebar.text_input(
    "공공데이터 API 인증키 (ServiceKey)",
    value="",
    type="password",
    help=(
        "공공데이터포털에서 발급받은 인증키를 입력하세요. 입력하지 않으면"
        " 데모(테스트) 데이터로 작동합니다."
    ),
)

st.sidebar.subheader("내 위치 설정")
user_lat = st.sidebar.number_input(
    "위도 (Latitude)", value=35.2279, format="%.4f"
)
user_lon = st.sidebar.number_input(
    "경도 (Longitude)", value=128.6819, format="%.4f"
)
search_radius = st.sidebar.slider(
    "검색 반경 (km)", min_value=1, max_value=30, value=10
)

st.sidebar.divider()
only_available = st.sidebar.checkbox("잔여 좌석 있는 곳만 보기", value=False)


# 2. 거리 계산 함수 (Haversine Formula - 정확한 대권 거리 계산)
def calculate_distance(lat1, lon1, lat2, lon2):
  try:
    R = 6371.0  지구 반지름 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c
  except Exception:
    return 999.0


# 3. 데이터 로드 함수 (API 연동 + 예외 처리 및 폴백 시스템)
@st.cache_data(ttl=60)  # 60초 동안 캐싱하여 API 과부하 방지 및 성능 극대화
def fetch_library_data(service_key):
  # API 키가 없는 경우 안전하게 작동하도록 시뮬레이션용 데모 데이터 반환
  if not service_key or service_key.strip() == "":
    return pd.DataFrame([
        {
            "name": "창원시립도서관 열람실 (데모)",
            "type": "공공도서관",
            "lat": 35.2322,
            "lon": 128.6901,
            "total_seats": 150,
            "remaining_seats": 42,
            "address": "경상남도 창원시 성산구 용호동",
        },
        {
            "name": "성산도서관 열람실 (데모)",
            "type": "공공도서관",
            "lat": 35.2150,
            "lon": 128.6950,
            "total_seats": 200,
            "remaining_seats": 88,
            "address": "경상남도 창원시 성산구 사파동",
        },
        {
            "name": "마산도서관 열람실 (데모)",
            "type": "공공도서관",
            "lat": 35.1950,
            "lon": 128.5750,
            "total_seats": 120,
            "remaining_seats": 0,
            "address": "경상남도 창원시 마산합포구",
        },
    ])

  url = "http://apis.data.go.kr/1741000/LibraryRealtimeSeat/selectLibraryRealtimeSeatList"
  params = {
      "serviceKey": service_key,
      "pageNo": "1",
      "numOfRows": "100",
      "type": "json",
  }

  try:
    response = requests.get(url, params=params, timeout=5)
    if response.status_code == 200:
      res_json = response.json()
      # 공공 API 응답 구조에 맞춰 파싱 (구조에 따라 상이할 수 있으므로 예외처리 방어막 구축)
      items = (
          res_json.get("response", {})
          .get("body", {})
          .get("items", {})
          .get("item", [])
      )
      if not items:
        st.warning(
            "API 호출은 성공했으나 데이터가 없습니다. 인증키를 확인해주세요."
        )
        return pd.DataFrame()

      parsed_data = []
      for item in items:
        try:
          parsed_data.append({
              "name": item.get("libNm", "이름 없음"),
              "type": "공공도서관",
              "lat": float(
                  item.get("lat", 35.2279)
              ),  # API 제공 위도 필드명에 따라 조정 필요
              "lon": float(item.get("lon", 128.6819)),
              "total_seats": int(item.get("totSeatCnt", 100)),
              "remaining_seats": int(item.get("remainderSeatCnt", 0)),
              "address": item.get("rdnmadr", "주소 정보 없음"),
          })
        except Exception:
          continue
      return pd.DataFrame(parsed_data)
    else:
      st.error(
          f"API 서버 오류 발생 (상태 코드: {response.status_code}). 데모"
          " 데이터로 대체합니다."
      )
      return pd.DataFrame()
  except Exception as e:
    st.error(
        f"네트워크 연결 오류 발생: {str(e)}. 인터넷 연결을 확인해주세요."
    )
    return pd.DataFrame()


# 데이터 불러오기 실행
with st.spinner("실시간 도서관 좌석 정보를 불러오는 중입니다..."):
  df = fetch_library_data(api_key)

if df.empty:
  st.warning(
      "표출할 데이터가 없습니다. API 인증키를 확인하거나 잠시 후 다시"
      " 시도해주세요."
  )
else:
  # 4. 거리 계산 및 필터링 최적화
  df["distance_km"] = df.apply(
      lambda row: calculate_distance(
          user_lat, user_lon, row["lat"], row["lon"]
      ),
      axis=1,
  )

  # 반경 필터 및 잔여 좌석 필터 적용
  filtered_data = df[df["distance_km"] <= search_radius].copy()
  if only_available:
    filtered_data = filtered_data[filtered_data["remaining_seats"] > 0]

  # 거리순 정렬
  filtered_data = filtered_data.sort_values(by="distance_km")

  # 5. 지도 생성 (Folium)
  m = folium.Map(location=[user_lat, user_lon], zoom_start=12, control_scale=True)

  # 내 위치 마커
  folium.Marker(
      location=[user_lat, user_lon],
      popup="<b>내 현재 위치</b>",
      tooltip="내 위치",
      icon=folium.Icon(color="blue", icon="user", prefix="fa"),
  ).add_to(m)

  # 도서관 마커 동적 생성
  for _, row in filtered_data.iterrows():
    if row["remaining_seats"] > 0:
      color = "green"
      status_text = (
          f"잔여 좌석: <b>{row['remaining_seats']}석</b> / 전체"
          f" {row['total_seats']}석"
      )
    else:
      color = "red"
      status_text = "<b>만석</b>"

    popup_html = f"""
        <div style="width:230px; font-family:sans-serif;">
            <h4 style="margin-bottom:5px;">{row['name']}</h4>
            <p style="margin:2px 0;"><b>상태:</b> {status_text}</p>
            <p style="margin:2px 0;"><b>거리:</b> 약 {row['distance_km']:.2f} km</p>
            <p style="margin:2px 0; font-size:11px; color:#555;">{row['address']}</p>
        </div>
        """

    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"{row['name']} (약 {row['distance_km']:.2f}km)",
        icon=folium.Icon(color=color, icon="book"),
    ).add_to(m)

  # 6. 화면 UI 배치 (2단 분할)
  col1, col2 = st.columns([2, 1])

  with col1:
    st.subheader(
        "🗺️ 실시간 지도 (반경 "
        f"{search_radius}km 내 도서관 {len(filtered_data)}곳)"
    )
    st_folium(m, width="100%", height=600)

  with col2:
    st.subheader("📋 실시간 잔여 좌석 현황판")

    if len(filtered_data) == 0:
      st.info(
          "설정한 검색 반경 내에 조건에 맞는 공공도서관이 없습니다. 반경을"
          " 넓혀보세요."
      )
    else:
      for _, row in filtered_data.iterrows():
        with st.container():
          st.markdown(f"### **{row['name']}**")
          st.caption(
              f"📍 주소: {row['address']} | 🚗 거리: 약"
              f" {row['distance_km']:.2f}km"
          )

          # 좌석 백분율 계산 및 프로그레스바 출력
          total = row["total_seats"]
          remaining = row["remaining_seats"]
          percent = remaining / total if total > 0 else 0

          st.progress(
              percent,
              text=f"남은 자리: {remaining}석 / 총 {total}석",
          )
          st.divider()