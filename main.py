import datetime
import requests
import pandas as pd
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
# 선택 가능한 최대 날짜는 '어제'로 제한 (오늘 데이터는 미집계)
# ==========================================
tz_kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(tz_kst)
yesterday_kst = (now_kst - datetime.timedelta(days=1)).date()

# 달력 위젯 생성 (기본값: 어제, 최대값: 어제)
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday_kst,
    max_value=yesterday_kst
)

# API 요청용 날짜 문자열 변환 (YYYYMMDD)
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
@st.cache_data(ttl=3600)  # 1시간 동안 응답 데이터 캐싱
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

# KOBIS 오류 응답 처리 (faultInfo)
if "faultInfo" in data:
    fault_message = data["faultInfo"].get("message", "알 수 없는 오류가 발생했습니다.")
    st.error(f"❌ API 오류 응답: {fault_message}")
    st.info(
        "💡 **확인 사항:**\n"
        "- `KOBIS_KEY`가 정확하게 입력되었는지 확인해 주세요.\n"
        "- KOBIS 공식 홈페이지에서 발급받은 키의 유효 상태를 확인해 주세요."
    )
    st.stop()

# 영화 목록 검증 (비어있을 경우 지정된 메시지 출력)
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

# 숫자로 변환할 컬럼 지정
int_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in int_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 1) 순위 변동(rankInten) 텍스트 및 화살표 가공 함수
def format_rank_change(inten):
    if inten > 0:
        return f"🔺 {inten}"  # 순위 상승 (빨간 위 화살표)
    elif inten < 0:
        return f"🔹 {abs(inten)}"  # 순위 하강 (파란 아래 화살표)
    else:
        return "-"  # 변동 없음

df["rank_change"] = df["rankInten"].apply(format_rank_change)

# 2) 누적 관객 100만 명 이상 트로피 이모지 추가 함수
def format_movie_name(row):
    name = row["movieNm"]
    if row["audiAcc"] >= 1_000_000:
        return f"🏆 {name}"
    return name

df["movieNm_display"] = df.apply(format_movie_name, axis=1)

# ==========================================
# 7. 1위 영화 지표 카드 (Metrics)
# ==========================================
top1_movie = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위: {top1_movie['movieNm_display']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="당일 관객수",
        value=f"{top1_movie['audiCnt']:,} 명"
    )
with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top1_movie['audiAcc']:,} 명"
    )
with col3:
    st.metric(
        label="스크린 수",
        value=f"{top1_movie['scrnCnt']:,} 개"
    )

# ==========================================
# 8. 상위 5개 영화 관객수 막대그래프
# ==========================================
st.divider()
st.subheader("📊 관객수 TOP 5 시각화")

df_top5 = df.head(5)[["movieNm_display", "audiCnt"]].copy()
df_top5.columns = ["영화명", "당일 관객수"]

st.bar_chart(
    df_top5,
    x="영화명",
    y="당일 관객수"
)

# ==========================================
# 9. 박스오피스 전체 순위 표 출력
# ==========================================
st.divider()
st.subheader("📋 전체 박스오피스 순위")

# 표에 보여줄 컬럼 선택 및 정렬
df_display = df[[
    "rank", "rank_change", "movieNm_display", "openDt", "audiCnt", "audiAcc", "scrnCnt"
]].copy()

df_display.columns = [
    "순위", "순위 변동", "영화명", "개봉일", "관객수(명)", "누적관객(명)", "스크린수(개)"
]

# 표 출력 (숫자 콤마 포맷팅 적용)
st.dataframe(
    df_display.style.format({
        "관객수(명)": "{:,}",
        "누적관객(명)": "{:,}",
        "스크린수(개)": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)
