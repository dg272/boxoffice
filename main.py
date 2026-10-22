import datetime
import requests
import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 다크 영화 테마 CSS 적용
# ==========================================
st.set_page_config(
    page_title="시네마 박스오피스",
    page_icon="🎬",
    layout="wide"
)

# 영화 사이트 스타일 커스텀 CSS (다크 스타일, 네온 포인트, 카드 스타일링)
st.markdown("""
    <style>
    /* 전체 배경 다크 톤 적용 */
    .stApp {
        background-color: #0d0f12;
        color: #e0e0e0;
    }
    
    /* 1위 영화 Hero 배너 스타일 */
    .hero-container {
        background: linear-gradient(135deg, #1f1c2c 0%, #928dab 100%);
        border-radius: 16px;
        padding: 30px;
        color: #ffffff;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 10px;
        color: #ffffff;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
    }
    .hero-badge {
        background-color: #e50914; /* 넷플릭스 레드 포인트 */
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.9rem;
        display: inline-block;
        margin-bottom: 15px;
    }
    
    /* 카드 스타일 지표 */
    .metric-card {
        background-color: rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffcc00;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #b0b0b0;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 CINEMA BOX OFFICE")
st.caption("실시간 KOBIS 영화관입장권통합전산망 연동")

# ==========================================
# 2. 날짜 선택 기능 (한국 표준시 KST 기준)
# ==========================================
tz_kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(tz_kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

# 사이드바에 날짜 선택 배치하여 영화 사이트의 필터 메뉴 느낌 적용
with st.sidebar:
    st.header("🔍 날짜 탐색")
    selected_date = st.date_input(
        "조회 일자 선택",
        value=yesterday_kst,
        max_value=yesterday_kst
    )
    st.info("💡 당일 집계 전 데이터는 표시되지 않으므로 '어제' 날짜까지 선택할 수 있습니다.")

target_dt = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

st.markdown(f"#### 🗓️ **{formatted_date}** 일별 순위")

# ==========================================
# 3. Streamlit Secrets에서 API 키 불러오기
# ==========================================
api_key = st.secrets.get("KOBIS_KEY", None)

if not api_key:
    st.error("❌ 비밀 금고(Secrets)에 `KOBIS_KEY` 설정이 되어있지 않습니다.")
    st.info(
        "💡 **확인 방법:**\n"
        "1. **로컬 실행 시**: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = '발급받은키'` 입력\n"
        "2. **Streamlit Cloud 배포 시**: App Settings -> Secrets 메뉴에서 `KOBIS_KEY = '발급받은키'` 설정"
    )
    st.stop()

# ==========================================
# 4. KOBIS API 데이터 요청 함수
# ==========================================
@st.cache_data(ttl=3600)
def fetch_daily_boxoffice(key, target_date):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": key,
        "targetDt": target_date
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"네트워크 요청 중 오류가 발생했습니다: {e}"

data, error_msg = fetch_daily_boxoffice(api_key, target_dt)

# ==========================================
# 5. 예외 및 오류 처리
# ==========================================
if error_msg:
    st.error(f"❌ {error_msg}")
    st.info("💡 인터넷 연결 상태 및 API 주소를 확인해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault_message = data["faultInfo"].get("message", "알 수 없는 오류가 발생했습니다.")
    st.error(f"❌ API 오류 응답: {fault_message}")
    st.info(
        "💡 **확인 사항:**\n"
        "- `KOBIS_KEY`가 정확하게 입력되었는지 확인해 주세요.\n"
        "- KOBIS 공식 홈페이지에서 발급받은 키의 유효 상태를 확인해 주세요."
    )
    st.stop()

boxoffice_result = data.get("boxOfficeResult", {})
movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning("⚠️ 그날은 아직 집계 전입니다.")
    st.info("💡 선택한 날짜의 데이터가 아직 등록되지 않았습니다. 다른 날짜를 선택해 주세요.")
    st.stop()

# ==========================================
# 6. 데이터 전처리 및 가공
# ==========================================
df = pd.DataFrame(movie_list)

int_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in int_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

def format_rank_change(inten):
    if inten > 0:
        return f"🔺 {inten}"
    elif inten < 0:
        return f"🔹 {abs(inten)}"
    else:
        return "-"

df["rank_change"] = df["rankInten"].apply(format_rank_change)

def format_movie_name(row):
    name = row["movieNm"]
    acc_cnt = row["audiAcc"]
    
    if acc_cnt >= 10_000_000:
        return f"👑 {name}"
    elif acc_cnt >= 1_000_000:
        return f"🏆 {name}"
    return name

df["movieNm_display"] = df.apply(format_movie_name, axis=1)

# ==========================================
# 7. 1위 영화 HERO 배너 섹션 (영화 플랫폼 스타일)
# ==========================================
top1_movie = df.iloc[0]

st.markdown(f"""
    <div class="hero-container">
        <div class="hero-badge">🔥 DAILY NO.1</div>
        <div class="hero-title">{top1_movie['movieNm_display']}</div>
        <p style="color: #e0e0e0; margin-bottom: 20px;">개봉일: {top1_movie['openDt']}</p>
        <div style="display: flex; gap: 15px;">
            <div class="metric-card" style="flex: 1;">
                <div class="metric-value">{top1_movie['audiCnt']:,} 명</div>
                <div class="metric-label">일일 관객수</div>
            </div>
            <div class="metric-card" style="flex: 1;">
                <div class="metric-value">{top1_movie['audiAcc']:,} 명</div>
                <div class="metric-label">누적 관객수</div>
            </div>
            <div class="metric-card" style="flex: 1;">
                <div class="metric-value">{top1_movie['scrnCnt']:,} 개</div>
                <div class="metric-label">스크린 수</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 8. 차트 영역 (다크 테마 적용)
# ==========================================
st.subheader("📊 차트 분석")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**■ 당일 관객수 TOP 5**")
    df_top5 = df.head(5)[["movieNm_display", "audiCnt"]].copy()
    df_top5.columns = ["영화명", "당일 관객수"]

    st.bar_chart(
        df_top5,
        x="영화명",
        y="당일 관객수"
    )

with chart_col2:
    st.markdown("**■ TOP 10 누적 관객수 비율**")
    
    # 다크 모드용 컬러 팔레트 적용
    fig_pie = px.pie(
        df,
        names="movieNm_display",
        values="audiAcc",
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Darkmint
    )
    
    fig_pie.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate="<b>%{label}</b><br>누적 관객수: %{value:,} 명<br>비율: %{percent}<extra></extra>"
    )
    
    fig_pie.update_layout(
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ffffff'),
        hoverlabel=dict(bgcolor="#1f1c2c", font_color="#ffffff", font_size=13),
        margin=dict(t=20, b=20, l=20, r=20)
    )
    
    st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# 9. 박스오피스 전체 순위 표 출력
# ==========================================
st.divider()
st.subheader("📋 박스오피스 전체 순위")

df_display = df[[
    "rank", "rank_change", "movieNm_display", "openDt", "audiCnt", "audiAcc", "scrnCnt"
]].copy()

df_display.columns = [
    "순위", "순위 변동", "영화명", "개봉일", "관객수(명)", "누적관객(명)", "스크린수(개)"
]

st.dataframe(
    df_display.style.format({
        "관객수(명)": "{:,}",
        "누적관객(명)": "{:,}",
        "스크린수(개)": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)
