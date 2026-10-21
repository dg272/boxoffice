import datetime
import requests
import pandas as pd
import pytz
import streamlit as st

# ==========================================
# 1. 페이지 기본 설정 및 스타일 정의
# ==========================================
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 일별 박스오피스 TOP 10")
st.caption("KOBIS(영화관입장권통합전산망) API 연동 앱")

# ==========================================
# 2. 날짜 계산 (한국 표준시 KST 기준)
# Streamlit Cloud 서버 시간과 상관없이 한국 시간으로 어제 날짜를 계산합니다.
# ==========================================
tz_kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(tz_kst)
yesterday_kst = now_kst - datetime.timedelta(days=1)
target_dt = yesterday_kst.strftime("%Y%m%d")  # 예: 20261020
formatted_date = yesterday_kst.strftime("%Y년 %m월 %d일")

st.markdown(f"### 🗓️ 기준일자: **{formatted_date}**")

# ==========================================
# 3. Streamlit Secrets에서 API 키 불러오기
# secrets.toml 또는 Streamlit Cloud Secrets의 KOBIS_KEY 항목 이용
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

# KOBIS는 인증키 오류 시에도 HTTP 200 반환 후 faultInfo 전달
if "faultInfo" in data:
    fault_message = data["faultInfo"].get("message", "알 수 없는 오류가 발생했습니다.")
    st.error(f"❌ API 오류 응답: {fault_message}")
    st.info(
        "💡 **확인 사항:**\n"
        "- `KOBIS_KEY`가 정확하게 입력되었는지 확인해 주세요.\n"
        "- KOBIS 공식 홈페이지에서 발급받은 키의 유효 상태를 확인해 주세요."
    )
    st.stop()

# 응답 데이터 구조 검증 및 빈 목록 확인
boxoffice_result = data.get("boxOfficeResult", {})
movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning("⚠️ 해당 날짜의 박스오피스 데이터가 존재하지 않습니다.")
    st.info(
        "💡 **확인 사항:**\n"
        "- KOBIS 시스템 집계 지연으로 데이터가 아직 제공되지 않았을 수 있습니다.\n"
        "- 잠시 후 다시 시도해 주세요."
    )
    st.stop()

# ==========================================
# 6. 데이터 전처리 (문자열 -> 숫자 변환)
# ==========================================
df = pd.DataFrame(movie_list)

# 필요한 컬럼 정수형 변환
int_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in int_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# ==========================================
# 7. 1위 영화 지표 카드 (Metrics)
# ==========================================
top1_movie = df.iloc[0]

st.divider()
st.subheader(f"🥇 1위: {top1_movie['movieNm']}")

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

df_top5 = df.head(5)[["movieNm", "audiCnt"]].copy()
df_top5.columns = ["영화명", "당일 관객수"]

# 막대그래프 출력
st.bar_chart(
    df_top5,
    x="영화명",
    y="당일 관객수"
)

# ==========================================
# 9. 박스오피스 전체 순위 표 출력
# 순위 · 영화명 · 개봉일 · 관객수 · 누적관객 · 스크린수
# ==========================================
st.divider()
st.subheader("📋 전체 박스오피스 순위")

# 표에 출력할 컬럼 선택 및 이름 변경
df_display = df[[
    "rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"
]].copy()

df_display.columns = [
    "순위", "영화명", "개봉일", "관객수(명)", "누적관객(명)", "스크린수(개)"
]

# 관객수/스크린수 천 단위 콤마 포맷팅 적용 후 표 표시
st.dataframe(
    df_display.style.format({
        "관객수(명)": "{:,}",
        "누적관객(명)": "{:,}",
        "스크린수(개)": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)
