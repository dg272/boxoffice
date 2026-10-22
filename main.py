import datetime
import requests
import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 스타일 정의
# ==========================================
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 조회")
st.caption("KOBIS(영화관입장권통합전산망) API 연동 앱")

# ==========================================
# 2. 날짜 선택 기능 (한국 표준시 KST 기준)
# ==========================================
tz_kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(tz_kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday_kst,
    max_value=yesterday_kst
)

target_dt = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")

st.markdown(f"### 🗓️ 선택한 일자: **{formatted_date}**")

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

default_poster_url = "https://via.placeholder.com/150x220?text=No+Poster"
df["poster_url"] = default_poster_url

# ==========================================
# 7. 1위 영화 지표 카드 (Metrics)
# ==========================================
top1_movie = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위: {top1_movie['movieNm_display']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="당일 관객수", value=f"{top1_movie['audiCnt']:,} 명")
with col2:
    st.metric(label="누적 관객수", value=f"{top1_movie['audiAcc']:,} 명")
with col3:
    st.metric(label="스크린 수", value=f"{top1_movie['scrnCnt']:,} 개")

# ==========================================
# 8. 차트 영역 (막대그래프 & 원그래프 나란히 배치)
# ==========================================
st.divider()
st.subheader("📊 박스오피스 시각화")

# 화면을 두 개의 열로 나누어 좌측엔 당일 관객(막대), 우측엔 누적 관객(파이) 배치
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**■ 당일 관객수 TOP 5 (막대그래프)**")
    df_top5 = df.head(5).copy()
    
    fig_bar = px.bar(
        df_top5,
        x="movieNm_display",
        y="audiCnt",
        labels={"movieNm_display": "영화명", "audiCnt": "당일 관객수"},
        hover_data={
            "movieNm_display": True,
            "audiCnt": ":,",
            "audiAcc": ":,",
            "poster_url": True
        }
    )

    fig_bar.update_traces(
        hovertemplate="""
        <b>%{x}</b><br><br>
        <img src='%{customdata[2]}' width='120'><br><br>
        <b>당일 관객수:</b> %{y:,} 명<br>
        <b>누적 관객수:</b> %{customdata[1]:,} 명
        <extra></extra>
        """,
        customdata=df_top5[["movieNm", "audiAcc", "poster_url"]].values
    )

    fig_bar.update_layout(
        xaxis_title="영화명",
        yaxis_title="당일 관객수",
        hoverlabel=dict(bgcolor="white", font_size=13)
    )
    fig_bar.update_xaxes(fixedrange=True)
    fig_bar.update_yaxes(fixedrange=True)

    st.plotly_chart(fig_bar, use_container_width=True, config={'scrollZoom': False})

with chart_col2:
    st.markdown("**■ TOP 10 누적 관객수 비율 (원그래프)**")
    
    # 누적 관객수 원그래프 생성 (TOP 10 전체)
    fig_pie = px.pie(
        df,
        names="movieNm_display",
        values="audiAcc",
        hole=0.3  # 가운데가 살짝 뚫린 도넛 형태로 만들어 시각적 효과 향상
    )
    
    fig_pie.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate="<b>%{label}</b><br>누적 관객수: %{value:,} 명<br>비율: %{percent}<extra></extra>"
    )
    
    fig_pie.update_layout(
        showlegend=False, # 라벨이 내부에 표시되므로 범례 숨김
        hoverlabel=dict(bgcolor="white", font_size=13)
    )
    
    st.plotly_chart(fig_pie, use_container_width=True, config={'scrollZoom': False})

# ==========================================
# 9. 박스오피스 전체 순위 표 출력
# ==========================================
st.divider()
st.subheader("📋 전체 박스오피스 순위")

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
