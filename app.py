# -*- coding: utf-8 -*-
"""
DART 대시보드 (PE/VC용) - 1차 버전
====================================
왼쪽 사이드바에서 탭을 골라 각 데이터를 조회합니다.

  1) 상장사 실적 비교 (연간/분기)  ... 다중회사 주요계정 API
  2) 최근 상장/공모 현황            ... 공시검색 API (증권신고서 트래커)
  3) 발행내역 (유상증자 / CB / BW)  ... 주요사항보고서 API
  4) 기타공시 (자기주식 취득/처분)  ... 주요사항보고서 API
  5) 밸류에이션 (공모가 산정근거)   ... 증권신고서 원문 링크 (파싱은 다음 단계)

▶ 실행 방법 : 터미널에서   streamlit run app.py
▶ 데이터 출처 : 금융감독원 OpenDART (https://opendart.fss.or.kr)
"""

import io
import re
import json
import zipfile
import datetime as dt
import xml.etree.ElementTree as ET

import requests
import pandas as pd
import streamlit as st

# DART API 기본 주소
DART_API = "https://opendart.fss.or.kr/api"
# 공시 원문(사람이 보는 페이지) 주소 앞부분. 뒤에 접수번호(rcept_no)를 붙이면 됩니다.
DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="


# ------------------------------------------------------------------
# 0. 페이지 기본 설정
# ------------------------------------------------------------------
st.set_page_config(page_title="Mezzanine Look-up & Analysis · 안다아시아벤처스",
                   page_icon="📈", layout="wide")

# ------------------------- 전체 디자인(스타일) -------------------------
st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

    :root{
      --brand:#2F6FE0; --brand-ink:#1C4FB0; --sky:#E8F1FD; --sky-hover:#F0F6FE;
      --ink:#1A2330; --ink-2:#3A4656; --muted:#6B7788; --line:#E4E9F0;
      --bg:#F4F6FA; --surface:#FFFFFF;
    }

    /* 폰트 (전체적으로 키움: 본문 16px ≈ 나눔고딕 11pt) */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"]{
      font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI','Malgun Gothic',sans-serif;
    }
    [data-testid="stAppViewContainer"]{background:var(--bg);}
    html, body{font-size:16px;}

    /* 상단 툴바·장식 정리 + 여백 */
    [data-testid="stToolbar"]{visibility:hidden;height:0;}
    [data-testid="stDecoration"]{display:none;}
    [data-testid="stHeader"]{background:transparent;}
    .block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1460px;}

    /* 본문 텍스트 (대비 강화 + 크기 up) */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li{font-size:16px !important;color:var(--ink-2);}
    [data-testid="stWidgetLabel"] p, label p{font-size:15px !important;color:#2A3545 !important;font-weight:600;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p{
      color:var(--muted) !important;font-size:13.5px !important;}

    /* 헤더 */
    h1,h2,h3,h4{color:var(--ink);font-weight:700;letter-spacing:-.3px;}
    h1{font-size:30px;}
    h2{font-size:22px;padding-bottom:10px;border-bottom:2px solid var(--line);margin-bottom:8px;}
    h3{font-size:18px;color:#22303F;}
    h4{font-size:16.5px;color:#2A3A4C;margin-top:8px;}

    /* 버튼 (하늘색 계열) */
    .stButton button{
      background:var(--brand);color:#fff;border:0;border-radius:9px;
      padding:.55rem 1.5rem;font-weight:600;font-size:15px;
      box-shadow:0 1px 3px rgba(47,111,224,.25);transition:.15s;
    }
    .stButton button:hover{background:var(--brand-ink);box-shadow:0 4px 12px rgba(47,111,224,.3);}
    /* 버튼 글씨가 버튼 색을 따라가도록(파란 버튼=흰 글씨). 중첩 마크다운 p의 검은색 방지 */
    .stButton button p, .stButton button span, .stButton button div{color:inherit !important;}

    /* 체크박스·라디오 '선택칸' 테두리를 파랗게(잘 보이게) */
    [data-baseweb="checkbox"] > span:first-child,
    [data-baseweb="checkbox"] > div:first-child,
    [data-testid="stCheckbox"] label > span:first-child,
    [data-baseweb="radio"] > div:first-child,
    [data-baseweb="radio"] > span:first-child,
    [data-testid="stRadio"] [role="radio"] > div:first-child{
      border-color:var(--brand) !important;border-width:2px !important;}

    /* 입력창·드롭다운 — '누를 수 있는 칸'으로 또렷하게 (테두리·배경·포커스링) */
    [data-baseweb="input"],
    [data-baseweb="select"] > div,
    [data-baseweb="textarea"]{
      border:1.6px solid #6F9BE8 !important;
      border-radius:9px !important;
      background:#FFFFFF !important;
      font-size:15px;
      box-shadow:0 1px 2px rgba(20,36,59,.05);
      transition:border-color .15s, box-shadow .15s;
    }
    [data-baseweb="input"]:hover,
    [data-baseweb="select"] > div:hover,
    [data-baseweb="textarea"]:hover{border-color:var(--brand) !important;}
    [data-baseweb="input"]:focus-within,
    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="textarea"]:focus-within{
      border-color:var(--brand) !important;
      box-shadow:0 0 0 3px rgba(47,111,224,.18) !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] input,
    [data-baseweb="input"] input{color:var(--ink);}
    /* 셀렉트박스: 클릭 가능 + 화살표(▾) 또렷하게 */
    [data-baseweb="select"]{cursor:pointer;}
    [data-baseweb="select"] svg{color:var(--brand) !important;opacity:1 !important;width:22px;height:22px;}
    /* 위젯 라벨 위에 작은 안내가 잘 보이도록 */
    [data-testid="stWidgetLabel"] p, label p{margin-bottom:4px;}

    /* 지표 카드(st.metric) — 흰 카드로 */
    [data-testid="stMetric"]{
      background:var(--surface);border:1px solid var(--line);border-radius:12px;
      padding:14px 18px;box-shadow:0 1px 3px rgba(20,36,59,.05);}
    [data-testid="stMetricLabel"] p{font-size:14px !important;color:var(--muted) !important;}
    [data-testid="stMetricValue"]{font-size:26px;color:var(--ink);font-weight:700;}

    /* HTML 표(fs-table) — 나눔고딕·크게·대비 up */
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Gothic:wght@400;700;800&display=swap');
    .fs-table{border-collapse:collapse;width:100%;font-size:16.5px;margin:2px 0 18px;
      font-family:'Nanum Gothic','나눔고딕',Pretendard,-apple-system,sans-serif;}
    .fs-table thead th{background:#EEF3FA;color:#2A3A4C;font-weight:700;font-size:16.5px;
      border-bottom:2px solid #D7E0EC;position:sticky;top:0;}
    .fs-table th,.fs-table td{padding:10px 14px;border-bottom:1px solid #EDF1F6;white-space:nowrap;color:var(--ink);}
    .fs-table a{color:var(--brand);text-decoration:none;font-weight:600;}
    .fs-table a:hover{text-decoration:underline;}
    .fs-table tbody tr:hover td{background:var(--sky-hover);}
    .fs-table td,.fs-table th{text-align:right;}
    .fs-table td:first-child,.fs-table th:first-child{text-align:left;font-weight:600;color:#1F2C3A;}

    /* Streamlit 기본 표 (대비·크기) */
    [data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden;
      box-shadow:0 1px 3px rgba(20,36,59,.05);}
    [data-testid="stDataFrame"] *{font-size:15px !important;color:var(--ink) !important;}

    /* ---------- 사이드바 (FineBI/Teams 느낌) ---------- */
    [data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--line);min-width:290px;}
    [data-testid="stSidebar"] .block-container{padding-top:1.4rem;}
    .brand{padding:2px 2px 16px;margin-bottom:10px;border-bottom:1px solid var(--line);}
    .brand .bar{width:36px;height:4px;border-radius:3px;background:var(--brand);margin-bottom:12px;}
    .brand .name{font-size:25px;font-weight:800;color:var(--ink);letter-spacing:-.4px;line-height:1.2;}
    .brand .sub{font-size:13px;color:var(--muted);margin-top:6px;}

    /* 사이드바 메뉴(radio)를 간격 넓은 메뉴 항목으로 */
    [data-testid="stSidebar"] [role="radiogroup"]{gap:4px;}
    [data-testid="stSidebar"] [role="radiogroup"] label{
      display:flex;align-items:center;width:100%;
      padding:11px 14px;margin:3px 0;border-radius:10px;
      cursor:pointer;transition:background .15s, color .15s;font-size:15.5px;}
    [data-testid="stSidebar"] [role="radiogroup"] label p{
      font-size:15.5px !important;color:#45505F !important;font-weight:500;margin:0;}
    [data-testid="stSidebar"] [role="radiogroup"] label:hover{background:var(--sky-hover);}
    /* 선택된 메뉴: 연한 하늘색 + 파란 글씨 + 왼쪽 악센트 */
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){
      background:var(--sky);box-shadow:inset 3px 0 0 var(--brand);}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{
      color:var(--brand-ink) !important;font-weight:700;}
    /* 라디오 동그라미 숨김 */
    [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{display:none;}

    /* ---------- 사이드바 메뉴(button 방식) ---------- */
    [data-testid="stSidebar"] .nav-sec{
      margin:.65rem 0 .1rem;font-weight:700;font-size:13px;
      color:var(--brand);letter-spacing:.3px;}
    /* 메뉴(nav) 버튼만 '메뉴 항목' 스타일. (st-key-nav_btn 클래스로 한정 → '적용' 등 일반 버튼 제외) */
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button{
      width:100%;justify-content:flex-start;text-align:left;
      background:transparent;color:#45505F;border:0;box-shadow:none;
      font-weight:500;font-size:15.5px;padding:10px 14px;margin:2px 0;border-radius:10px;}
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button:hover{
      background:var(--sky-hover);color:#45505F;box-shadow:none;}
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button p{
      font-size:15.5px !important;font-weight:inherit;color:inherit !important;margin:0;}
    /* 선택된 메뉴(primary): 연한 하늘색 + 파란 글씨 + 왼쪽 악센트 */
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button[kind="primary"],
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button[data-testid="baseButton-primary"],
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button[data-testid="stBaseButton-primary"]{
      background:var(--sky);color:var(--brand-ink);font-weight:700;
      box-shadow:inset 3px 0 0 var(--brand);}
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button[data-testid="baseButton-primary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-nav_btn"] button[data-testid="stBaseButton-primary"]:hover{
      background:var(--sky);color:var(--brand-ink);}

    /* 라디오(본문 가로형: 유형 선택 등)도 또렷하게 */
    [role="radiogroup"] label p{color:#2A3545 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# 1. 사이드바 : API 키 입력 + 메뉴
# ------------------------------------------------------------------
st.sidebar.markdown(
    '<div class="brand"><div class="bar"></div>'
    '<div class="name">Mezzanine<br>Look-up &amp; Analysis</div>'
    '<div class="sub">안다아시아벤처스 · DART 기반 분석</div></div>',
    unsafe_allow_html=True,
)

# 키를 매번 입력하기 싫으면 .streamlit/secrets.toml 에 DART_API_KEY 를 넣어두면 자동으로 채워집니다.
default_key = ""
try:
    default_key = st.secrets.get("DART_API_KEY", "")
except Exception:
    default_key = ""

st.sidebar.markdown("**DART 인증키 (40자리)**")
_kc1, _kc2 = st.sidebar.columns([3, 1])
api_key = _kc1.text_input(
    "DART 인증키",
    value=default_key,
    type="password",
    label_visibility="collapsed",
    placeholder="키 입력 후 '적용' →",
    key="dart_key_input",
    help="opendart.fss.or.kr 에서 발급받은 키를 붙여넣고 '적용'을 누르세요.",
)
_kc2.button("적용", key="dart_key_apply", use_container_width=True,
            help="입력한 키를 반영합니다. (Enter 를 눌러도 됩니다)")
if not api_key:
    st.sidebar.caption("👆 DART 인증키를 넣고 **적용**(또는 Enter)을 누르면 대시보드가 열립니다.")

# 공모 상세 AI 분석용 Anthropic 키 (선택). 없으면 공모 AI 분석만 비활성.
default_anthropic = ""
try:
    default_anthropic = st.secrets.get("ANTHROPIC_API_KEY", "")
except Exception:
    default_anthropic = ""

anthropic_key = st.sidebar.text_input(
    "Anthropic API 키 (공모 AI 분석용)",
    value=default_anthropic,
    type="password",
    help="console.anthropic.com 에서 발급. '최근 상장/공모 현황' 탭의 공모 상세 분석에만 쓰입니다.",
)
ai_model = st.sidebar.text_input(
    "AI 모델",
    value="claude-haiku-4-5-20251001",
    help="저렴한 haiku 권장. 계정에서 쓸 수 있는 모델 ID로 바꿔도 됩니다.",
)


# ------------------------------------------------------------------
# 2. 공통 함수들
# ------------------------------------------------------------------
class DartError(Exception):
    """DART API가 정상(000)이 아닐 때 던지는 오류."""
    pass


# DART가 돌려주는 상태코드별 안내 문구
STATUS_MSG = {
    "010": "등록되지 않은 인증키입니다.",
    "011": "사용할 수 없는 인증키입니다. (일시 중지 상태)",
    "013": "조회된 데이터가 없습니다.",
    "020": "요청 제한을 초과했습니다. (하루 사용 한도 초과)",
    "100": "필수 입력값이 잘못되었습니다.",
    "800": "시스템 점검 중입니다.",
    "900": "알 수 없는 오류가 발생했습니다.",
}


def dart_get(endpoint: str, params: dict) -> list:
    """DART API를 호출해서 결과(list)를 돌려준다. 데이터가 없으면 빈 리스트."""
    if not api_key:
        raise DartError("먼저 왼쪽 사이드바에 DART 인증키를 입력하세요.")
    query = dict(params)
    query["crtfc_key"] = api_key
    resp = requests.get(f"{DART_API}/{endpoint}", params=query, timeout=30)
    data = resp.json()
    status = data.get("status")
    if status == "000":            # 정상
        return data.get("list", [])
    if status == "013":            # 데이터 없음 → 오류가 아니라 빈 결과로 처리
        return []
    raise DartError(STATUS_MSG.get(status, f"오류({status}) {data.get('message', '')}"))


def _list_page(base_params: dict, page: int) -> dict:
    """공시검색(list.json)의 한 페이지 원본(dict)을 그대로 돌려준다."""
    q = dict(base_params)
    q["crtfc_key"] = api_key
    q["page_no"] = str(page)
    q["page_count"] = "100"          # 페이지당 최대 100건
    r = requests.get(f"{DART_API}/list.json", params=q, timeout=30)
    data = r.json()
    status = data.get("status")
    if status == "000":
        return data
    if status == "013":              # 데이터 없음
        return {"list": [], "total_page": 0, "total_count": 0}
    raise DartError(STATUS_MSG.get(status, f"오류({status}) {data.get('message', '')}"))


def dart_list_all(base_params: dict, max_pages: int = 100):
    """
    공시검색 결과를 '모든 페이지'에 걸쳐 이어서 가져온다.
    반환: (전체 목록, 총건수, 잘렸는지 여부)
    max_pages 는 과도한 호출을 막는 안전장치(기본 100페이지 = 최대 1만건).
    """
    first = _list_page(base_params, 1)
    out = list(first.get("list", []))
    total_count = int(first.get("total_count", len(out)) or 0)
    total_page = int(first.get("total_page", 1) or 1)
    pages = min(total_page, max_pages)
    for page in range(2, pages + 1):
        out.extend(_list_page(base_params, page).get("list", []))
    capped = total_page > max_pages
    return out, total_count, capped


@st.cache_data(show_spinner="기업 고유번호(corp_code) 목록을 처음 한 번 내려받는 중...")
def load_corp_codes(key: str) -> pd.DataFrame:
    """
    전체 기업의 corp_code <-> 회사명 <-> 종목코드 매핑표를 내려받아 캐시한다.
    DART의 모든 조회는 종목코드가 아니라 corp_code(8자리)로 하기 때문에 이 표가 꼭 필요하다.
    """
    resp = requests.get(f"{DART_API}/corpCode.xml", params={"crtfc_key": key}, timeout=60)
    zf = zipfile.ZipFile(io.BytesIO(resp.content))       # 응답은 zip 파일
    xml_bytes = zf.read(zf.namelist()[0])                # 그 안의 CORPCODE.xml
    root = ET.fromstring(xml_bytes)
    rows = []
    for node in root.iter("list"):
        rows.append({
            "corp_code": (node.findtext("corp_code") or "").strip(),
            "corp_name": (node.findtext("corp_name") or "").strip(),
            "stock_code": (node.findtext("stock_code") or "").strip(),
        })
    return pd.DataFrame(rows)


def resolve_corp(name: str, corp_df: pd.DataFrame):
    """회사명(또는 6자리 종목코드)으로 회사 1곳을 찾는다. 상장사를 우선한다."""
    name = (name or "").strip()
    if not name:
        return None
    # 6자리 종목코드로 들어온 경우
    if name.isdigit() and len(name) == 6:
        hit = corp_df[corp_df["stock_code"] == name]
        if len(hit):
            return hit.iloc[0]
    # 이름이 정확히 같은 경우 (상장사 우선)
    exact = corp_df[corp_df["corp_name"] == name]
    listed = exact[exact["stock_code"] != ""]
    if len(listed):
        return listed.iloc[0]
    if len(exact):
        return exact.iloc[0]
    # 부분 일치 (상장사 우선)
    part = corp_df[corp_df["corp_name"].str.contains(name, na=False, regex=False)]
    listed = part[part["stock_code"] != ""]
    if len(listed):
        return listed.iloc[0]
    if len(part):
        return part.iloc[0]
    return None


def to_num(x):
    """'1,234,567' 같은 문자열 금액을 숫자로. 안 되면 None."""
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def eok(x):
    """원 단위 금액 문자열을 억원으로 (반올림)."""
    v = to_num(x)
    return round(v / 1e8) if v is not None else None


@st.cache_data(show_spinner="재무제표를 불러오는 중...")
def fetch_full_fs(key: str, corp_code: str, year: int, reprt_code: str, fs_div: str) -> list:
    """
    단일회사 '전체 재무제표'(모든 계정과목)를 조회한다. (fnlttSinglAcntAll)
    응답의 sj_div 값으로 재무제표 종류를 구분한다:
      BS=재무상태표, IS=손익계산서, CIS=포괄손익계산서, CF=현금흐름표, SCE=자본변동표
    ※ 금융업(은행·보험 등)은 이 API 대상에서 제외됩니다.
    """
    q = {
        "crtfc_key": key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": reprt_code,
        "fs_div": fs_div,          # OFS=별도, CFS=연결
    }
    resp = requests.get(f"{DART_API}/fnlttSinglAcntAll.json", params=q, timeout=30)
    data = resp.json()
    status = data.get("status")
    if status == "000":
        return data.get("list", [])
    if status == "013":
        return []
    raise DartError(STATUS_MSG.get(status, f"오류({status}) {data.get('message', '')}"))


# 정기보고서 종류 → DART 코드
REPORT_CODES = {
    "사업보고서(연간)": "11011",
    "반기보고서": "11012",
    "1분기보고서": "11013",
    "3분기보고서": "11014",
}


def _fmt_cell(v):
    """숫자면 천단위 콤마(정수는 소수 없이, 소수는 2자리), 글자면 그대로, 비었으면 '-'."""
    try:
        if pd.isna(v):
            return "-"
    except (TypeError, ValueError):
        pass
    if v in (None, "", []):
        return "-"
    try:
        f = float(v)                # 숫자(또는 순수 숫자문자열)일 때
    except (ValueError, TypeError):
        return str(v)               # 글자(문자열)는 그대로
    if f.is_integer():
        return f"{f:,.0f}"          # 정수: 1,234
    return f"{f:,.2f}"              # 소수: 2.50, 1,234.56


def show_fs_table(df, dl_stem=None, dl_key=None):
    """표를, 천단위 콤마(숫자)·글자 그대로가 섞여도 안전하게 HTML 표로 출력한다.
    dl_stem/dl_key를 주면 표 아래에 엑셀/CSV 다운로드 버튼을 추가한다."""
    disp = df.reset_index()
    first_col = disp.columns[0]           # 첫 열 = 계정/항목명 (콤마 처리 제외)
    raw = disp.copy()                     # 다운로드용 원본(숫자 그대로)
    for c in disp.columns:
        if c != first_col:
            disp[c] = disp[c].map(_fmt_cell)
    html = disp.to_html(index=False, classes="fs-table", border=0)
    st.markdown(f'<div style="overflow-x:auto">{html}</div>', unsafe_allow_html=True)
    if dl_stem:
        _download_buttons(raw, dl_stem, dl_key)


# ------------------------------------------------------------------
# 공용: 표 출력(천단위 콤마) + 엑셀/CSV 다운로드 버튼
# ------------------------------------------------------------------
# 숫자 서식을 넣지 않을(=날짜·텍스트) 열 이름 힌트
_NONNUM_HINT = ("일", "시작", "종료", "기간", "구분", "방식", "상장", "회사", "종목명",
                "제출", "보고서", "원문", "유형", "회차", "항목", "회차수")


def _excel_bytes(df):
    """DataFrame을 엑셀(xlsx) 바이트로. openpyxl 없으면 None."""
    import io as _io
    try:
        buf = _io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="data")
        return buf.getvalue()
    except Exception:
        return None


def _download_buttons(df, stem, key):
    """엑셀 우선, 안 되면 CSV 다운로드 버튼."""
    xls = _excel_bytes(df)
    if xls is not None:
        st.download_button("⬇ 엑셀 다운로드 (.xlsx)", data=xls, file_name=f"{stem}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=key)
    else:
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ CSV 다운로드 (엑셀에서 열기)", data=csv, file_name=f"{stem}.csv",
                           mime="text/csv", key=key,
                           help="엑셀(.xlsx) 저장을 쓰려면 터미널에서 'python -m pip install openpyxl' 후 재실행하세요.")


def _num_col():
    """천단위 콤마(14,052) NumberColumn. 구버전 Streamlit이면 None(기본 렌더)."""
    try:
        return st.column_config.NumberColumn(format="localized")
    except Exception:
        return None


def show_table(df, stem, key, link_cols=()):
    """표를 '큰 글씨 HTML 표'로 보여준다(나눔고딕·천단위 콤마·원문 링크). 아래에 엑셀/CSV 다운로드 버튼.
    - st.dataframe(캔버스 표)은 CSS 폰트가 안 먹어 작게 보이므로, 가독성을 위해 HTML 표로 렌더한다.
    - link_cols: 'http…' 값을 '원문' 링크로 렌더할 열 이름들
    - 날짜·텍스트로 보이는 열(_NONNUM_HINT 포함)은 콤마 서식을 넣지 않음"""
    import html as _html
    disp = df.reset_index(drop=True)
    cols = list(disp.columns)
    numeric_cols = set()
    for c in cols:
        if c in link_cols or any(h in str(c) for h in _NONNUM_HINT):
            continue
        if pd.to_numeric(disp[c], errors="coerce").notna().any():
            numeric_cols.add(c)

    thead = "".join(f"<th>{_html.escape(str(c))}</th>" for c in cols)
    rows_html = []
    for _, row in disp.iterrows():
        tds = []
        for c in cols:
            v = row[c]
            if c in link_cols:
                url = "" if v is None else str(v)
                cell = (f'<a href="{_html.escape(url)}" target="_blank">원문</a>'
                        if url.lower().startswith("http") else "-")
            elif c in numeric_cols:
                cell = _html.escape(_fmt_cell(v))
            else:
                try:
                    empty = bool(pd.isna(v))
                except (TypeError, ValueError):
                    empty = False
                cell = "-" if (empty or v in (None, "", [])) else _html.escape(str(v))
            tds.append(f"<td>{cell}</td>")
        rows_html.append("<tr>" + "".join(tds) + "</tr>")

    table = (f'<div style="max-height:600px;overflow:auto">'
             f'<table class="fs-table"><thead><tr>{thead}</tr></thead>'
             f'<tbody>{"".join(rows_html)}</tbody></table></div>')
    st.markdown(table, unsafe_allow_html=True)
    _download_buttons(df, stem, key)


# ==================================================================
#  공모 상세 AI 분석  (증권신고서 원문 → 필요한 부분만 잘라 → AI 추출)
# ==================================================================
@st.cache_data(show_spinner=False)
def fetch_dart_document(key: str, rcept_no: str) -> str:
    """공시서류 원문(document API)을 받아 태그를 제거한 순수 텍스트로 돌려준다."""
    resp = requests.get(f"{DART_API}/document.xml",
                        params={"crtfc_key": key, "rcept_no": rcept_no}, timeout=90)
    content = resp.content
    if not zipfile.is_zipfile(io.BytesIO(content)):
        msg = content.decode("utf-8", "ignore")[:200]
        raise DartError("원문(문서 API)을 가져오지 못했습니다. " + msg)
    zf = zipfile.ZipFile(io.BytesIO(content))
    parts = []
    for name in zf.namelist():
        raw = zf.read(name)
        text = None
        for enc in ("utf-8", "cp949", "euc-kr"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        parts.append(text if text is not None else raw.decode("utf-8", "ignore"))
    full = "\n".join(parts)
    # 태그·특수문자 제거 → 사람이 읽는 텍스트만 남김
    full = re.sub(r"(?is)<(style|script).*?</\1>", " ", full)
    full = re.sub(r"(?s)<[^>]+>", " ", full)
    full = re.sub(r"&nbsp;|&[a-zA-Z#0-9]+;", " ", full)
    full = re.sub(r"[ \t ]+", " ", full)
    full = re.sub(r"\n\s*\n+", "\n", full)
    return full.strip()


def slice_offering_sections(text: str, max_chars: int = 45000) -> str:
    """원문에서 공모 관련 섹션만 키워드로 잘라 붙인다. (AI에 보낼 양=비용을 줄이는 핵심)"""
    anchors = [
        ("공모개요", 200, 3500),
        ("공모가 산정 요약표", 300, 5000),
        ("공모가격 산정", 300, 4000),
        ("비교기업으로 선정", 900, 400),
        ("비교회사로 선정", 900, 400),
        ("비교회사 PER", 500, 2500),
        ("희망공모가액", 300, 1500),
        ("적용산식", 200, 2500),
    ]
    spans = []
    for kw, before, after in anchors:
        for m in re.finditer(re.escape(kw), text):
            spans.append((max(0, m.start() - before), min(len(text), m.start() + after)))
    if not spans:
        return text[:max_chars]
    spans.sort()
    merged = [list(spans[0])]
    for s, e in spans[1:]:
        if s <= merged[-1][1] + 200:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out, total = [], 0
    for s, e in merged:
        chunk = text[s:e]
        if total + len(chunk) > max_chars:
            chunk = chunk[:max_chars - total]
        out.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            break
    return "\n\n...(중략)...\n\n".join(out)


EXTRACTION_PROMPT = """당신은 한국 증권신고서(IPO)에서 공모 정보를 추출하는 애널리스트입니다.
아래 [원문 발췌]만 근거로, 다음 JSON 스키마에 맞춰 값을 채우세요.

규칙:
- 원문에 있는 값만 사용하고, 없으면 "—" 로 표기하세요. 절대 지어내지 마세요.
- 숫자는 원문 표기(콤마·단위 포함)를 그대로 쓰세요. 예: "27,600,000,000원", "26.76배".
- 오직 JSON만 출력하세요. 설명·군더더기 금지.

스키마:
{{
  "공모개요": {{"증권의 종류":"", "증권수량":"", "액면가액":"", "모집가액":"", "모집총액":"", "모집방법":"", "대표주관회사":"", "청약기일":"", "납입기일":"", "상장예정시장":""}},
  "공모가격": {{"주당 희망공모가액":"", "확정공모가액 결정방법":""}},
  "밸류에이션": {{"평가방법":"", "평가모형":"", "적용산식":"", "적용근거":[{{"구분":"", "내용":"", "수치":""}}], "주당 평가가액":"", "할인율":"", "공모가 산정결과":""}},
  "비교기업": [],
  "비교기업 평균 PER":""
}}

회사명: {company}

[원문 발췌]
{text}
"""


def extract_offering_with_ai(anthropic_key: str, model: str, sliced_text: str, company: str) -> dict:
    """잘라낸 원문을 Anthropic AI에 보내 구조화된 공모 정보(dict)를 받는다."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 터미널에서 'python -m pip install anthropic' 실행 후 다시 시도하세요.")
    client = anthropic.Anthropic(api_key=anthropic_key)
    prompt = EXTRACTION_PROMPT.format(company=company, text=sliced_text)
    try:
        msg = client.messages.create(
            model=model, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    raw = "".join(getattr(b, "text", "") for b in msg.content)
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j < 0:
        raise DartError("AI 응답에서 데이터를 읽지 못했습니다.")
    try:
        return json.loads(raw[i:j + 1])
    except Exception:
        raise DartError("AI 응답(JSON) 해석에 실패했습니다.")


def _kv_table(d: dict):
    """{'항목':'값'} 형태의 dict 를 2열 표로 출력."""
    rows = [(k, v if (v not in (None, "", [])) else "—") for k, v in d.items()]
    df = pd.DataFrame(rows, columns=["항목", "내용"]).set_index("항목")
    show_fs_table(df.rename_axis("항목"))


def render_offering(data: dict, company: str):
    """AI가 추출한 공모 정보를 보기 좋은 표들로 출력."""
    st.markdown(f"### {company} · 공모 상세")

    if isinstance(data.get("공모개요"), dict):
        st.markdown("#### 1. 공모개요")
        _kv_table(data["공모개요"])

    if isinstance(data.get("공모가격"), dict):
        st.markdown("#### 2. 공모가격")
        _kv_table(data["공모가격"])

    val = data.get("밸류에이션")
    if isinstance(val, dict):
        st.markdown("#### 3. 밸류에이션 (공모가 산정)")
        top = {k: val.get(k, "—") for k in ["평가방법", "평가모형", "적용산식",
                                            "주당 평가가액", "할인율", "공모가 산정결과"]}
        _kv_table(top)
        basis = val.get("적용근거")
        if isinstance(basis, list) and basis:
            st.markdown("**적용근거**")
            bdf = pd.DataFrame(basis)
            st.markdown(f'<div style="overflow-x:auto">{bdf.to_html(index=False, classes="fs-table", border=0)}</div>',
                        unsafe_allow_html=True)

    peers = data.get("비교기업")
    if peers:
        st.markdown("#### 4. 비교기업 (Peer Group)")
        if isinstance(peers, list):
            st.markdown("- " + "\n- ".join(str(p) for p in peers))
        else:
            st.write(peers)
        if data.get("비교기업 평균 PER") not in (None, "", "—"):
            st.caption(f"비교기업 평균 PER: {data['비교기업 평균 PER']}")

    with st.expander("원본 데이터(JSON) 보기"):
        st.json(data)


# ------------------------------------------------------------------
# 탭 1) 상장사 실적 비교
# ------------------------------------------------------------------
def tab_financials(corp_df):
    st.header("📊 상장사 실적 (전체 재무제표)")
    st.caption("재무상태표·손익계산서 등 모든 계정을 조회합니다. 회사를 한 곳만 넣으면 당기·전기·전전기 추세를, "
               "여러 곳을 넣으면 계정별로 나란히 비교합니다. (출처: 단일회사 전체 재무제표 API)")

    c1, c2, c3 = st.columns([3, 1, 1])
    names = c1.text_input("회사명 (쉼표로 여러 개)", "삼성전자")
    year = c2.number_input("사업연도", min_value=2015, max_value=dt.date.today().year,
                           value=dt.date.today().year - 1)
    rpt = c3.selectbox("보고서", list(REPORT_CODES.keys()))

    c4, c5 = st.columns(2)
    fs = c4.radio("재무제표 기준", ["연결(CFS)", "별도(OFS)"], horizontal=True)
    unit = c5.radio("단위", ["억원", "백만원"], horizontal=True)
    fs_div = "CFS" if fs.startswith("연결") else "OFS"
    divisor = 1e8 if unit == "억원" else 1e6

    if not st.button("조회", type="primary"):
        return

    # 입력한 회사명들을 corp_code 로 변환
    resolved, missing = [], []
    for n in [x.strip() for x in names.split(",") if x.strip()]:
        row = resolve_corp(n, corp_df)
        if row is None:
            missing.append(n)
        else:
            resolved.append((row["corp_name"], row["corp_code"]))
    if missing:
        st.warning("찾지 못한 회사: " + ", ".join(missing))
    if not resolved:
        return

    # 회사별로 '전체 재무제표'를 받아 하나로 합침
    frames = []
    for cname, ccode in resolved:
        try:
            rows = fetch_full_fs(api_key, ccode, int(year), REPORT_CODES[rpt], fs_div)
        except DartError as e:
            st.error(f"{cname}: {e}")
            continue
        if not rows:
            st.info(f"{cname}: 해당 조건의 데이터가 없습니다. (금융업이거나 연도/보고서 종류를 바꿔보세요)")
            continue
        d = pd.DataFrame(rows)
        d["회사"] = cname
        frames.append(d)
    if not frames:
        return
    alldf = pd.concat(frames, ignore_index=True)

    # 금액(당기/전기/전전기)을 선택한 단위로 변환
    def conv(x):
        v = to_num(x)
        return round(v / divisor) if v is not None else None
    alldf["당기"] = alldf["thstrm_amount"].map(conv)
    if "frmtrm_amount" in alldf.columns:
        alldf["전기"] = alldf["frmtrm_amount"].map(conv)
    if "bfefrmtrm_amount" in alldf.columns:
        alldf["전전기"] = alldf["bfefrmtrm_amount"].map(conv)
    alldf["ord_n"] = pd.to_numeric(alldf.get("ord"), errors="coerce")

    # 재무제표 종류 순서 (있는 것만 표시)
    SJ_ORDER = [("BS", "재무상태표"), ("IS", "손익계산서"), ("CIS", "포괄손익계산서"),
                ("CF", "현금흐름표"), ("SCE", "자본변동표")]
    known = {k for k, _ in SJ_ORDER}
    present = [(k, label) for k, label in SJ_ORDER if (alldf["sj_div"] == k).any()]
    present += [(k, k) for k in alldf["sj_div"].dropna().unique() if k not in known]

    single = len(resolved) == 1
    st.subheader(f"{int(year)}년 · {rpt} · {fs}  (단위: {unit})")

    for k, label in present:
        part = alldf[alldf["sj_div"] == k]
        st.markdown(f"#### {label}")
        if single:
            # 한 회사: 당기·전기·전전기 추세를 함께 표시
            cols = ["account_nm", "당기"] + [c for c in ["전기", "전전기"] if c in part.columns]
            show = (part.sort_values("ord_n")[cols]
                        .rename(columns={"account_nm": "계정"})
                        .set_index("계정"))
            # 열 이름에 단위를 붙임 (예: 당기(억원))
            show = show.rename(columns={c: f"{c}({unit})" for c in show.columns})
            show_fs_table(show, dl_stem=f"재무_{label}_{int(year)}", dl_key=f"fin_dl_{k}")
        else:
            # 여러 회사: 계정을 행, 회사를 열로 비교 (당기 기준)
            order = part.groupby("account_nm")["ord_n"].min().sort_values()
            piv = part.pivot_table(index="account_nm", columns="회사",
                                   values="당기", aggfunc="first")
            piv = piv.reindex(order.index)
            piv.index.name = "계정"
            # 열 이름(회사명)에 단위를 붙임 (예: 삼성전자(억원))
            piv.columns = [f"{c}({unit})" for c in piv.columns]
            show_fs_table(piv, dl_stem=f"재무비교_{label}_{int(year)}", dl_key=f"fin_cmp_dl_{k}")


# ------------------------------------------------------------------
# 탭 2) 최근 상장/공모 현황 (증권신고서 트래커)
# ------------------------------------------------------------------
# 증권신고서 유형별 '주요정보'(구조화) API — 무료. 보고서명으로 알맞은 걸 고른다.
DS006_ENDPOINTS = [
    ("지분증권", "estkRs.json"),
    ("채무증권", "bdRs.json"),
    ("증권예탁증권", "stkdpRs.json"),
    ("합병", "mgRs.json"),
    ("분할", "dvRs.json"),
]


def _ds006_for(report_nm: str):
    """보고서명에 따라 알맞은 증권신고서 주요정보 API를 고른다. 없으면 (None, None)."""
    for key, ep in DS006_ENDPOINTS:
        if key in report_nm:
            return key, ep
    if "교환" in report_nm or "이전" in report_nm:
        return "주식의포괄적교환·이전", "extrRs.json"
    return None, None


def render_ipo_detail(cname, ccode, report_nm, bgn, end):
    """증권신고서 주요정보(구조화 API)를 표로 바로 보여준다. (무료, AI 불필요)"""
    label, ep = _ds006_for(report_nm)
    st.markdown(f"**{cname}**  ·  {report_nm}")
    if ep is None:
        st.info("이 유형은 구조화 API가 없습니다. 아래 AI 분석 또는 표의 원문 링크를 이용하세요.")
        return
    try:
        rows = dart_get(ep, {"corp_code": ccode, "bgn_de": bgn, "end_de": end})
    except DartError as e:
        st.caption(f"조회 실패: {e}")
        return
    if not rows:
        st.info("구조화된 증권신고서 주요정보가 없습니다. (아래 AI 분석을 이용해 보세요)")
        return
    d = pd.DataFrame(rows)
    drop = [c for c in ["rcept_no", "corp_cls", "corp_code"] if c in d.columns]
    d = d.drop(columns=drop)
    st.dataframe(d.T if len(d) == 1 else d, width="stretch")


def tab_ipo(corp_df):
    st.header("🆕 최근 상장/공모 현황")
    st.caption("회사명을 비우면 전체 공모 목록이, 회사명을 넣으면 그 회사만 나옵니다. "
               "목록에서 회사를 고르면 공모 상세(발행 내용)가 표로 바로 뜹니다. "
               "(출처: 공시검색 + 증권신고서 주요정보 API)")

    cc1, cc2 = st.columns(2)
    name = cc1.text_input("회사명 (선택 — 비우면 전체)", "", key="ipo_name")
    kw = cc2.text_input("보고서명 필터", "증권신고서", key="ipo_kw")
    c1, c2 = st.columns(2)
    today = dt.date.today()
    bgn = c1.date_input("시작일", today - dt.timedelta(days=90), key="ipo_b")
    end = c2.date_input("종료일", today, key="ipo_e")

    if st.button("조회", type="primary", key="ipo_search_btn"):
        nm = name.strip()
        bs, es = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        # 이전 선택/결과 초기화
        for k in ("ipo_detail", "ipo_ai_result", "ipo_ai_srclen"):
            st.session_state.pop(k, None)
        base = {"bgn_de": bs, "end_de": es, "pblntf_ty": "C"}
        if nm:
            row = resolve_corp(nm, corp_df)
            if row is None:
                st.warning("회사를 찾지 못했습니다. 이름을 정확히 입력해 보세요.")
                st.session_state.pop("ipo_state", None)
                return
            base["corp_code"] = row["corp_code"]
        try:
            with st.spinner("공시를 불러오는 중... (기간이 길수록 시간이 걸립니다)"):
                rows, total_count, capped = dart_list_all(base)
        except DartError as e:
            st.error(str(e))
            return
        df = pd.DataFrame(rows)
        if kw.strip() and not df.empty:
            df = df[df["report_nm"].str.contains(kw.strip(), na=False, regex=False)]
        st.session_state["ipo_state"] = {
            "df": df.reset_index(drop=True), "total": total_count,
            "capped": capped, "bgn": bs, "end": es,
        }

    state = st.session_state.get("ipo_state")
    if not state:
        return
    df = state["df"]
    if df.empty:
        st.info("조건에 맞는 공시가 없습니다. 회사명/기간/필터를 바꿔보세요.")
        return

    dd = df.copy()
    dd["원문"] = DART_VIEWER + dd["rcept_no"]
    show = dd.rename(columns={"rcept_dt": "접수일", "corp_name": "회사",
                              "report_nm": "보고서명", "flr_nm": "제출인"})
    cols = [c for c in ["접수일", "회사", "보고서명", "제출인", "원문"] if c in show.columns]
    st.caption(
        f"필터 통과 {len(df):,}건 표시"
        + ("  ⚠️ 기간이 너무 길어 일부가 생략됐습니다. 기간을 좁혀 다시 조회하세요." if state["capped"] else "")
    )
    show_table(show[cols], f"공모목록_{dt.date.today():%Y%m%d}", "ipo_list_dl", link_cols=("원문",))

    # ---------------- 목록에서 회사 골라 공모 상세 보기 ----------------
    st.divider()
    st.subheader("📄 공모 상세 (발행 내용)")
    labels = {}
    for _, r in df.iterrows():
        labels[f"{r['corp_name']}  |  {r['report_nm']}  |  {r['rcept_dt']}"] = (
            r["corp_name"], r["corp_code"], r["report_nm"], r["rcept_no"])
    pick = st.selectbox("회사(공시) 선택", list(labels.keys()), key="ipo_pick")
    if st.button("이 회사 공모 상세 보기", type="primary", key="ipo_detail_btn"):
        st.session_state["ipo_detail"] = labels[pick]
        st.session_state.pop("ipo_ai_result", None)

    if "ipo_detail" not in st.session_state:
        return
    cname, ccode, rnm, rcept = st.session_state["ipo_detail"]

    # (1) 무료: 구조화된 증권신고서 주요정보
    render_ipo_detail(cname, ccode, rnm, state["bgn"], state["end"])

    # (2) 선택: AI로 밸류에이션(Peer/PER/할인율)까지 심층 분석
    st.markdown("##### 밸류에이션 심층 분석 (AI · 선택)")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면 Peer Group·PER·할인율·공모가 산정근거까지 자동으로 뽑아줍니다.")
        return
    if st.button("AI로 밸류에이션 분석", key="ipo_ai_btn"):
        try:
            with st.spinner("원문을 가져와 필요한 부분만 추려 AI가 분석하는 중... (10~30초)"):
                full = fetch_dart_document(api_key, rcept)
                sliced = slice_offering_sections(full)
                data = extract_offering_with_ai(anthropic_key, ai_model, sliced, cname)
            st.session_state["ipo_ai_result"] = (cname, data)
            st.session_state["ipo_ai_srclen"] = (len(full), len(sliced))
        except DartError as e:
            st.error(str(e))
            return

    if "ipo_ai_result" in st.session_state:
        nm2, data = st.session_state["ipo_ai_result"]
        render_offering(data, nm2)
        fl, sl = st.session_state.get("ipo_ai_srclen", (0, 0))
        if fl:
            st.caption(f"원문 {fl:,}자 중 {sl:,}자({sl/fl*100:.1f}%)만 AI에 전송해 비용을 절감했습니다. "
                       "값은 반드시 원문(위 표의 링크)과 대조해 확인하세요.")


# ------------------------------------------------------------------
# (공용) 회사 상세 표 — 기타공시 탭에서 사용
# ------------------------------------------------------------------
def _render_company_detail(cname, ccode, bgn, end, endpoints):
    """한 회사의 주요사항보고서 상세 항목을 표로 출력한다."""
    st.write(f"**{cname}**  ·  corp_code `{ccode}`")
    any_shown = False
    for label, ep in endpoints.items():
        st.markdown(f"#### {label}")
        try:
            rows = dart_get(ep, {"corp_code": ccode, "bgn_de": bgn, "end_de": end})
        except DartError as e:
            st.caption(f"조회 실패: {e}")
            continue
        if rows:
            # 항목(세로)·값(가로) 형태로 전치해 읽기 쉽게
            d = pd.DataFrame(rows)
            drop = [c for c in ["rcept_no", "corp_cls", "corp_code"] if c in d.columns]
            d = d.drop(columns=drop)
            st.dataframe(d.T, width="stretch")
            _download_buttons(d, f"{cname}_{label}", f"cd_{ccode}_{label}")
            any_shown = True
        else:
            st.caption("해당 기간 내역 없음")
    if not any_shown:
        st.info("이 회사는 해당 기간에 관련 발행/공시 내역이 없습니다.")


def _company_event_tab(corp_df, title, endpoints, key_prefix, search_keywords):
    """
    두 가지 방식으로 동작한다.
      · 회사명을 비우면  → 전체 회사의 최근 관련 공시 '목록'을 보여주고,
                           목록에서 회사를 골라 '상세'를 바로 볼 수 있다.
      · 회사명을 입력하면 → 그 회사의 상세 항목을 바로 보여준다.
    """
    name = st.text_input("회사명 (비우면 전체 회사 최근 내역)", "", key=f"{key_prefix}_name")
    c1, c2 = st.columns(2)
    bgn = c1.date_input("시작일", dt.date.today() - dt.timedelta(days=90), key=f"{key_prefix}_b")
    end = c2.date_input("종료일", dt.date.today(), key=f"{key_prefix}_e")

    if st.button("조회", type="primary", key=f"{key_prefix}_btn"):
        nm = name.strip()
        bs, es = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        st.session_state.pop(f"{key_prefix}_detail", None)   # 이전 상세 선택 초기화
        if nm:
            row = resolve_corp(nm, corp_df)
            if row is None:
                st.warning("회사를 찾지 못했습니다. 이름을 정확히 입력해 보세요.")
                st.session_state.pop(f"{key_prefix}_state", None)
                return
            st.session_state[f"{key_prefix}_state"] = {
                "mode": "company", "cname": row["corp_name"], "ccode": row["corp_code"],
                "bgn": bs, "end": es,
            }
        else:
            try:
                with st.spinner("전체 회사 공시를 불러오는 중... (기간이 길수록 시간이 걸립니다)"):
                    rows, total, capped = dart_list_all({
                        "bgn_de": bs, "end_de": es, "pblntf_ty": "B",   # B = 주요사항보고
                    })
            except DartError as e:
                st.error(str(e))
                return
            df = pd.DataFrame(rows)
            if not df.empty:
                mask = pd.Series(False, index=df.index)
                for kwd in search_keywords:
                    mask = mask | df["report_nm"].str.contains(kwd, na=False, regex=False)
                df = df[mask].reset_index(drop=True)
            st.session_state[f"{key_prefix}_state"] = {
                "mode": "list", "df": df, "total": total, "capped": capped,
                "bgn": bs, "end": es,
            }

    state = st.session_state.get(f"{key_prefix}_state")
    if not state:
        return

    # ---------- 특정 회사 모드 ----------
    if state["mode"] == "company":
        _render_company_detail(state["cname"], state["ccode"], state["bgn"], state["end"], endpoints)
        return

    # ---------- 전체 목록 모드 ----------
    df = state["df"]
    if df.empty:
        st.info("해당 기간에 관련 공시가 없습니다. 기간을 넓혀보세요.")
        return

    dd = df.copy()
    dd["원문"] = DART_VIEWER + dd["rcept_no"]
    show = dd.rename(columns={"rcept_dt": "접수일", "corp_name": "회사",
                              "report_nm": "보고서명", "flr_nm": "제출인"})
    scols = [c for c in ["접수일", "회사", "보고서명", "제출인", "원문"] if c in show.columns]
    st.caption(
        f"전체 회사 기준 관련 공시 {len(df):,}건"
        + ("  ⚠️ 기간이 너무 길어 일부가 생략됐습니다. 기간을 좁혀 조회하세요." if state["capped"] else "")
    )
    show_table(show[scols], f"{title}_{dt.date.today():%Y%m%d}", f"{key_prefix}_list_dl", link_cols=("원문",))

    # ---------- 목록에서 회사 선택 → 상세 바로 보기 ----------
    st.divider()
    st.subheader("📄 목록에서 회사 골라 상세 보기")
    labels = {}
    for _, r in df.iterrows():
        labels[f"{r['corp_name']}  |  {r['report_nm']}  |  {r['rcept_dt']}"] = (
            r["corp_name"], r["corp_code"])
    pick = st.selectbox("회사(공시) 선택", list(labels.keys()), key=f"{key_prefix}_pick")
    if st.button("상세 보기", type="primary", key=f"{key_prefix}_detail_btn"):
        cname, ccode = labels[pick]
        st.session_state[f"{key_prefix}_detail"] = (cname, ccode)

    if f"{key_prefix}_detail" in st.session_state:
        cname, ccode = st.session_state[f"{key_prefix}_detail"]
        _render_company_detail(cname, ccode, state["bgn"], state["end"], endpoints)


# ------------------------------------------------------------------
# 탭 3) 발행내역 (유형 선택 → 전체 회사 상세내역 표)
# ------------------------------------------------------------------
# 발행 유형별 상세 필드 스펙 : (표시명, [후보 키], 형식)
#   형식 eok=원→억 / won=원(숫자) / int=주식수 / pct=% / text=문자
ISSUE_SPECS = {
    "유상증자": {
        "ep": "piicDecsn.json", "kw": "유상증자결정",
        "cols": [
            ("증자방식", ["pici_mth", "ic_mthn"], "text"),
            ("신주수(보통주)", ["nstk_knd_ostk", "nstk_ostk_cnt"], "int"),
            ("예정발행가(원)", ["nstk_plnprc"], "won"),
            ("확정발행가(원)", ["nstk_isar_prc"], "won"),
            ("상장예정일", ["nstk_lstprd"], "text"),
            ("조달총액(억)", ["__fdpp__"], "eok"),
        ],
    },
    "CB (전환사채)": {
        "ep": "cvbdIsDecsn.json", "kw": "전환사채",
        "cols": [
            ("사채총액(억)", ["bd_fta"], "eok"),
            ("표면이자율(%)", ["bd_intr_ex"], "pct"),
            ("만기이자율(%)", ["bd_intr_sf"], "pct"),
            ("전환가액(원)", ["cv_prc", "cvprc"], "won"),
            ("전환청구 시작", ["cvrqpd_bgd"], "text"),
            ("전환청구 종료", ["cvrqpd_edd"], "text"),
            ("사채만기일", ["bd_mtd"], "text"),
            ("리픽싱 최저가(원)", ["act_mktprcfl_cvprc_lwtrsprc"], "won"),
            ("희석비율(%)", ["cvisstk_tisstk_vs"], "pct"),
        ],
    },
    "BW (신주인수권부사채)": {
        "ep": "bdwtIsDecsn.json", "kw": "신주인수권부사채",
        "cols": [
            ("사채총액(억)", ["bd_fta"], "eok"),
            ("표면이자율(%)", ["bd_intr_ex"], "pct"),
            ("만기이자율(%)", ["bd_intr_sf"], "pct"),
            ("행사가액(원)", ["ex_prc", "exprc"], "won"),
            ("행사 시작", ["expd_bgd"], "text"),
            ("행사 종료", ["expd_edd"], "text"),
            ("사채만기일", ["bd_mtd"], "text"),
            ("희석비율(%)", ["nstk_isstk_tisstk_vs", "exstk_tisstk_vs"], "pct"),
        ],
    },
}

FDPP_KEYS = ["fdpp_fclt", "fdpp_bsninh", "fdpp_op", "fdpp_dtrp", "fdpp_ocsa", "fdpp_etc"]


def _issue_value(row, keys, fmt):
    """한 행에서 지정 필드를 뽑아 형식에 맞게 변환."""
    if keys == ["__fdpp__"]:                       # 자금조달 목적 합계
        tot = sum((_mznum(row.get(k)) or 0) for k in FDPP_KEYS)
        return round(tot / 1e8) if tot else None
    raw = None
    for k in keys:
        if k in row and row[k] not in (None, ""):
            raw = row[k]
            break
    if raw is None:
        return None
    if fmt == "eok":
        v = _mznum(raw)
        return round(v / 1e8) if v is not None else None
    if fmt in ("won", "int", "pct"):
        return _mznum(raw)
    return str(raw)                                # text/date


def _build_issue_df(type_label, codes, code2name, ep, bgn, es):
    """회사코드들에 대해 발행결정 상세를 모아 한 표(DataFrame)로 만든다."""
    cols = ISSUE_SPECS[type_label]["cols"]
    recs = []
    for code in codes:
        try:
            drows = dart_get(ep, {"corp_code": code, "bgn_de": bgn, "end_de": es})
        except DartError:
            continue
        kind = "유상증자" if "유상증자" in type_label else ("CB" if "CB" in type_label else "BW")
        for r in drows:
            rec = {"회사": r.get("corp_name") or code2name.get(code, code),
                   "접수일": (str(r.get("rcept_no", ""))[:8] or None),
                   "_corp_code": r.get("corp_code") or code,
                   "_shares": _est_total_shares(r, kind)}
            for label, keys, fmt in cols:
                rec[label] = _issue_value(r, keys, fmt)
            rcept = r.get("rcept_no")
            rec["원문"] = (DART_VIEWER + rcept) if rcept else None
            recs.append(rec)
    return pd.DataFrame(recs)


def _map_from_df(df, code_cols, px_cols):
    """DataFrame에서 {종목코드: 가격}을 만든다. 종가가 비면 다음 가격열로 대체."""
    code_col = next((c for c in code_cols if c in df.columns), None)
    if not code_col:
        return {}
    codes = df[code_col].astype(str)
    for pxc in px_cols:
        if pxc not in df.columns:
            continue
        s = pd.to_numeric(df[pxc], errors="coerce")
        if (s > 0).any():
            m = {}
            for code, px in zip(codes, s):
                if pd.notna(px) and px > 0:
                    m[str(code).zfill(6)] = float(px)
            if m:
                return m
    return {}


def _fetch_price_map():
    """현재가(원) {종목코드: 가격} 스냅샷. FinanceDataReader의 KRX 전체 시세.
       종가가 비어있으면(장 시작 전) 시가 열로 대체. 반환 (dict, 오류문구)."""
    errs = []
    try:
        import FinanceDataReader as fdr
        lst = fdr.StockListing("KRX")
        m = _map_from_df(lst, ["Code", "Symbol", "종목코드"],
                         ["Close", "종가", "ClosePrice", "현재가", "Open", "시가"])
        if m:
            return m, None
        errs.append(f"FDR 유효가격 없음: {list(lst.columns)[:10]}")
    except ImportError:
        errs.append("FDR 미설치")
    except Exception as e:
        errs.append(f"FDR {type(e).__name__}")

    return {}, " / ".join(errs) if errs else "현재가 조회 실패"


def price_map_current():
    """현재가 맵을 반환하되 '성공한 결과만' 세션에 30분 캐시한다.
       (실패를 캐시하지 않으므로, 장중 초반 실패 후 재조회하면 정상 복구)"""
    import time as _time
    cached = st.session_state.get("_pxmap")
    if cached and cached[0] and (_time.time() - cached[2] < 1800):
        return cached[0], None
    pmap, err = _fetch_price_map()
    if pmap:
        st.session_state["_pxmap"] = (pmap, None, _time.time())
    return pmap, err


def _est_total_shares(r, kind):
    """공시 자체에서 발행주식총수를 추정. CB/BW=전환(행사)주식수÷희석비율, 유상증자=증자전 총수."""
    def g(keys):
        for k in keys:
            if k in r and r[k] not in (None, ""):
                return r[k]
        return None
    if kind == "유상증자":
        return _mznum(g(["bfic_tisstk", "bfcr_tisstk"]))
    if kind == "CB":
        cnt, vs = _mznum(g(["cvisstk_cnt"])), _mznum(g(["cvisstk_tisstk_vs"]))
    else:  # BW
        cnt, vs = _mznum(g(["nstk_isstk_cnt"])), _mznum(g(["nstk_isstk_tisstk_vs", "exstk_tisstk_vs"]))
    if cnt and vs and vs > 0:
        return cnt * 100.0 / vs       # 희석비율(%)로 역산한 발행주식총수(추정)
    return None


def _px_for_tickers(tickers, max_fetch=250):
    """표에 필요한 종목만 개별 종가를 FDR DataReader로 받아 채운다(장 초반에도 동작).
       종목별 결과를 세션 캐시해 재사용. 반환 (dict{code:price}, 가져온 수, 남은 수)."""
    cache = st.session_state.setdefault("_pxcache", {})
    need = [t for t in tickers if t not in cache]
    fetched = 0
    if need:
        try:
            import FinanceDataReader as fdr
            start = (dt.date.today() - dt.timedelta(days=12)).strftime("%Y-%m-%d")
            for t in need[:max_fetch]:
                try:
                    d = fdr.DataReader(t, start)
                    s = pd.to_numeric(d["Close"], errors="coerce").dropna() if (d is not None and "Close" in d) else None
                    cache[t] = float(s.iloc[-1]) if (s is not None and len(s) and s.iloc[-1] > 0) else None
                except Exception:
                    cache[t] = None
                fetched += 1
        except ImportError:
            pass
    out = {t: cache[t] for t in tickers if cache.get(t)}
    remain = max(0, len(need) - max_fetch)
    return out, fetched, remain


def _attach_market_cap(df, corp_df, label):
    """시가총액(억) = 현재가 × 발행주식수. 현재가는 장중 전체 스냅샷(빠름) + 비면 종목별 종가(시간 무관)로 보완."""
    code_map = {str(c): str(s) for c, s in zip(corp_df["corp_code"], corp_df["stock_code"])}
    size_col = next((c for c in ["사채총액(억)", "조달총액(억)"] if c in df.columns), None)

    # 이 표에 필요한 종목코드
    tickers = set()
    row_sc = []
    for _, r in df.iterrows():
        raw_sc = code_map.get(str(r.get("_corp_code")), "")
        sc = raw_sc.zfill(6) if raw_sc and raw_sc.strip() else ""
        row_sc.append(sc)
        if sc and len(sc) == 6:
            tickers.add(sc)

    # 1) 전체 스냅샷(FDR) — 장중이면 대부분 채워짐
    pmap, perr = price_map_current()
    have = {t: pmap[t] for t in tickers if pmap and t in pmap}
    # 2) 빠진 종목만 개별 종가로 보완(장 초반 등)
    missing = [t for t in tickers if t not in have]
    note = "현재가 스냅샷" if have and not missing else ""
    remain = 0
    if missing:
        more, fetched, remain = _px_for_tickers(missing)
        have.update(more)
        note = "종목별 종가(보완)"

    caps, ratios, matched = [], [], 0
    for (_, r), sc in zip(df.iterrows(), row_sc):
        cap = None
        if sc:
            shares = r.get("_shares")
            px = have.get(sc)
            if pd.notna(shares) and shares and px:
                cap = round(shares * px / 1e8)
                matched += 1
        caps.append(cap)
        sz = r.get(size_col) if size_col else None
        ratios.append(round(sz / cap * 100, 1) if (cap and pd.notna(sz)) else None)
    cap_note = note + (f" · 상위 {len(have)}종목" if have else "")
    perr = perr or "가격 소스 미응답"

    out = df.copy()
    out["시가총액(억)"] = caps
    out["발행/시총(%)"] = ratios
    if size_col:
        cols = list(out.columns)
        for c in ["시가총액(억)", "발행/시총(%)"]:
            cols.remove(c)
        i = cols.index(size_col) + 1
        cols = cols[:i] + ["시가총액(억)", "발행/시총(%)"] + cols[i:]
        out = out[cols]

    if matched == 0:
        if not have:
            st.error("시가총액을 계산하지 못했습니다. (가격 소스 미응답 / 장 시작 전에는 실시간 가격이 비어있을 수 있음)  "
                     f"— 현재가: {perr}")
        else:
            st.warning("시가총액 매칭 결과가 없습니다. (비상장이거나 종목코드 매칭 실패)")
    else:
        msg = f"시가총액 출처: {cap_note}"
        if remain:
            msg += f" · {remain}개 종목은 가격 조회 상한으로 생략"
        st.caption(msg)
    return out


@st.cache_data(show_spinner=False)
def build_issue_all(api_key_arg, type_label, bgn, es, max_corps=800):
    """기간 내 시장 전체에서 해당 유형의 발행 상세를 모아 표로 만든다.
    CB/BW는 DB에 적재분이 있으면 DB에서 즉시 조회, 없으면(또는 유상증자) DART 실시간 스캔."""
    if "CB" in type_label or "BW" in type_label:
        kind = "CB" if "CB" in type_label else "BW"
        if db_bond_count(kind) > 0:
            return db_query_issue(type_label, bgn, es)
    spec = ISSUE_SPECS[type_label]
    all_rows = []
    for cb, ce in _date_chunks(bgn, es, 90):       # 회사 미지정 검색의 기간 제한 회피
        try:
            rows, _, _ = dart_list_all({"bgn_de": cb, "end_de": ce, "pblntf_ty": "B"})
            all_rows.extend(rows)
        except DartError:
            continue
    ldf = pd.DataFrame(all_rows)
    if ldf.empty:
        return pd.DataFrame()
    ldf = ldf[ldf["report_nm"].str.contains(spec["kw"], na=False, regex=False)]
    if "rcept_no" in ldf.columns:
        ldf = ldf.drop_duplicates("rcept_no")
    if ldf.empty:
        return pd.DataFrame()
    code2name = dict(zip(ldf["corp_code"], ldf["corp_name"]))
    codes = list(dict.fromkeys(ldf["corp_code"].tolist()))[:max_corps]
    return _build_issue_df(type_label, codes, code2name, spec["ep"], bgn, es)


def tab_issuance(corp_df):
    st.header("💰 발행내역 (유상증자 · CB · BW)")
    st.caption("발행 유형을 고르고 기간을 정하면, 그 기간에 발행된 해당 유형의 상세 내역(금액·금리·만기 등)이 "
               "전체 회사에 대해 표로 나옵니다. 특정 회사만 보려면 회사명을 입력하세요.  "
               "※ CB·BW는 백필해 둔 DB에서 즉시 조회됩니다. 유상증자는 DB에 없어 실시간 조회라 다소 걸립니다.")

    type_label = st.radio("발행 유형", list(ISSUE_SPECS.keys()), horizontal=True)
    name = st.text_input("회사명 (비우면 전체 회사)", "", key="iss_name")
    c1, c2 = st.columns(2)
    bgn = c1.date_input("시작일", dt.date.today() - dt.timedelta(days=90), key="iss_b")
    end = c2.date_input("종료일", dt.date.today(), key="iss_e")
    show_cap = st.checkbox("시가총액 추가 (현재 기준 · FinanceDataReader/pykrx 사용)", key="iss_cap")

    if st.button("조회", type="primary", key="iss_btn"):
        bs, es = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        nm = name.strip()
        try:
            with st.spinner("발행내역을 수집·정리하는 중... (전체 조회는 기간에 따라 시간이 걸립니다)"):
                if nm:
                    row = resolve_corp(nm, corp_df)
                    if row is None:
                        st.warning("회사를 찾지 못했습니다. 이름을 정확히 입력해 보세요.")
                        st.session_state.pop("iss_df", None)
                        return
                    spec = ISSUE_SPECS[type_label]
                    df = _build_issue_df(type_label, [row["corp_code"]],
                                         {row["corp_code"]: row["corp_name"]}, spec["ep"], bs, es)
                else:
                    df = build_issue_all(api_key, type_label, bs, es)
        except DartError as e:
            st.error(str(e))
            return
        st.session_state["iss_df"] = df
        st.session_state["iss_label"] = type_label

    if "iss_df" not in st.session_state:
        return
    df = st.session_state["iss_df"]
    label = st.session_state["iss_label"]
    if df is None or df.empty:
        st.info("해당 조건의 발행내역이 없습니다. 유형·기간·회사명을 바꿔보세요.")
        return

    if "접수일" in df.columns:
        df = df.sort_values("접수일", ascending=False)
    if show_cap:
        with st.spinner("KRX에서 발행일 기준 시가총액을 가져오는 중..."):
            df = _attach_market_cap(df, corp_df, label)
    # 내부용 숨김 열 제거
    df = df.drop(columns=[c for c in ["_corp_code", "_shares"] if c in df.columns])
    st.caption(f"{label} · 총 {len(df):,}건  (열 제목을 클릭하면 정렬됩니다)"
               + ("  · 시가총액은 KRX(pykrx) 기준, 비상장/매칭 실패는 빈칸" if show_cap else ""))
    st.dataframe(df, width="stretch", hide_index=True,
                 column_config={"원문": st.column_config.LinkColumn("원문")})


# ------------------------------------------------------------------
# 탭 4) 기타공시 (자기주식 취득/처분)
# ------------------------------------------------------------------
TREASURY_ENDPOINTS = {
    "자기주식 취득 결정": "tsstkAqDecsn.json",
    "자기주식 처분 결정": "tsstkDpDecsn.json",
}
TREASURY_KEYWORDS = ["자기주식"]


def tab_other(corp_df):
    st.header("🔁 기타공시 (자기주식 등)")
    st.caption("회사명을 비우면 전체 회사의 최근 자기주식 관련 공시가 목록으로, 목록에서 고르거나 "
               "회사명을 입력하면 그 회사의 상세 내역이 표로 나옵니다.")
    _company_event_tab(corp_df, "기타공시", TREASURY_ENDPOINTS, "oth", TREASURY_KEYWORDS)


# ------------------------------------------------------------------
# 탭 5) 밸류에이션 (공모가 산정근거) — 원문 링크 제공
# ------------------------------------------------------------------
def tab_valuation(corp_df):
    st.header("🧮 밸류에이션 (공모가 산정근거)")
    st.caption("회사명을 넣으면 증권신고서(IPO) 목록이 나오고, 하나를 골라 AI로 분석하면 "
               "공모개요·공모가격·밸류에이션(평가방법/할인율)·비교기업(Peer Group)·PER을 원문에서 추출해 표로 보여줍니다. "
               "(산정근거는 정형 API가 없어 원문을 파싱합니다. 사이드바에 Anthropic API 키가 필요합니다.)")

    name = st.text_input("회사명", "", key="val_name")
    c1, c2 = st.columns(2)
    bgn = c1.date_input("시작일", dt.date.today() - dt.timedelta(days=1095), key="val_b")
    end = c2.date_input("종료일", dt.date.today(), key="val_e")

    if st.button("증권신고서 찾기", type="primary", key="val_btn"):
        row = resolve_corp(name, corp_df)
        if row is None:
            st.warning("회사를 찾지 못했습니다.")
            st.session_state.pop("val_rows", None)
            return
        try:
            rows, _, _ = dart_list_all({
                "corp_code": row["corp_code"],
                "bgn_de": bgn.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "pblntf_ty": "C",
            })
        except DartError as e:
            st.error(str(e))
            return
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df[df["report_nm"].str.contains("증권신고서", na=False, regex=False)]
        if df.empty:
            st.info("해당 기간 증권신고서를 찾지 못했습니다.")
            st.session_state.pop("val_rows", None)
            return
        st.session_state["val_rows"] = df.to_dict("records")
        st.session_state["val_company"] = row["corp_name"]
        st.session_state.pop("val_ai", None)

    recs = st.session_state.get("val_rows")
    if not recs:
        return
    company = st.session_state.get("val_company", name)

    df = pd.DataFrame(recs)
    df["원문"] = DART_VIEWER + df["rcept_no"]
    show = df.rename(columns={"rcept_dt": "접수일", "report_nm": "보고서명", "flr_nm": "제출인"})
    cols = [c for c in ["접수일", "보고서명", "제출인", "원문"] if c in show.columns]
    show_table(show[cols], f"증권신고서_{company}", "val_dl", link_cols=("원문",))

    # ---- AI로 공모가 산정근거(밸류에이션) 추출 ----
    st.divider()
    st.subheader("📑 공모가 산정근거 추출 (AI)")
    st.caption("수치는 보통 '[발행조건확정]' 또는 가장 최근 정정본이 가장 완결돼 있습니다. 그걸 고르면 정확도가 높습니다.")
    labels = [f"{r.get('rcept_dt','')} · {r.get('report_nm','')}" for r in recs]
    pick = st.selectbox("분석할 증권신고서 선택", range(len(labels)),
                        format_func=lambda i: labels[i], key="val_pick")

    if not anthropic_key:
        st.info("사이드바에 **Anthropic API 키**를 입력하면, 선택한 증권신고서 원문에서 "
                "Peer Group·PER·할인율 등 밸류에이션을 추출합니다.")
        return

    if st.button("AI로 산정근거 분석", type="primary", key="val_ai_btn"):
        rcept = recs[pick].get("rcept_no")
        try:
            with st.spinner("증권신고서 원문을 받아 공모 관련 부분만 추려 AI로 분석 중... (약 10~30초)"):
                text = fetch_dart_document(api_key, rcept)
                sliced = slice_offering_sections(text)
                data = extract_offering_with_ai(anthropic_key, ai_model, sliced, company)
            st.session_state["val_ai"] = data
        except DartError as e:
            st.error(str(e))
            return

    if "val_ai" in st.session_state:
        render_offering(st.session_state["val_ai"], company)
        st.caption("※ AI가 원문에서 추출한 값입니다. 중요한 수치는 '원문' 링크로 반드시 대조하세요.")


# ==================================================================
#  탭 6) 메자닌 벤치마킹 (우리 CB/BW 딜 조건 vs 시장)
# ==================================================================
def _mznum(s):
    """'2.0', '0.02%', '2,600', '13,800원' 등을 숫자로. 빈값/해당없음은 None."""
    if s is None:
        return None
    t = str(s).replace(",", "").replace("%", "").replace("원", "").replace("주", "").strip()
    if t in ("", "-", "해당사항없음", "해당없음", "없음", "N/A", "nan"):
        return None
    try:
        return float(t)
    except ValueError:
        m = re.search(r"-?\d+\.?\d*", t)
        return float(m.group()) if m else None


def _parse_date(s):
    if not s:
        return None
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(s)) or re.search(r"(\d{4})(\d{2})(\d{2})", str(s))
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _parse_mezz_row(row, code2name):
    """CB/BW 발행결정 1건에서 벤치마킹용 핵심 조건을 뽑는다."""
    def g(keys):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return None

    cvprc = _mznum(g(["cv_prc", "cvprc", "ex_prc", "exprc"]))
    floor = _mznum(g(["act_mktprcfl_cvprc_lwtrsprc"]))
    refix = round(floor / cvprc * 100, 1) if (floor and cvprc) else None
    mat = _parse_date(g(["bd_mtd"]))
    base = _parse_date(g(["pymd", "bddd", "rcept_dt"]))
    years = round((mat - base).days / 365.25, 1) if (mat and base) else None
    amt = _mznum(g(["bd_fta"]))
    dil = _mznum(g(["cvisstk_tisstk_vs", "exstk_tisstk_vs", "tisstk_vs"]))
    return {
        "회사": row.get("corp_name") or code2name.get(row.get("corp_code"), row.get("corp_code")),
        "표면금리": _mznum(g(["bd_intr_ex"])),
        "YTM": _mznum(g(["bd_intr_sf"])),
        "만기(년)": years,
        "발행비율(%)": dil,
        "리픽싱하한(%)": refix,      # 리픽싱 없는 건은 None
        "규모(억)": round(amt / 1e8) if amt else None,
    }


def _date_chunks(bgn, es, max_days=90):
    """긴 기간을 max_days 이하 구간으로 쪼갠다. (회사 지정 없는 DART 검색의 기간 제한 회피)"""
    d0, d1 = _parse_date(bgn), _parse_date(es)
    if not d0 or not d1:
        return [(bgn, es)]
    out, cur = [], d0
    while cur <= d1:
        nxt = min(d1, cur + dt.timedelta(days=max_days - 1))
        out.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + dt.timedelta(days=1)
    return out


@st.cache_data(show_spinner=False)
def build_mezz_comps(api_key_arg, kind, bgn, es, max_corps=600):
    """기간 내 시장 전체의 CB(또는 BW) 발행조건을 모아 비교군 DataFrame을 만든다."""
    ep = "cvbdIsDecsn.json" if kind == "CB" else "bdwtIsDecsn.json"
    kw = "전환사채" if kind == "CB" else "신주인수권부사채"
    # 회사 지정 없는 검색은 기간 제한이 있어, 90일 이하로 쪼개서 모은다.
    all_rows = []
    for cb, ce in _date_chunks(bgn, es, 90):
        try:
            rows, _, _ = dart_list_all({"bgn_de": cb, "end_de": ce, "pblntf_ty": "B"})
            all_rows.extend(rows)
        except DartError:
            continue
    ldf = pd.DataFrame(all_rows)
    if ldf.empty:
        return pd.DataFrame()
    ldf = ldf[ldf["report_nm"].str.contains(kw, na=False, regex=False)]
    if "rcept_no" in ldf.columns:
        ldf = ldf.drop_duplicates("rcept_no")
    if ldf.empty:
        return pd.DataFrame()
    code2name = dict(zip(ldf["corp_code"], ldf["corp_name"]))
    codes = list(dict.fromkeys(ldf["corp_code"].tolist()))[:max_corps]
    recs = []
    for code in codes:
        try:
            drows = dart_get(ep, {"corp_code": code, "bgn_de": bgn, "end_de": es})
        except DartError:
            continue
        for r in drows:
            recs.append(_parse_mezz_row(r, code2name))
    return pd.DataFrame(recs)


def _pct_of(series, value):
    """분포에서 value가 하위 몇 %인지(=value보다 작은 표본 비율)."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0 or value is None:
        return None
    return round((s < value).mean() * 100)


MEZZ_METRICS = [
    # (라벨, 컬럼, 단위, 투자자에게 높을수록 유리?)
    ("표면금리", "표면금리", "%", True),
    ("만기이자율(YTM)", "YTM", "%", True),
    ("만기", "만기(년)", "년", None),
    ("발행규모", "규모(억)", "억원", None),
    ("발행비율(희석)", "발행비율(%)", "%", None),
    ("리픽싱 하한", "리픽싱하한(%)", "%", False),
]


def mezz_ai_opinion(anthropic_key, model, kind, deal, stats_text, n):
    """계산된 시장 통계 위에서 AI 심사역 의견서를 생성."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 실행 후 다시 시도하세요.")
    client = anthropic.Anthropic(api_key=anthropic_key)
    prompt = f"""당신은 한국 벤처·PE의 메자닌(전환사채/신주인수권부사채) 투자 심사역입니다.
아래는 우리가 검토 중인 {kind} 딜 조건과, 최근 시장에서 발행된 동일 유형 {n}건의 통계입니다.
투자자(우리) 관점에서, 제공된 숫자만 근거로 평가하세요. 숫자를 새로 지어내지 마세요.
(참고: 풋옵션 조건은 DART 정형 데이터에 없어 시장 통계가 없습니다. 우리 딜의 풋옵션 정보는 정성적으로만 참고하세요.)

[우리 딜 조건]
{deal}

[최근 시장 통계]
{stats_text}

다음 형식의 한국어 메모로 작성하세요:
1) 종합 판단 (한 줄: 시장 대비 투자자 유리/중립/불리)
2) 조건별 시장 대비 위치 (표면금리·YTM·만기·발행규모·발행비율·리픽싱 각각 간단히)
3) 강점 / 약점
4) 구체적 조정 제안 (예: YTM +50bp, 리픽싱 하한 70%로 강화, 풋옵션 금리 상향 등 수치로)
5) 리스크·유의사항
투자 권유가 아니라 협상 참고용임을 마지막에 한 줄로 명시하세요."""
    try:
        msg = client.messages.create(model=model, max_tokens=1500,
                                     messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    return "".join(getattr(b, "text", "") for b in msg.content)


# ==================================================================
#  탭) 밸류에이션 (메자닌) — 증발공 규정 전환가 산정 + 주가 여력 + AI 전망
# ==================================================================
def _mv_price_series(ticker, start, end):
    """일별 주가(Close·Volume) 시계열. FinanceDataReader."""
    try:
        import FinanceDataReader as fdr
    except ImportError:
        raise DartError("FinanceDataReader가 없습니다. 'python -m pip install finance-datareader' 후 재시도하세요.")
    d = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    if d is None or d.empty or "Close" not in d:
        return None
    d = d[[c for c in ["Close", "Volume"] if c in d.columns]].copy()
    if "Volume" not in d.columns:
        d["Volume"] = 1.0
    return d


def _mv_conv_price(series, base_date, cur_price):
    """증발공 규정식 예상 전환가.
    기준일 '이전'의 3개월·1개월 거래량가중평균(일별 종가×거래량 추정)과 전일 종가 중 최댓값.
    기준일이 미래면 마지막 실거래일 이후는 현재가로 가정(부사장님 지시)."""
    s = series.copy()
    last_real = s.index[-1].date()
    # 미래 기준일 → 현재가로 채움
    if base_date > last_real:
        med_vol = float(pd.to_numeric(s["Volume"], errors="coerce").tail(20).median() or 1.0)
        fut = pd.bdate_range(last_real + dt.timedelta(days=1), base_date)
        if len(fut):
            ext = pd.DataFrame({"Close": cur_price, "Volume": med_vol}, index=fut)
            s = pd.concat([s, ext])
    w_all = s[s.index.date < base_date]
    if w_all.empty:
        return None
    prev_close = float(pd.to_numeric(w_all["Close"], errors="coerce").dropna().iloc[-1])

    def wavg(days):
        w = w_all[w_all.index.date >= (base_date - dt.timedelta(days=days))]
        c = pd.to_numeric(w["Close"], errors="coerce")
        v = pd.to_numeric(w["Volume"], errors="coerce")
        vol = v.sum()
        if vol and vol > 0:
            return float((c * v).sum() / vol)
        return float(c.mean()) if len(c.dropna()) else None

    p3, p1 = wavg(90), wavg(30)
    cands = [x for x in (p3, p1, prev_close) if x is not None]
    conv = max(max(cands), prev_close) if cands else prev_close   # max · max (2단계)
    return {"3개월가중평균": p3, "1개월가중평균": p1, "전일종가": prev_close, "예상전환가": conv}


def mezz_val_ai(anthropic_key, model, ctx):
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 후 다시 시도하세요.")
    prompt = f"""당신은 메자닌(CB/BW) 투자 심사역입니다. 아래 한 상장사의 주가·전환가 정보를 바탕으로,
적정 주가와 '전환(행사) 타이밍'에 대한 의견을 제시하세요. 제공된 숫자만 근거로 하되, 일반적 밸류에이션 관점을 적용하세요.

[데이터]
{ctx}

반드시 아래 JSON 형식 '하나만' 출력하세요(코드블록·설명 없이 순수 JSON). 각 값은 한국어 서술로 2~4문장:
{{
  "peer": "피어그룹 관점(동종업계 통상 PER/PBR 대비)에서 본 현재 주가 수준 — 고평가/적정/저평가와 근거",
  "absolute": "절대가치 관점(실적·성장성 대비)에서의 적정주가 레인지(대략)와 근거",
  "timing": "전환가 대비 현재가(패리티)와 상승 여력을 감안할 때, 지금 전환이 유리한지 / 더 기다리는 게 유리한지에 대한 판단과 근거(한 줄 결론 포함)"
}}"""
    try:
        msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
            model=model, max_tokens=1300, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    raw = "".join(getattr(b, "text", "") for b in msg.content).strip()
    # 순수 JSON 파싱 (코드블록/잡텍스트가 섞여도 중괄호 구간만 추출)
    import json as _json
    txt = raw
    if "```" in txt:
        txt = txt.split("```")[1].replace("json", "", 1) if txt.count("```") >= 2 else txt
    i, j = txt.find("{"), txt.rfind("}")
    parsed = None
    if i != -1 and j != -1 and j > i:
        try:
            parsed = _json.loads(txt[i:j + 1])
        except Exception:
            parsed = None
    if not isinstance(parsed, dict):
        # 파싱 실패 시: 전체 텍스트를 '피어그룹' 칸에 넣어 최소한 보이게
        return {"peer": raw, "absolute": "", "timing": ""}
    return {
        "peer": str(parsed.get("peer", "") or ""),
        "absolute": str(parsed.get("absolute", "") or ""),
        "timing": str(parsed.get("timing", "") or ""),
    }


def tab_mezz_val(corp_df):
    st.header("💹 Ⅳ. 밸류에이션")
    st.caption("증발공 규정 기준 **예상 전환가** = max( 3개월·1개월 가중평균주가, 전일 종가 )를 산정하고, 현재가 대비 "
               "전환 패리티·상승 여력을 봅니다. 두 번째 기준일(예: 한 달 뒤)로 예상 리픽싱가도 추정해 "
               "**언제 전환·발행하는 게 유리한지** 판단합니다. (가중평균은 일별 종가×거래량 기준 추정치 · 미래 기준일은 현재가로 가정)")

    c1, c2, c3 = st.columns([2, 1, 1])
    name = c1.text_input("종목명", "", key="mv_name")
    today = dt.date.today()
    base1 = c2.date_input("기준일 ① (발행 가정)", today, key="mv_d1")
    base2 = c3.date_input("기준일 ② (미래·리픽싱)", today + dt.timedelta(days=30), key="mv_d2")

    if st.button("조회", type="primary", key="mv_btn"):
        row = resolve_corp(name, corp_df)
        sc = str(row.get("stock_code", "")).strip() if row is not None else ""
        if row is None or not sc:
            st.warning("상장 종목을 찾지 못했습니다. (비상장이거나 종목명을 확인하세요)")
            st.session_state.pop("mv", None)
            return
        ticker = sc.zfill(6)
        start = min(base1, base2) - dt.timedelta(days=170)
        end = min(max(base1, base2, today), today)         # 미래는 못 받으므로 today까지
        try:
            with st.spinner("주가를 불러오는 중..."):
                series = _mv_price_series(ticker, start, end)
        except DartError as e:
            st.error(str(e)); return
        except Exception as e:
            st.error(f"주가 조회 실패: {e} (회사 네트워크에서 FinanceDataReader가 막혔을 수 있음)"); return
        if series is None or series.empty:
            st.info("주가 데이터를 불러오지 못했습니다. (상장 여부·네트워크 확인, 장중 재시도)")
            st.session_state.pop("mv", None); return
        cur = float(pd.to_numeric(series["Close"], errors="coerce").dropna().iloc[-1])
        r1 = _mv_conv_price(series, base1, cur)
        r2 = _mv_conv_price(series, base2, cur)
        # 최근 수익률(참고/AI용)
        closes = pd.to_numeric(series["Close"], errors="coerce").dropna()
        def _ret(days):
            past = series[series.index.date <= (today - dt.timedelta(days=days))]
            if past.empty:
                return None
            p = float(pd.to_numeric(past["Close"], errors="coerce").dropna().iloc[-1])
            return round((cur / p - 1) * 100, 1) if p else None
        st.session_state["mv"] = {
            "name": row["corp_name"], "ticker": ticker, "cur": cur, "r1": r1, "r2": r2,
            "base1": str(base1), "base2": str(base2), "ret1m": _ret(30), "ret3m": _ret(90),
            "hi52": float(closes.tail(250).max()) if len(closes) else None,
            "lo52": float(closes.tail(250).min()) if len(closes) else None,
            "corp_code": row["corp_code"],
        }
        st.session_state.pop("mv_ai", None)

    mv = st.session_state.get("mv")
    if not mv:
        return

    st.subheader(f"{mv['name']} ({mv['ticker']}) · 현재가 {mv['cur']:,.0f}원")

    def _render(label, base, r):
        st.markdown(f"**기준일 {base}**")
        if not r:
            st.caption("해당 기준일 이전 주가가 부족해 산정 불가.")
            return
        conv = r["예상전환가"]
        parity = (mv["cur"] / conv * 100) if conv else None
        a, b, c, d, e = st.columns(5)
        a.metric("3개월 가중평균", f"{r['3개월가중평균']:,.0f}원" if r["3개월가중평균"] else "-")
        b.metric("1개월 가중평균", f"{r['1개월가중평균']:,.0f}원" if r["1개월가중평균"] else "-")
        c.metric("전일 종가", f"{r['전일종가']:,.0f}원" if r["전일종가"] else "-")
        d.metric("예상 전환가", f"{conv:,.0f}원" if conv else "-",
                 help="max(3개월·1개월 가중평균, 전일 종가)")
        e.metric("패리티(%)", f"{parity:.1f}%" if parity is not None else "-",
                 help="현재가 ÷ 예상 전환가 × 100. 100% 이상이면 전환 유리(In-the-money).")
        if parity is not None:
            state = "전환 유리(In-the-money)" if parity >= 100 else "전환 불리(Out-of-the-money)"
            st.caption(f"→ {state}  ·  전환가 대비 현재가 "
                       f"{'+' if mv['cur']>=conv else ''}{(mv['cur']-conv)/conv*100:.1f}%")

    st.markdown("#### 1) 예상 전환가격")
    _render("① 발행 시점 전환가", mv["base1"], mv["r1"])
    st.divider()
    st.markdown("#### 2) 리픽싱 시 예상 전환가격")
    _render("② 미래·리픽싱 시점 추정", mv["base2"], mv["r2"])

    # ---- 3) 적정 주가 (AI · 기본 표시) ----
    st.divider()
    st.markdown("#### 3) 적정 주가")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 피어그룹·절대가치 관점의 적정 주가와 전환 타이밍 의견이 자동으로 표시됩니다.")
    else:
        # 새 조회(mv_btn) 시 mv_ai 를 비워두므로, 없으면 1회 자동 생성 후 세션에 고정
        if "mv_ai" not in st.session_state:
            c1v = mv["r1"]["예상전환가"] if mv["r1"] else None
            c2v = mv["r2"]["예상전환가"] if mv["r2"] else None
            fin_txt = ""
            try:
                fin = fetch_company_financials(api_key, mv["corp_code"], today.year - 1, today.year)
                la = f"{today.year-1}년"
                d = fin.get(la, {})
                fin_txt = (f"매출 {d.get('매출액')}억, 영업이익 {d.get('영업이익')}억, "
                           f"부채총계 {d.get('부채총계')}억, 자본총계 {d.get('자본총계')}억")
            except Exception:
                fin_txt = "자료 없음"
            lines = [
                f"- 종목: {mv['name']}({mv['ticker']})",
                f"- 현재가: {mv['cur']:,.0f}원, 52주 고가 {mv['hi52']:,.0f}원 / 저가 {mv['lo52']:,.0f}원",
                f"- 최근 수익률: 1개월 {mv['ret1m']}% · 3개월 {mv['ret3m']}%",
            ]
            if c1v:
                lines.append(f"- 예상 전환가(발행 가정 {mv['base1']}): {c1v:,.0f}원")
            if c2v:
                lines.append(f"- 예상 전환가(미래 {mv['base2']}, 현재가 가정): {c2v:,.0f}원")
            lines.append(f"- 직전연도 재무: {fin_txt}")
            ctx = "\n".join(lines)
            try:
                with st.spinner("AI가 적정 주가·전환 타이밍을 정리하는 중..."):
                    st.session_state["mv_ai"] = mezz_val_ai(anthropic_key, ai_model, ctx)
            except DartError as e:
                st.error(str(e))
                st.session_state["mv_ai"] = {"peer": "", "absolute": "", "timing": ""}

        ai = st.session_state.get("mv_ai") or {}
        st.markdown("**3-1) 피어그룹**")
        st.markdown(ai.get("peer") or "_(자료 부족으로 산정 불가)_")
        st.markdown("**3-2) 절대가치**")
        st.markdown(ai.get("absolute") or "_(자료 부족으로 산정 불가)_")

    # ---- 결론 (AI · 기본 표시) ----
    st.divider()
    st.markdown("#### 결론")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면 전환 타이밍 의견이 자동으로 표시됩니다.")
    else:
        ai = st.session_state.get("mv_ai") or {}
        st.markdown(ai.get("timing") or "_(자료 부족으로 산정 불가)_")
        st.caption("※ 실시간 시세·시장상황에 따라 달라지는 참고용 추정입니다. 투자 권유가 아닙니다.")


def tab_mezzanine(corp_df):
    st.header("🧬 메자닌 벤치마킹 (우리 딜 vs 시장)")
    st.caption("우리가 검토 중인 CB/BW 조건을 입력하면, 최근 시장에서 발행된 동일 유형과 비교해 "
               "우리 딜이 시장 대비 어디에 위치하는지 보여줍니다. (출처: 주요사항보고서 발행결정 API)")

    kind = st.radio("상품 유형", ["CB (전환사채)", "BW (신주인수권부사채)"], horizontal=True)
    kind_code = "CB" if kind.startswith("CB") else "BW"

    st.markdown("#### 1) 우리 딜 조건 입력")
    c1, c2, c3 = st.columns(3)
    d_coupon = c1.number_input("표면금리 (%)", value=1.0, step=0.1, format="%.2f")
    d_ytm = c2.number_input("만기이자율 YTM (%)", value=5.0, step=0.1, format="%.2f")
    d_mat = c3.number_input("만기 (년)", value=3.0, step=0.5, format="%.1f")

    c4, c5, c6 = st.columns(3)
    d_size = c4.number_input("발행규모 (억원)", value=100.0, step=10.0, format="%.0f")
    d_dil = c5.number_input("발행비율/희석 (%)", value=10.0, step=1.0, format="%.1f",
                            help="전환·행사 시 발행될 주식 ÷ 발행주식총수 (%)")
    d_refix_yn = c6.selectbox("리픽싱 여부", ["있음", "없음"])

    c7, c8, c9 = st.columns(3)
    d_refix = None
    if d_refix_yn == "있음":
        d_refix = c7.number_input("리픽싱 하한 (전환가 대비 %)", value=70.0, step=1.0, format="%.0f",
                                  help="예: 최저 조정가액이 최초 전환가의 70%면 70 입력")
    d_put_yn = c8.selectbox("풋옵션 여부", ["있음", "없음"])
    d_put_rate = None
    if d_put_yn == "있음":
        d_put_rate = c9.number_input("풋옵션 금리 (YTP %)", value=5.0, step=0.1, format="%.2f",
                                     help="조기상환청구권 행사 시 보장수익률")

    st.markdown("#### 2) 비교할 시장 범위")
    cc1, cc2 = st.columns(2)
    today = dt.date.today()
    bgn = cc1.date_input("시작일", today - dt.timedelta(days=180), key="mz_b")
    end = cc2.date_input("종료일", today, key="mz_e")

    if st.button("벤치마킹 실행", type="primary", key="mz_btn"):
        bs, es = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        try:
            with st.spinner("시장 전체의 발행조건을 수집·집계하는 중... (기간에 따라 1분 이상 걸릴 수 있어요)"):
                comps = build_mezz_comps(api_key, kind_code, bs, es)
        except DartError as e:
            st.error(str(e))
            return
        st.session_state["mz_result"] = {
            "kind": kind_code, "comps": comps,
            "deal": {"표면금리": d_coupon, "YTM": d_ytm, "만기(년)": d_mat,
                     "규모(억)": d_size, "발행비율(%)": d_dil,
                     "리픽싱여부": d_refix_yn, "리픽싱하한(%)": d_refix,
                     "풋옵션여부": d_put_yn, "풋옵션금리": d_put_rate},
        }
        st.session_state.pop("mz_ai", None)

    res = st.session_state.get("mz_result")
    if not res:
        return
    comps, deal = res["comps"], res["deal"]
    if comps is None or comps.empty:
        st.info("해당 기간 시장 발행 건을 찾지 못했습니다. 기간을 넓히거나 유형(CB/BW)을 바꿔보세요.")
        return

    n = len(comps)
    st.divider()
    st.subheader(f"3) 벤치마킹 결과  (비교표본 {n}건, {res['kind']})")

    # --- 비교표 ---
    table_rows = []
    for label, col, unit, hib in MEZZ_METRICS:
        s = pd.to_numeric(comps[col], errors="coerce").dropna()
        if s.empty:
            continue
        ours = deal.get(col)
        pct = _pct_of(s, ours)
        if pct is None or hib is None:
            interp = "—"
        elif hib:
            interp = "투자자 유리" if pct >= 60 else ("투자자 불리" if pct <= 40 else "시장 평균")
        else:  # 낮을수록 유리 (리픽싱 하한)
            interp = "투자자 유리" if pct <= 40 else ("투자자 불리" if pct >= 60 else "시장 평균")
        table_rows.append({
            "항목": f"{label} ({unit})",
            "우리 딜": ours if ours is not None else "—",
            "시장 P25": round(s.quantile(0.25), 2),
            "시장 중앙값": round(s.median(), 2),
            "시장 P75": round(s.quantile(0.75), 2),
            "우리 위치(%)": pct if pct is not None else "—",
            "해석(투자자 관점)": interp,
        })
    tdf = pd.DataFrame(table_rows).set_index("항목")
    show_fs_table(tdf.rename_axis("항목"), dl_stem="메자닌_벤치마킹", dl_key="mz_dl")

    # 리픽싱·풋옵션 부가 설명
    refix_rate = pd.to_numeric(comps["리픽싱하한(%)"], errors="coerce").notna().mean() * 100
    st.caption(f"· 리픽싱 부여 비율: 시장 {refix_rate:.0f}%  /  우리 딜: {deal['리픽싱여부']}"
               + (f" (하한 {deal['리픽싱하한(%)']:.0f}%)" if deal['리픽싱하한(%)'] is not None else ""))
    put_txt = deal["풋옵션여부"] + (f" (YTP {deal['풋옵션금리']:.2f}%)" if deal["풋옵션금리"] is not None else "")
    st.caption(f"· 풋옵션: 우리 딜 {put_txt}  /  ⚠️ 풋옵션은 DART 정형 데이터에 없어 시장 비교값은 제공되지 않습니다.")

    # --- 시각화: 핵심 지표 퍼센타일 위치 ---
    st.markdown("#### 우리 딜의 시장 내 위치")
    for label, col, unit, hib in MEZZ_METRICS:
        if hib is None:
            continue
        s = pd.to_numeric(comps[col], errors="coerce").dropna()
        ours = deal.get(col)
        pct = _pct_of(s, ours)
        if pct is None or s.empty:
            continue
        st.caption(f"{label}: 우리 {ours}{unit}  ·  시장 중앙값 {s.median():.2f}{unit}  ·  하위 {pct}% 지점")
        st.progress(int(pct))

    # --- AI 심사역 ---
    st.divider()
    st.subheader("🤖 AI 심사역 의견 (선택)")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 위 통계를 근거로 딜 평가·조정 제안 메모를 만들어줍니다.")
        return
    if st.button("AI 심사역 의견 생성", key="mz_ai_btn"):
        stats_lines = []
        for label, col, unit, hib in MEZZ_METRICS:
            s = pd.to_numeric(comps[col], errors="coerce").dropna()
            if s.empty:
                continue
            ours = deal.get(col)
            stats_lines.append(f"- {label}: 시장 P25 {s.quantile(0.25):.2f} / 중앙값 {s.median():.2f} "
                               f"/ P75 {s.quantile(0.75):.2f} {unit} (우리 {ours}{unit})")
        stats_lines.append(f"- 리픽싱: 시장 부여비율 {refix_rate:.0f}% (우리 {deal['리픽싱여부']})")
        deal_text = (f"표면금리 {deal['표면금리']}%, YTM {deal['YTM']}%, 만기 {deal['만기(년)']}년, "
                     f"규모 {deal['규모(억)']}억, 발행비율(희석) {deal['발행비율(%)']}%, "
                     f"리픽싱 {deal['리픽싱여부']}"
                     + (f"(하한 {deal['리픽싱하한(%)']}%)" if deal['리픽싱하한(%)'] is not None else "")
                     + f", 풋옵션 {deal['풋옵션여부']}"
                     + (f"(YTP {deal['풋옵션금리']}%)" if deal['풋옵션금리'] is not None else ""))
        try:
            with st.spinner("AI 심사역이 검토 중..."):
                memo = mezz_ai_opinion(anthropic_key, ai_model, res["kind"], deal_text,
                                       "\n".join(stats_lines), n)
            st.session_state["mz_ai"] = memo
        except DartError as e:
            st.error(str(e))
            return
    if "mz_ai" in st.session_state:
        st.markdown(st.session_state["mz_ai"])
        st.caption("※ 투자 권유가 아니라 협상 참고용입니다. 수치는 반드시 원문과 대조하세요.")


# ==================================================================
#  탭 7) 발행조건 스크리너 (대항목·중항목·연도·CB/BW → 종목 주르륵, 시총 상위순)
# ==================================================================
# =========================================================================
#  데이터 소스: 자동 전환
#   · DB에 해당 유형(CB/BW)이 적재돼 있으면  → DB에서 즉시 조회 (빠름)
#   · 아직 백필 전이라 DB가 비어 있으면       → DART에서 실시간 조회 (느림)
#  따라서 "데이터 관리" 탭에서 백필을 한 번 돌리면, 이후로는 자동으로 DB를 씁니다.
# =========================================================================
def build_screener_df(kind, bgn, es, progress=None, max_corps=900):
    """DB에 적재분이 있으면 DB에서 즉시 조회, 없으면(백필 전) DART 실시간 조회."""
    if db_bond_count(kind) > 0:
        return db_query_bond(kind, bgn, es)
    return _live_screener_scan(kind, bgn, es, progress=progress, max_corps=max_corps)


def _live_screener_scan(kind, bgn, es, progress=None, max_corps=900):
    """(폴백) DART에서 직접 CB/BW를 수집해 스크리너 형태 DataFrame으로 반환."""
    ep = "cvbdIsDecsn.json" if kind == "CB" else "bdwtIsDecsn.json"
    kw = "전환사채" if kind == "CB" else "신주인수권부사채"
    if progress:
        progress(0.0, "DB가 비어 실시간으로 공시 목록을 불러오는 중...")
    all_rows = []
    for cb, ce in _date_chunks(bgn, es, 90):
        try:
            rows, _, _ = dart_list_all({"bgn_de": cb, "end_de": ce, "pblntf_ty": "B"})
            all_rows.extend(rows)
        except DartError:
            continue
    ldf = pd.DataFrame(all_rows)
    if ldf.empty:
        return pd.DataFrame()
    ldf = ldf[ldf["report_nm"].str.contains(kw, na=False, regex=False)]
    if "rcept_no" in ldf.columns:
        ldf = ldf.drop_duplicates("rcept_no")
    if ldf.empty:
        return pd.DataFrame()
    codes = list(dict.fromkeys(ldf["corp_code"].tolist()))[:max_corps]
    total = len(codes)
    recs = []
    for idx, code in enumerate(codes, 1):
        if progress and (idx % 5 == 0 or idx == total):
            progress(idx / total, f"실시간 수집 중... {idx}/{total}개사 (백필하면 즉시 조회됩니다)")
        try:
            drows = dart_get(ep, {"corp_code": code, "bgn_de": bgn, "end_de": es})
        except DartError:
            continue
        for r in drows:
            rec = _parse_bond_detail(r, kind)
            if not rec:
                continue
            iss = _parse_date(rec["issue_date"]); mat = _parse_date(rec["maturity"])
            years = round((mat - iss).days / 365.25, 1) if (iss and mat) else None
            price_col = "전환가액(원)" if kind == "CB" else "행사가액(원)"
            recs.append({
                "종목명": rec["corp_name"], "_corp_code": rec["corp_code"], "_shares": rec["shares"],
                "접수일": rec["rcept_dt"], "만기일": rec["maturity"],
                "표면이자율(%)": rec["coupon"], "만기이자율(%)": rec["ytm"], "만기(년)": years,
                price_col: rec["price"], "리픽싱하한(%)": rec["refix_pct"],
                "리픽싱유무": "있음" if rec["refix_pct"] is not None else "없음",
                "희석비율(%)": rec["dilution"], "사채총액(억)": rec["amount_eok"],
                "원문": (DART_VIEWER + rec["rcept_no"]) if rec["rcept_no"] else None,
            })
    return pd.DataFrame(recs)


SCREENER_MAJORS = [
    "시가총액", "전환가격 조정(리픽싱)", "표면이자율", "만기이자율(YTM)", "만기",
    "발행대상자 (원문)", "조기상환권/풋 (원문)", "매도청구권/콜 (원문)",
]


def _apply_screener_filter(df, major, sub, cap_col):
    """대항목·중항목에 따라 df를 거른다."""
    s = df
    if major == "시가총액":
        if cap_col in s.columns:
            cap = pd.to_numeric(s[cap_col], errors="coerce")
            lo, hi = (sub if isinstance(sub, (tuple, list)) else (sub, 0))
            m = cap.notna()
            if lo:
                m &= cap >= lo
            if hi:
                m &= cap <= hi
            s = s[m]
    elif major == "전환가격 조정(리픽싱)":
        if sub in ("있음", "없음"):
            s = s[s["리픽싱유무"] == sub]
    elif major == "표면이자율":
        col = pd.to_numeric(s["표면이자율(%)"], errors="coerce")
        if sub == "0%":
            s = s[col == 0]
        elif sub == "0~2%":
            s = s[(col > 0) & (col <= 2)]
        elif sub == "2% 이상":
            s = s[col >= 2]
    elif major == "만기이자율(YTM)":
        col = pd.to_numeric(s["만기이자율(%)"], errors="coerce")
        if sub == "2% 미만":
            s = s[col < 2]
        elif sub == "2~5%":
            s = s[(col >= 2) & (col <= 5)]
        elif sub == "5% 이상":
            s = s[col >= 5]
    elif major == "만기":
        col = pd.to_numeric(s["만기(년)"], errors="coerce")
        if sub == "2년 이하":
            s = s[col <= 2]
        elif sub == "3년":
            s = s[(col > 2) & (col <= 3)]
        elif sub == "3년 초과":
            s = s[col > 3]
    # 원문 대항목(발행대상자/조기상환권/매도청구권)은 필터 없이 전체 + 원문 링크 제공
    return s


def _pct_near(window):
    """텍스트 조각에서 비율(%)을 뽑는다. '100분의 30' 또는 '30%' / '30 퍼센트'."""
    m = re.search(r"100\s*분\s*의\s*(\d+(?:\.\d+)?)", window)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|퍼센트|％)", window)
    if m:
        try:
            v = float(m.group(1))
            if 0 < v <= 100:
                return v
        except ValueError:
            pass
    return None


def extract_call_put(text):
    """공시 원문에서 콜(매도청구권)·풋(조기상환청구권) 유무와 비율(%)을 베스트에포트로 추출."""
    out = {"콜옵션": None, "콜옵션(%)": None, "풋옵션": None, "풋옵션(%)": None}
    if not text:
        return out
    t = re.sub(r"\s+", " ", text)
    # 콜옵션(매도청구권/콜옵션/Call Option/매수할 수 있는 권리)
    cm = re.search(r"(매도청구권|콜\s*옵션|call\s*option|매수할\s*수\s*있는)", t, re.I)
    if cm:
        out["콜옵션"] = "있음"
        out["콜옵션(%)"] = _pct_near(t[max(0, cm.start() - 60): cm.start() + 700])
    else:
        out["콜옵션"] = "없음"
    # 풋옵션(조기상환청구권/풋옵션/Put Option/조기상환을 청구) — 인접한 콜 문구 숫자 오염을 막으려 키워드 '뒤쪽'만 탐색
    pm = re.search(r"(조기상환청구권|풋\s*옵션|put\s*option|조기상환을?\s*청구)", t, re.I)
    if pm:
        out["풋옵션"] = "있음"
        out["풋옵션(%)"] = _pct_near(t[pm.start(): pm.start() + 700])
    else:
        out["풋옵션"] = "없음"
    return out


def extract_call_put_ai(anthropic_key, model, text, company):
    """공시 원문에서 콜/풋을 AI로 추출. 정규식과 동일한 dict 키로 반환(더 정확, 비용 발생)."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 후 다시 시도하세요.")
    # 특약 관련 구간만 추려 비용 절감
    spans = []
    for kw in ["매도청구권", "조기상환청구권", "콜옵션", "풋옵션", "Call Option",
               "Put Option", "특약", "매수할 수 있는", "조기상환"]:
        for m in re.finditer(re.escape(kw), text):
            spans.append((max(0, m.start() - 200), min(len(text), m.start() + 900)))
    sliced = text[:9000]
    if spans:
        spans.sort()
        merged = [list(spans[0])]
        for s, e in spans[1:]:
            if s <= merged[-1][1] + 150:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        parts, tot = [], 0
        for s, e in merged:
            ch = text[s:e]
            if tot + len(ch) > 9000:
                ch = ch[:9000 - tot]
            parts.append(ch)
            tot += len(ch)
            if tot >= 9000:
                break
        sliced = "\n...\n".join(parts)
    prompt = (f"{company}의 사채 발행 공시 원문에서 콜옵션(매도청구권)과 풋옵션(조기상환청구권)을 판단하세요.\n"
              "원문에 있는 내용만 사용하고, 없으면 '없음'으로, 비율을 알 수 없으면 ''로 두세요. "
              "비율은 숫자(%)만 쓰세요(예: 30).\n"
              'JSON만 출력: {"콜옵션":"있음|없음","콜옵션비율":"","풋옵션":"있음|없음","풋옵션비율":""}\n\n'
              f"[원문 발췌]\n{sliced}")
    try:
        msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
            model=model, max_tokens=300, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    raw = "".join(getattr(b, "text", "") for b in msg.content)
    i, j = raw.find("{"), raw.rfind("}")
    data = {}
    if i >= 0 and j >= 0:
        try:
            data = json.loads(raw[i:j + 1])
        except Exception:
            data = {}

    def _yn(v):
        s = str(v or "").strip()
        return "있음" if s.startswith("있") else ("없음" if s.startswith("없") else (s or None))
    return {
        "콜옵션": _yn(data.get("콜옵션")),
        "콜옵션(%)": _mznum(data.get("콜옵션비율")),
        "풋옵션": _yn(data.get("풋옵션")),
        "풋옵션(%)": _mznum(data.get("풋옵션비율")),
    }


def _rcept_from_url(u):
    """원문 뷰어 URL에서 접수번호(rcpNo)만 뽑는다."""
    s = str(u or "")
    return s.split("rcpNo=")[-1] if "rcpNo=" in s else ""


def tab_screener(corp_df):
    st.header("🔎 Ⅱ. Look-up - 1. 발행내역 전체 screen")
    st.caption("【Flow 1단계】 발행가능성 있는 기업을 **러프하게** 찾는 단계입니다. 기간·시가총액·발행유형(CB/BW/유상증자)·"
               "조건을 골라 전체 발행내역을 한눈에 봅니다. 회사명을 비우면 기간 내 전체가, 입력하면 그 회사만 나옵니다. "
               "여기서 전체 리스트를 추린 뒤 → 'Ⅱ-2. 발행 후보 기업 · look-up'에서 세부 조건으로 좁히세요.")

    c1, c2 = st.columns([1.4, 1])
    type_label = c1.radio("발행 유형", ["CB (전환사채)", "BW (신주인수권부사채)", "유상증자"], horizontal=True)
    name = c2.text_input("회사명 (비우면 전체)", "", key="scr_name")
    is_cbbw = type_label.startswith("CB") or type_label.startswith("BW")
    kind_code = "CB" if type_label.startswith("CB") else ("BW" if type_label.startswith("BW") else None)

    p1, p2 = st.columns([1, 1])
    _yrs = [str(y) for y in range(dt.date.today().year, 2016, -1)]   # 2017 ~ 올해
    period = p1.selectbox("조회 기간", ["최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"]
                          + _yrs + ["직접 지정"], index=2)
    major = None
    if is_cbbw:
        major = p2.selectbox("대항목(조건 필터)", SCREENER_MAJORS)

    cust_bgn = cust_end = None
    if period == "직접 지정":
        d1, d2 = st.columns(2)
        cust_bgn = d1.date_input("시작일", dt.date.today() - dt.timedelta(days=90), key="scr_b")
        cust_end = d2.date_input("종료일", dt.date.today(), key="scr_e")

    # 중항목 (CB/BW + 대항목에 따라)
    sub = None
    if is_cbbw:
        if major == "시가총액":
            cc1s, cc2s = st.columns(2)
            cap_lo = cc1s.number_input("중항목 — 시가총액 최소 (억원, 0=하한없음)",
                                       value=0.0, step=500.0, format="%.0f", key="scr_cap_lo")
            cap_hi = cc2s.number_input("중항목 — 시가총액 최대 (억원, 0=상한없음)",
                                       value=0.0, step=500.0, format="%.0f", key="scr_cap_hi")
            sub = (cap_lo, cap_hi)
        elif major == "전환가격 조정(리픽싱)":
            sub = st.selectbox("중항목 — 리픽싱", ["전체", "있음", "없음"])
        elif major == "표면이자율":
            sub = st.selectbox("중항목 — 표면이자율", ["전체", "0%", "0~2%", "2% 이상"])
        elif major == "만기이자율(YTM)":
            sub = st.selectbox("중항목 — 만기이자율(YTM)", ["전체", "2% 미만", "2~5%", "5% 이상"])
        elif major == "만기":
            sub = st.selectbox("중항목 — 만기", ["전체", "2년 이하", "3년", "3년 초과"])
        elif major and major.endswith("(원문)"):
            st.info(f"'{major}'는 DART 정형 데이터에 없어 자동 필터가 안 됩니다. 전체 목록과 원문 링크를 제공합니다.")

    if st.button("조회", type="primary", key="scr_btn"):
        today = dt.date.today()
        preset_days = {"최근 1개월": 30, "최근 3개월": 90, "최근 6개월": 180, "최근 1년": 365}
        if period == "직접 지정":
            bgn_d, end_d = cust_bgn, cust_end
        elif period in preset_days:
            bgn_d, end_d = today - dt.timedelta(days=preset_days[period]), today
        else:  # 특정 연도
            bgn_d = dt.date(int(period), 1, 1)
            end_d = min(today, dt.date(int(period), 12, 31))
        bs, es = bgn_d.strftime("%Y%m%d"), end_d.strftime("%Y%m%d")
        nm = name.strip()
        row = resolve_corp(nm, corp_df) if nm else None
        if nm and row is None:
            st.warning("회사를 찾지 못했습니다. 이름을 정확히 입력해 보세요.")
            st.session_state.pop("scr_df", None)
            return
        pbar = st.progress(0.0, "준비 중...")
        try:
            if is_cbbw:
                df = build_screener_df(kind_code, bs, es, progress=lambda f, t: pbar.progress(f, t))
                if nm and not df.empty and "_corp_code" in df.columns:
                    df = df[df["_corp_code"].astype(str) == str(row["corp_code"])]
                if not df.empty:
                    pbar.progress(1.0, "시가총액 계산 중...")
                    df = _attach_market_cap(df, corp_df, kind_code)
            else:  # 유상증자
                spec = ISSUE_SPECS["유상증자"]
                if nm:
                    pbar.progress(0.4, "유상증자 상세 조회 중...")
                    df = _build_issue_df("유상증자", [row["corp_code"]],
                                         {row["corp_code"]: row["corp_name"]}, spec["ep"], bs, es)
                else:
                    df = build_issue_all(api_key, "유상증자", bs, es)
                if not df.empty:
                    pbar.progress(1.0, "시가총액 계산 중...")
                    df = _attach_market_cap(df, corp_df, "유상증자")
        except DartError as e:
            pbar.empty()
            st.error(str(e))
            return
        pbar.empty()
        st.session_state["scr_df"] = df
        st.session_state["scr_ctx"] = (type_label, kind_code, is_cbbw, major, sub, nm)
        st.session_state.pop("scr_cp", None)        # 콜/풋 추출 결과 초기화

    if "scr_df" not in st.session_state:
        return
    df = st.session_state["scr_df"]
    tl, kc, is_cbbw, mj, sb, nm = st.session_state["scr_ctx"]
    if df is None or df.empty:
        st.info("해당 조건의 발행내역이 없습니다. 기간·유형·회사명을 바꿔보거나, CB/BW는 '🗄️ 데이터 관리(DB)'에서 먼저 백필하세요.")
        return

    cap_col = "시가총액(억)"
    if is_cbbw:
        out = _apply_screener_filter(df, mj, sb, cap_col)
        if cap_col in out.columns and out[cap_col].notna().any():
            out = out.sort_values(cap_col, ascending=False, na_position="last")
        elif "접수일" in out.columns:
            out = out.sort_values("접수일", ascending=False)
        price_col = "전환가액(원)" if kc == "CB" else "행사가액(원)"
        display_cols = [c for c in ["종목명", "접수일", "표면이자율(%)", "만기이자율(%)", "만기(년)",
                                    price_col, "리픽싱하한(%)", "희석비율(%)", "사채총액(억)",
                                    cap_col, "발행/시총(%)", "원문"] if c in out.columns]

        # ---- 콜/풋 옵션 추출 (원문 파싱 · 상위 N건) ----
        with st.expander("🧷 콜/풋 옵션 추출 (원문 파싱 · 느림)"):
            st.caption("콜(매도청구권)·풋(조기상환청구권)은 DART 정형 데이터가 아니라 공시 원문의 '특약'에 글로 적혀 있어, "
                       "원문을 받아 파싱해야 합니다. 아래 상위 N건만 추출하며, 원문과 대조를 권장합니다.")
            cpc1, cpc2 = st.columns([1, 1.4])
            npick = cpc1.number_input("추출할 상위 건수", value=30, min_value=1, max_value=200, step=10, key="scr_cp_n")
            use_ai = cpc2.checkbox("AI로 추출 (더 정확, 건당 비용 발생)", key="scr_cp_ai",
                                   help="체크하면 Anthropic AI로 특약을 해석합니다(사이드바 키 필요). "
                                        "미체크 시 무료 정규식으로 추출합니다.")
            if use_ai and not anthropic_key:
                st.warning("AI 추출을 쓰려면 사이드바에 Anthropic API 키를 입력하세요. (키가 없으면 정규식으로 추출됩니다)")
            if st.button("콜/풋 추출 실행", key="scr_cp_btn"):
                ai_on = bool(use_ai and anthropic_key)
                head = out.head(int(npick))
                results = {}
                pbar = st.progress(0.0, ("AI로 분석 중..." if ai_on else "원문 파싱 중..."))
                n = len(head)
                for i, (_, r) in enumerate(head.iterrows(), 1):
                    rc = _rcept_from_url(r.get("원문"))
                    if rc:
                        try:
                            txt = fetch_dart_document(api_key, rc)
                            if ai_on:
                                try:
                                    results[rc] = extract_call_put_ai(anthropic_key, ai_model, txt, r.get("종목명", ""))
                                except Exception:
                                    results[rc] = extract_call_put(txt)   # AI 실패 시 정규식 폴백
                            else:
                                results[rc] = extract_call_put(txt)
                        except Exception:
                            results[rc] = {}
                    pbar.progress(i / max(n, 1), f"{'AI 분석' if ai_on else '원문 파싱'} {i}/{n}")
                pbar.empty()
                st.session_state["scr_cp"] = results
                st.session_state["scr_cp_method"] = "AI" if ai_on else "정규식"
                st.success(f"{len([v for v in results.values() if v])}건 추출 완료 "
                           f"(상위 {n}건 · {st.session_state['scr_cp_method']} 방식)")

        cp = st.session_state.get("scr_cp")
        if cp and "원문" in out.columns:
            def _cpv(u, k):
                return cp.get(_rcept_from_url(u), {}).get(k)
            for col in ["콜옵션", "콜옵션(%)", "풋옵션", "풋옵션(%)"]:
                out[col] = out["원문"].map(lambda u, k=col: _cpv(u, k))
            # 원문 앞에 콜/풋 열 끼워넣기
            opt_cols = ["콜옵션", "콜옵션(%)", "풋옵션", "풋옵션(%)"]
            base = [c for c in display_cols if c != "원문"]
            display_cols = base + opt_cols + (["원문"] if "원문" in display_cols else [])
            method = st.session_state.get("scr_cp_method", "정규식")
            st.caption(f"콜/풋 열은 상위 {int(st.session_state.get('scr_cp_n', 30))}건 원문에서 {method}으로 추출(베스트에포트). "
                       "빈칸은 미추출 또는 해당 조건 없음 · 원문과 대조 권장.")

        st.caption(f"{tl} · {mj} · 결과 {len(out):,}건" + (f" · '{nm}'" if nm else " · 시가총액 상위순"))
        out = out.rename(columns={"접수일": "공시일"})
        display_cols = ["공시일" if c == "접수일" else c for c in display_cols]
        show_table(out[display_cols], f"스크리너_{kc}_{dt.date.today():%Y%m%d}", "scr_dl", link_cols=("원문",))
    else:
        out = df.sort_values("접수일", ascending=False) if "접수일" in df.columns else df
        out = out.drop(columns=[c for c in ["_corp_code", "_shares"] if c in out.columns])
        out = out.rename(columns={"접수일": "공시일"})
        st.caption(f"{tl} · 결과 {len(out):,}건" + (f" · '{nm}'" if nm else ""))
        show_table(out, f"유상증자_{dt.date.today():%Y%m%d}", "scr_dl", link_cols=("원문",))


# ==================================================================
#  탭 8) 기업 발행 동향 (회차별 조건·일정 + 영업 신호 + 인수기관)
# ==================================================================
def build_company_bonds(api_key_arg, corp_code, kind, bgn, es):
    """한 회사의 CB/BW 회차별 발행 조건.
    DB에 그 회사가 있으면 DB에서(즉시), 없으면(백필 전·적재기간 밖) DART 실시간 폴백."""
    recs = db_query_company_bond(corp_code, kind)
    if recs:
        return recs
    return _live_company_bonds(corp_code, kind, bgn, es)


def _live_company_bonds(corp_code, kind, bgn, es):
    """(폴백) DB에 없을 때 DART에서 해당 회사의 CB/BW를 직접 받아 DB 조회와 동일한 형태로 반환.
    단일 기업은 corp_code가 있어 공시검색 90일 제한에 걸리지 않고 상세 엔드포인트로 바로 조회 가능."""
    ep = "cvbdIsDecsn.json" if kind == "CB" else "bdwtIsDecsn.json"
    price_lbl = "최초전환가(원)" if kind == "CB" else "최초행사가(원)"
    recs = []
    # 긴 구간은 DART가 거절할 수 있어 3년 단위로 나눠 조회(단일 기업이라 호출 수는 적음)
    for cb, ce in _date_chunks(bgn, es, 365 * 3):
        try:
            drows = dart_get(ep, {"corp_code": corp_code, "bgn_de": cb, "end_de": ce})
        except DartError:
            continue
        for r in drows:
            rec = _parse_bond_detail(r, kind)
            if not rec:
                continue
            iss = _parse_date(rec["issue_date"])
            if not iss:
                continue
            recs.append({
                "회차": rec["round_no"], "발행일": iss,
                "발행액(억)": rec["amount_eok"], "표면(%)": rec["coupon"],
                "만기이자율(%)": rec["ytm"], price_lbl: rec["price"],
                "리픽싱하한(원)": rec["refix_floor"], "만기일": _parse_date(rec["maturity"]),
                "_rcept": rec["rcept_no"],
            })
    # 접수번호 기준 중복 제거 후 발행일 순 정렬
    seen, uniq = set(), []
    for x in sorted(recs, key=lambda x: x["발행일"]):
        if x["_rcept"] in seen:
            continue
        seen.add(x["_rcept"])
        uniq.append(x)
    return uniq


def _months_between(d0, d1):
    return (d1.year - d0.year) * 12 + (d1.month - d0.month)


def extract_underwriters_ai(anthropic_key, model, text, company, round_no):
    """발행결정 원문에서 인수(배정)기관 목록을 AI로 추출."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 후 다시 시도하세요.")
    # 배정/인수 관련 구간만 추려 비용 절감
    import re as _re
    spans = []
    for kw in ["배정", "인수", "청약", "특정인", "대상자", "모집"]:
        for m in _re.finditer(kw, text):
            spans.append((max(0, m.start() - 300), min(len(text), m.start() + 1200)))
    sliced = text[:35000]
    if spans:
        spans.sort()
        merged = [list(spans[0])]
        for s, e in spans[1:]:
            if s <= merged[-1][1] + 200:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        out, tot = [], 0
        for s, e in merged:
            ch = text[s:e]
            if tot + len(ch) > 35000:
                ch = ch[:35000 - tot]
            out.append(ch); tot += len(ch)
            if tot >= 35000:
                break
        sliced = "\n...\n".join(out)
    prompt = f"""{company}의 {round_no} 사채 발행 공시 원문에서, 이 사채를 '배정받은(인수한) 기관/투자자' 명단과 금액을 뽑으세요.
아래 원문에 있는 것만 사용하고, 없으면 빈 배열로 두세요. 숫자는 원문 표기를 따르세요.
JSON만 출력: {{"인수기관":[{{"기관명":"","배정금액":""}}]}}

[원문 발췌]
{sliced}"""
    try:
        msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
            model=model, max_tokens=1500, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    raw = "".join(getattr(b, "text", "") for b in msg.content)
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0:
        raise DartError("AI 응답에서 데이터를 읽지 못했습니다.")
    try:
        return json.loads(raw[i:j + 1])
    except Exception:
        raise DartError("AI 응답(JSON) 해석 실패.")


def _amt_to_eok(s):
    """배정금액 문자열을 억원 숫자로. '50억원'→50, '5,000,000,000원'→50, '500백만원'→5."""
    if s is None:
        return None
    t = str(s)
    v = _mznum(t)
    if v is None:
        return None
    if "억" in t:
        return round(v)
    if "백만" in t:
        return round(v / 100)
    if v >= 1e8:                 # 원 단위로 보이면
        return round(v / 1e8)
    return round(v)              # 이미 억 단위로 간주


def extract_underwriters_list(anthropic_key, model, text, company):
    """발행 1건 원문에서 배정기관 리스트 [{'inst','amount_eok'}] 반환 (AI)."""
    res = extract_underwriters_ai(anthropic_key, model, text, company, "")
    out = []
    for it in (res.get("인수기관") or []):
        nm = (it.get("기관명") or "").strip()
        if nm:
            out.append({"inst": nm, "amount_eok": _amt_to_eok(it.get("배정금액"))})
    return out


def _safe_num(v):
    n = pd.to_numeric(v, errors="coerce")
    try:
        return None if pd.isna(n) else float(n)
    except (TypeError, ValueError):
        return None


def analysis_ai(anthropic_key, model, lines, n_cand):
    """look-up 후보 기업들을 종합해 '딜소싱 유력 순위 + 이유'를 간략 리포트로."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 후 다시 시도하세요.")
    prompt = f"""당신은 메자닌(CB/BW) 딜소싱 투자심사역입니다.
아래는 재무·발행 조건으로 1차 선별된 후보 기업 {n_cand}곳의 요약입니다. 제공된 숫자만 근거로,
'추가 발행(딜소싱) 가능성이 높은 유력 후보'를 순위화하고 이유를 쓰세요. 숫자를 지어내지 마세요.

판단 기준: ① 만기 임박(차환 수요·시급) ② 현금성자산 부족·영업적자·이자부담(자금수요↑) ③ 미상환(만기전) 잔액 대비 상환 부담 ④ 규모(시가총액).

[후보 기업 요약]
{lines}

출력(한국어):
1) 유력 딜소싱 후보 Top 5 — 각 '회사명: 한 줄 이유(자금수요/만기/상환부담 근거)'
2) 그 외 주목 기업 (간단히)
3) 한 줄 총평
마지막에 '투자권유가 아니라 영업(딜소싱) 참고용'임을 명시."""
    try:
        msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
            model=model, max_tokens=1600, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    return "".join(getattr(b, "text", "") for b in msg.content)


def build_candidates_full(corp_df, kind, bs, es, within_days, mincap, add_fin, progress=None):
    """발행 스캔 → 후보 집계(+선택 재무)까지 한 번에. look-up/Analysis 공용.
    반환: (cdf, fin_cols, periods)"""
    df = build_screener_df(kind, bs, es, progress=progress)
    if not df.empty:
        df = _attach_market_cap(df, corp_df, kind)
    if df is None or df.empty:
        return pd.DataFrame(), [], []

    today = dt.date.today()
    horizon = today + dt.timedelta(days=within_days)
    price_col = "전환가액(원)" if kind == "CB" else "행사가액(원)"
    cap_col = "시가총액(억)"
    cand = []
    for name, grp in df.groupby("종목명"):
        total_cnt = len(grp)
        up = grp[grp["만기일"].notna()].copy()
        up["_mat"] = pd.to_datetime(up["만기일"], errors="coerce").dt.date
        up = up[(up["_mat"] >= today) & (up["_mat"] <= horizon)]
        if up.empty:
            continue
        cap = None
        if cap_col in grp.columns:
            vals = pd.to_numeric(grp[cap_col], errors="coerce").dropna()
            cap = int(vals.iloc[0]) if len(vals) else None
        if mincap and (cap is None or cap < mincap):
            continue
        amt = pd.to_numeric(up["사채총액(억)"], errors="coerce").dropna().sum()
        corp_code = str(grp["_corp_code"].iloc[0]) if "_corp_code" in grp.columns else None
        g2 = grp.copy()
        g2["_mat"] = pd.to_datetime(g2["만기일"], errors="coerce").dt.date
        alive = g2[g2["_mat"].notna() & (g2["_mat"] >= today)]
        outstanding = pd.to_numeric(alive["사채총액(억)"], errors="coerce").dropna().sum()
        latest = grp.sort_values("접수일", ascending=False).iloc[0] if "접수일" in grp.columns else grp.iloc[0]
        cand.append({
            "종목명": name, "_corp_code": corp_code,
            "최근 공시일": latest.get("접수일"),
            "표면이자율(%)": latest.get("표면이자율(%)"),
            "만기이자율(%)": latest.get("만기이자율(%)"),
            "만기(년)": latest.get("만기(년)"),
            price_col: latest.get(price_col),
            "리픽싱하한(%)": latest.get("리픽싱하한(%)"),
            "희석비율(%)": latest.get("희석비율(%)"),
            "사채총액(억)": latest.get("사채총액(억)"),
            "과거 총 발행": total_cnt,
            "시가총액(억)": cap,
            "가장 가까운 만기": min(up["_mat"]).strftime("%Y-%m-%d"),
            "도래 예정액(억)": int(amt) if amt else None,
            "만기전 발행잔액(억)": int(outstanding) if outstanding else None,
            "도래 회차수": len(up),
        })
    cdf = pd.DataFrame(cand).sort_values("가장 가까운 만기").reset_index(drop=True) if cand else pd.DataFrame()

    fin_cols, periods = [], []
    if add_fin and not cdf.empty:
        ann_year = today.year - 1
        cur_year = today.year
        periods = [f"{ann_year-2}년", f"{ann_year-1}년", f"{ann_year}년", f"{cur_year}년 상반기"]
        fin_cols = [f"{p} {m}" for p in periods for m in DEMAND_FIN_METRICS]
        pbar = st.progress(0.0, "후보기업 최신 보고서에서 재무 추출 중...")
        tot_n = len(cdf)
        fin_rows = []
        for i, r in cdf.iterrows():
            cc = r["_corp_code"]
            fin = fetch_company_financials(api_key, cc, ann_year, cur_year) if cc else {}
            row = {}
            for p in periods:
                pdata = fin.get(p, {})
                for m in DEMAND_FIN_METRICS:
                    row[f"{p} {m}"] = pdata.get(m)
            fin_rows.append(row)
            pbar.progress((i + 1) / tot_n, f"재무 추출 중... {i+1}/{tot_n}개사")
        pbar.empty()
        cdf = pd.concat([cdf, pd.DataFrame(fin_rows, index=cdf.index)], axis=1)
    return cdf, fin_cols, (periods if add_fin else [])


def tab_analysis(corp_df):
    st.header("🧭 Ⅲ. Analysis")
    st.caption("【Flow 3단계】 발행 후보 기업을 대상으로, 어떤 기업이 딜소싱 후보로 유력한지 "
               "자금수요·상환부담·발행 타이밍을 종합해 순위화합니다. 아래에서 **유형·기간을 직접 정해 조회**하거나, "
               "'Ⅱ-2. 발행 후보 기업 · look-up'의 결과를 그대로 이어받아 분석합니다.")

    # ---- 자체 조회 컨트롤 (look-up의 1) 일반적 발행 검토와 동일) ----
    a0, a1, a2, a3 = st.columns([1.2, 2, 2, 2])
    an_kind = a0.radio("발행 유형", ["CB", "BW"], horizontal=True, key="an_kind")
    an_scan = a1.selectbox("스캔 대상 (발행 시점)",
                           ["최근 3년 발행분", "최근 5년 발행분", "최근 2년 발행분", "연도 범위 지정"],
                           key="an_scan",
                           help="'연도 범위 지정'으로 특정 연도(예: 2018~2021)에 발행한 기업만 볼 수 있습니다.")
    an_within = a2.selectbox("만기 도래 기간", ["앞으로 6개월", "앞으로 12개월", "앞으로 18개월", "앞으로 24개월"],
                             key="an_within")
    an_mincap = a3.number_input("시가총액 최소 (억, 0=전체)", value=0.0, step=500.0, format="%.0f", key="an_mincap")

    _antoday = dt.date.today()
    if an_scan == "연도 범위 지정":
        _ayrs = list(range(2017, _antoday.year + 1))
        asc1, asc2 = st.columns(2)
        asy_from = asc1.selectbox("발행 시작 연도", _ayrs, index=max(0, len(_ayrs) - 4), key="an_yfrom")
        asy_to = asc2.selectbox("발행 종료 연도", _ayrs, index=len(_ayrs) - 1, key="an_yto")
        if asy_from > asy_to:
            asy_from, asy_to = asy_to, asy_from
        an_scan_bs = f"{asy_from}0101"
        an_scan_es = min(_antoday, dt.date(asy_to, 12, 31)).strftime("%Y%m%d")
    else:
        an_scan_years = {"최근 2년 발행분": 2, "최근 3년 발행분": 3, "최근 5년 발행분": 5}[an_scan]
        an_scan_bs = (_antoday - dt.timedelta(days=365 * an_scan_years)).strftime("%Y%m%d")
        an_scan_es = _antoday.strftime("%Y%m%d")

    an_add_fin = st.checkbox("후보기업 연도별 재무 추가 (매출·영업이익·현금성자산·부채·자본 / 최신 보고서 기준)",
                             value=True, key="an_fin")
    an_loss3 = st.checkbox("최근 3개년 연속 영업적자 제외", key="an_loss3",
                           help="최근 3개 사업연도 영업이익이 모두 적자인 기업을 결과에서 제외합니다. (재무 추가 필요)")
    an_within_days = {"앞으로 6개월": 183, "앞으로 12개월": 365, "앞으로 18개월": 548, "앞으로 24개월": 730}[an_within]

    if st.button("조회", type="primary", key="an_btn"):
        bs, es = an_scan_bs, an_scan_es
        pbar = st.progress(0.0, "준비 중...")
        try:
            _cdf, _fc, _pe = build_candidates_full(corp_df, an_kind, bs, es, an_within_days,
                                                   an_mincap, an_add_fin,
                                                   progress=lambda f, t: pbar.progress(f, t))
        except DartError as e:
            pbar.empty(); st.error(str(e)); return
        pbar.empty()
        st.session_state["an_cdf"] = _cdf
        st.session_state["an_fincols"] = _fc
        st.session_state["an_periods"] = _pe
        st.session_state["an_src_kind"] = an_kind
        st.session_state.pop("an_ai", None)
        st.session_state.pop("an_sum_sig", None)

    # ---- 데이터 소스: 자체 조회(an_cdf) 우선, 없으면 look-up 결과(dm_cdf) ----
    st.divider()
    if "an_cdf" in st.session_state:
        cdf = st.session_state.get("an_cdf")
        periods = st.session_state.get("an_periods", [])
        fin_cols = st.session_state.get("an_fincols", [])
        kind_src = st.session_state.get("an_src_kind", "CB")
    else:
        cdf = st.session_state.get("dm_cdf")
        periods = st.session_state.get("dm_periods", [])
        fin_cols = st.session_state.get("dm_fincols", [])
        _dmcfg = st.session_state.get("dm_cfg")
        kind_src = _dmcfg[4] if (_dmcfg and len(_dmcfg) > 4) else "CB"
    if cdf is None or len(cdf) == 0:
        st.info("위에서 **조회**를 눌러 유형·기간별 후보를 불러오거나, "
                "'Ⅱ-2. 발행 후보 기업 · look-up'에서 **수요기업 발굴**을 먼저 실행하세요.")
        return

    annuals = [p for p in periods if "상반기" not in p]
    # 최근 3개년 연속 영업적자 제외 (체크 시)
    if an_loss3 and periods:
        ann_cols = [f"{p} 영업이익" for p in annuals[-3:] if f"{p} 영업이익" in cdf.columns]
        if len(ann_cols) == 3:
            allneg = pd.Series(True, index=cdf.index)
            for _c in ann_cols:
                _vv = pd.to_numeric(cdf[_c], errors="coerce")
                allneg &= _vv.notna() & (_vv < 0)
            cdf = cdf[~allneg].reset_index(drop=True)
        else:
            st.caption("※ 연속 영업적자 제외는 '재무 추가'가 켜진 상태(3개 사업연도 영업이익)에서만 적용됩니다.")
    la = annuals[-1] if annuals else (periods[-1] if periods else None)
    cur = f"{dt.date.today().year}년 상반기"
    lp = cur if (periods and cur in periods) else la
    today = dt.date.today()

    # ===== 요약 데이터 준비 (상단 상세 + 하단 표 공용) =====
    es_a = today.strftime("%Y%m%d")
    names = [str(n) for n in cdf["종목명"].tolist()]
    code_map = {str(r.get("종목명")): str(r.get("_corp_code")) for _, r in cdf.iterrows()}
    sumsig = (tuple(names), kind_src)
    if st.session_state.get("an_sum_sig") != sumsig:
        srows = []
        pbar = st.progress(0.0, "발행이력 요약 집계 중...")
        n_tot = max(len(cdf), 1)
        for i2, nm in enumerate(names, 1):
            cc = code_map.get(nm)
            recs = build_company_bonds(api_key, cc, kind_src, "20120101", es_a) if cc and cc != "None" else []
            issues = [x["발행일"] for x in recs if x["발행일"]]
            last = max(issues) if issues else None
            elapsed = _months_between(last, today) if last else None
            total = sum(x["발행액(억)"] or 0 for x in recs)
            mats = [x for x in recs if x["만기일"] and x["만기일"] >= today]
            up = [x for x in mats if x["만기일"] <= today + dt.timedelta(days=550)]
            outb = sum((x["발행액(억)"] or 0) for x in recs if x["만기일"] and x["만기일"] >= today)
            srows.append({"기업명": nm, "총 발행 회차": len(recs), "누적 발행액(억)": total,
                          "만기전 발행잔액(억)": outb,
                          "직전 발행 후(개월)": elapsed, "18개월 내 만기(건)": len(up)})
            pbar.progress(i2 / n_tot, f"요약 집계 {i2}/{n_tot}")
        pbar.empty()
        st.session_state["an_sum"] = pd.DataFrame(srows)
        st.session_state["an_sum_sig"] = sumsig
    sumdf = st.session_state.get("an_sum", pd.DataFrame())

    # ===== (맨 위) 선택 기업 CB 발행 동향 상세 =====
    _selst = st.session_state.get("an_sum_tbl") or {}
    _selrows = (_selst.get("selection") or {}).get("rows", []) if isinstance(_selst, dict) else []
    if _selrows and not sumdf.empty and _selrows[0] < len(sumdf):
        pick_nm = str(sumdf.iloc[_selrows[0]]["기업명"])
        pick_cc = code_map.get(pick_nm)
        if st.session_state.get("an_co_last") != pick_nm:   # 기업 바뀌면 이전 AI 결과 제거
            st.session_state.pop("an_co_report", None)
            st.session_state.pop("an_co_uw", None)
            st.session_state["an_co_last"] = pick_nm
        if pick_cc and pick_cc != "None":
            with st.spinner(f"{pick_nm} 상세 발행내역을 불러오는 중..."):
                recs_d = build_company_bonds(api_key, pick_cc, kind_src, "20120101", es_a)
            render_company_detail(pick_nm, pick_cc, kind_src, recs_d, key_prefix="an_co")
        else:
            st.info("이 기업의 기업코드를 찾지 못해 상세를 불러올 수 없습니다.")
    else:
        st.info("아래 **발행내역 요약 (기업별)** 표에서 기업 행을 클릭하면, 그 기업의 CB 발행 동향이 여기(맨 위)에 표시됩니다.")

    # ===== 딜소싱 순위 (점수·등급) =====
    rows = []
    for _, r in cdf.iterrows():
        cash = _safe_num(r.get(f"{lp} 현금성자산")) if lp else None
        op = _safe_num(r.get(f"{la} 영업이익")) if la else None
        intr = _safe_num(r.get(f"{la} 이자비용")) if la else None
        cap = _safe_num(r.get("시가총액(억)"))
        out_bal = _safe_num(r.get("만기전 발행잔액(억)"))
        due = _safe_num(r.get("도래 예정액(억)"))
        matdate = r.get("가장 가까운 만기")
        d = _parse_date(matdate)
        dleft = (d - today).days if d else None

        score, sig = 0, []
        if dleft is not None:
            if dleft <= 183:
                score += 2; sig.append("만기 6개월내")
            elif dleft <= 365:
                score += 1; sig.append("만기 1년내")
        if cash is not None:
            if cash <= 100:
                score += 2; sig.append("현금성≤100억")
            elif cash <= 300:
                score += 1
        if op is not None and op < 0:
            score += 1; sig.append("영업적자")
        if intr is not None and cash is not None and intr > cash:
            score += 1; sig.append("이자>현금성")
        if out_bal and cap and out_bal >= cap * 0.1:
            score += 1; sig.append("미상환 부담")
        grade = "A" if score >= 5 else ("B" if score >= 3 else "C")
        rows.append({
            "회사": r.get("종목명"), "딜소싱점수": score, "등급": grade,
            "가까운 만기": matdate, "도래예정액(억)": due, "만기전잔액(억)": out_bal,
            "시가총액(억)": cap, f"현금성({lp})": cash, f"영업이익({la})": op,
            f"이자비용({la})": intr, "신호": " · ".join(sig) if sig else "-",
        })
    rdf = pd.DataFrame(rows).sort_values(["딜소싱점수", "가까운 만기"], ascending=[False, True]).reset_index(drop=True)

    st.divider()
    nA = int((rdf["등급"] == "A").sum()); nB = int((rdf["등급"] == "B").sum())
    m1, m2, m3 = st.columns(3)
    m1.metric("후보 기업", f"{len(rdf)}개사")
    m2.metric("A등급(유력)", f"{nA}개사")
    m3.metric("B등급(주목)", f"{nB}개사")
    st.caption("딜소싱점수: 만기 임박(≤6M +2/≤1Y +1) · 현금성(≤100억 +2/≤300억 +1) · 영업적자 +1 · 이자>현금성 +1 · "
               "미상환≥시총10% +1 → A(5↑)·B(3~4)·C. 점수 높을수록 자금수요·차환 필요성이 큼.")

    # 표시 테이블: look-up(발행 후보 기업)과 '동일한' 발행조건 컬럼으로 보여준다.
    #   (딜소싱점수·등급은 순위 파악용으로 좌측에 유지)
    price_col = "전환가액(원)" if "전환가액(원)" in cdf.columns else "행사가액(원)"
    score_map = rdf.set_index("회사")[["딜소싱점수", "등급"]].to_dict("index")
    disp = cdf.copy()
    disp["딜소싱점수"] = disp["종목명"].map(lambda n: (score_map.get(n) or {}).get("딜소싱점수"))
    disp["등급"] = disp["종목명"].map(lambda n: (score_map.get(n) or {}).get("등급"))
    sort_key = "가장 가까운 만기" if "가장 가까운 만기" in disp.columns else "종목명"
    disp = disp.sort_values(["딜소싱점수", sort_key], ascending=[False, True]).reset_index(drop=True)
    cond_cols = ["종목명", "딜소싱점수", "등급", "최근 공시일", "표면이자율(%)", "만기이자율(%)",
                 "만기(년)", price_col, "리픽싱하한(%)", "희석비율(%)", "사채총액(억)",
                 "과거 총 발행", "시가총액(억)"]
    order = [c for c in cond_cols if c in disp.columns] + [c for c in fin_cols if c in disp.columns]
    show = disp[order] if order else disp
    st.caption("발행조건은 각 기업의 **가장 최근 발행분** 기준입니다(look-up 표와 동일 항목)."
               + ("  · 재무 단위: 억원, 연결 우선(없으면 별도), 빈칸은 미제출/금융업." if fin_cols else ""))
    show_table(show, f"Analysis_후보순위_{dt.date.today():%Y%m%d}", "an_dl")

    # ---- 발행내역 요약 (기업별) · 선택 위젯 ----
    st.divider()
    st.subheader("📄 발행내역 요약 (기업별)")
    st.caption("각 후보 기업의 **발행 이력 요약**입니다. 표에서 **기업 행을 클릭하면** 그 기업의 "
               "CB 발행 동향 상세가 이 화면 **맨 위**에 표시됩니다.")
    if not sumdf.empty:
        st.dataframe(sumdf, hide_index=True, use_container_width=True,
                     on_select="rerun", selection_mode="single-row", key="an_sum_tbl")

    # ---- AI 종합 추천 ----
    st.divider()
    st.subheader("🤖 딜소싱 후보")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 위 후보들을 종합해 유력 순위와 이유를 정리해줍니다.")
    else:
        if st.button("AI 종합 추천 생성", type="primary", key="an_ai_btn"):
            top = rdf.head(20)
            lines = []
            for _, r in top.iterrows():
                lines.append(
                    f"- {r['회사']}(등급 {r['등급']}·{int(r['딜소싱점수'])}점): 가까운만기 {r['가까운 만기']}, "
                    f"도래액 {r['도래예정액(억)']}억, 미상환 {r['만기전잔액(억)']}억, 시총 {r['시가총액(억)']}억, "
                    f"현금성 {r[f'현금성({lp})']}억, 영업이익 {r[f'영업이익({la})']}억, 이자비용 {r[f'이자비용({la})']}억")
            try:
                with st.spinner("AI가 유력 후보를 정리하는 중..."):
                    memo = analysis_ai(anthropic_key, ai_model, "\n".join(lines), len(rdf))
                st.session_state["an_ai"] = memo
            except DartError as e:
                st.error(str(e))
        if "an_ai" in st.session_state:
            st.markdown(st.session_state["an_ai"])
            st.caption("※ 영업(딜소싱) 참고용. 수치는 반드시 원문·'발행내역 확인' 탭과 대조하세요.")

    st.caption("→ 특정 기업을 깊게 보려면 '발행내역 확인' 탭에 회사명을 넣어 회차·일정·배정기관·AI 리포트를 확인하세요.")


def company_report_ai(anthropic_key, model, company, kind, issue_lines, fin_lines):
    """한 기업의 발행이력+재무 요약으로 '딜소싱 대상 여부' 간략 리포트를 생성."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 후 다시 시도하세요.")
    prompt = f"""당신은 메자닌(CB/BW) 딜소싱을 담당하는 투자심사역입니다.
아래 '{company}'({kind})의 발행이력과 재무 요약만 근거로, 이 기업이 '추가 발행(딜소싱)의 대상이 되는지'를 판단하세요.
제공된 숫자만 사용하고 지어내지 마세요. 값이 비어있으면(None) 그 항목은 '자료 없음'으로 다루세요.

판단 포인트:
- 자금수요·현금창출력: 현금성자산이 적거나, 영업이익 적자·이자비용 부담이 크면 외부조달 수요가 높음
- 상환부담·여력: 만기전 발행잔액(미상환 추정)과 임박 만기 → 차환 필요성
- 발행주기: 과거 평균 발행주기 대비 직전 발행 후 경과 개월 → 재발행 타이밍

[발행 이력]
{issue_lines}

[재무 요약 · 단위 억원]
{fin_lines}

출력 형식(한국어): 근거를 든 3~5문장의 서술 + 마지막 줄에 '**결론:** (딜소싱 대상 여부 + 핵심 이유 한 문장)'.
예시 톤: "현금성 자산이 부족하고 기존 CB가 전환되어 잔액이 적은 상황. 자금 수요가 지속되고 만기도 임박해 발행 가능성이 높음."
"""
    try:
        msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
            model=model, max_tokens=900, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    return "".join(getattr(b, "text", "") for b in msg.content)


@st.cache_data(show_spinner=False, ttl=1800)
def latest_periodic_report_url(corp_code):
    """최신 정기보고서(사업/반기/분기) 원문 뷰어 URL. 없으면 None.
    (만기전 발행잔액 등은 부정확할 수 있어, 최신 정기보고서 원문으로 직접 확인용)"""
    try:
        rows, _, _ = dart_list_all({
            "corp_code": corp_code, "pblntf_ty": "A",      # A = 정기공시
            "bgn_de": "20170101", "end_de": dt.date.today().strftime("%Y%m%d"),
        }, max_pages=3)
    except Exception:
        return None
    best = None
    for r in rows:
        nm = r.get("report_nm") or ""
        if any(k in nm for k in ("사업보고서", "반기보고서", "분기보고서")):
            rd = r.get("rcept_dt") or ""
            if best is None or rd > best[0]:
                best = (rd, r.get("rcept_no"))
    return (DART_VIEWER + str(best[1])) if (best and best[1]) else None


def render_company_detail(name, code, kind, recs, key_prefix="co"):
    """한 기업의 발행 동향 상세(지표·신호·타임라인·회차표·AI·인수기관)를 그린다.
    tab_company 와 Ⅲ.Analysis 드릴다운에서 공통으로 사용."""
    st.subheader(f"{name} · {kind} 발행 동향")
    if not recs:
        st.info(f"이 회사의 {kind} 발행 내역을 찾지 못했습니다. (해당 유형 발행이 없을 수 있습니다)")
        return

    today = dt.date.today()

    # ---------- 영업 신호 (상단 지표) ----------
    issues = [r["발행일"] for r in recs if r["발행일"]]
    last_issue = max(issues) if issues else None
    elapsed = _months_between(last_issue, today) if last_issue else None
    total_amt = sum(r["발행액(억)"] or 0 for r in recs)
    mats = sorted([r for r in recs if r["만기일"] and r["만기일"] >= today], key=lambda x: x["만기일"])
    upcoming = [r for r in mats if r["만기일"] <= today + dt.timedelta(days=550)]
    outstanding = sum((r["발행액(억)"] or 0) for r in recs if r["만기일"] and r["만기일"] >= today)

    st.markdown("#### 1) 누적발행액, 직전발행후 잔액")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("총 발행 회차", f"{len(recs)}회")
    m2.metric("누적 발행액", f"{total_amt:,}억")
    m3.metric("만기전 발행잔액", f"{outstanding:,}억",
              help="아직 만기 전인 회차 발행액 합계 (미상환 추정 · 전환/조기상환 미반영). 추가 발행 여력 참고용.")
    m4.metric("직전 발행 후", f"{elapsed}개월" if elapsed is not None else "-",
              help=f"마지막 발행 {last_issue}")
    m5.metric("18개월 내 만기", f"{len(upcoming)}건", help="차환/재발행 영업 타이밍")

    gaps = [_months_between(issues[i-1], issues[i]) for i in range(1, len(issues))]
    if gaps:
        avg_gap = round(sum(gaps) / len(gaps))
        st.caption(f"과거 발행 간격: {' · '.join(str(g)+'개월' for g in gaps)}  (평균 {avg_gap}개월)  "
                   f"→ 직전 발행 후 {elapsed}개월 경과")

    if upcoming:
        lines = [f"- **{r['회차']}회** 만기 {r['만기일']} · 발행액 {r['발행액(억)']}억" for r in upcoming]
        st.success("**🎯 영업 타이밍 신호 — 만기 임박 회차** (차환·재발행 수요 가능)\n\n" + "\n".join(lines))

    # ---------- 타임라인 ----------
    try:
        import altair as alt
        tdf = pd.DataFrame([{
            "회차": f"{r['회차']}회", "발행일": pd.Timestamp(r["발행일"]),
            "만기일": pd.Timestamp(r["만기일"]) if r["만기일"] else pd.Timestamp(r["발행일"]),
            "발행액": r["발행액(억)"] or 0,
        } for r in recs])
        base = alt.Chart(tdf).mark_bar(height=16, cornerRadius=3, color="#1F3A5F").encode(
            y=alt.Y("회차:N", sort=list(tdf["회차"]), title=None),
            x=alt.X("발행일:T", title=None), x2="만기일:T",
            tooltip=["회차", "발행일", "만기일", "발행액"])
        rule = alt.Chart(pd.DataFrame({"오늘": [pd.Timestamp(today)]})).mark_rule(
            color="#eb6834", strokeDash=[4, 3]).encode(x="오늘:T")
        st.markdown("##### 회차별 일정 (발행 → 만기, 주황선=오늘)")
        st.altair_chart(base + rule, width="stretch")
    except Exception:
        pass

    # ---------- 회차별 상세 표 ----------
    st.markdown("##### 회차별 상세")
    show = pd.DataFrame(recs).drop(columns=["_rcept"])
    show["원문"] = [DART_VIEWER + (r["_rcept"] or "") if r["_rcept"] else None for r in recs]
    # 만기전 발행잔액 등은 부정확할 수 있어, 최신 정기보고서(사업·반기·분기) 원문을 맨 뒤 열에 제공
    pr_url = latest_periodic_report_url(code)
    show["최신 정기보고서"] = pr_url
    for dcol in ["발행일", "만기일"]:
        show[dcol] = show[dcol].map(lambda d: d.strftime("%Y-%m-%d") if d else "-")
    show_table(show, f"발행동향_{name}_{kind}", f"{key_prefix}_dl",
               link_cols=("원문", "최신 정기보고서"))
    st.caption("※ '만기전 발행잔액'은 전환·조기상환 미반영 추정치입니다. 정확한 잔액은 맨 뒤 '최신 정기보고서' "
               "원문(사업·반기·분기)에서 확인하세요.")

    # ---------- 2) 기 발행 참여기관 정보 (원문 AI 분석) ----------
    st.divider()
    st.markdown("#### 2) 기 발행 참여기관 정보")
    uw_key = f"{key_prefix}_uw"
    opts = {f"{r['회차']}회 · {r['발행일']}": r for r in recs if r["_rcept"]}
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 선택한 회차의 원문에서 참여(배정) 기관을 자동으로 뽑아줍니다.")
    elif not opts:
        st.caption("원문 링크가 있는 회차가 없어 참여기관을 분석할 수 없습니다.")
    else:
        pick = st.selectbox("회차 선택", list(opts.keys()), key=f"{key_prefix}_pick")
        if st.button("이 회차 참여기관 분석", key=f"{key_prefix}_uw_btn"):
            r = opts[pick]
            try:
                with st.spinner("원문을 가져와 참여기관을 분석하는 중..."):
                    full = fetch_dart_document(api_key, r["_rcept"])
                    res = extract_underwriters_ai(anthropic_key, ai_model, full, name, f"{r['회차']}회")
                st.session_state[uw_key] = (pick, res)
            except DartError as e:
                st.error(str(e))
        if uw_key in st.session_state:
            lbl, res = st.session_state[uw_key]
            lst = res.get("인수기관") if isinstance(res, dict) else None
            st.markdown(f"**{lbl}** 기 발행 참여기관")
            if lst:
                show_table(pd.DataFrame(lst), f"참여기관_{name}", f"{key_prefix}_uw_dl")
            else:
                st.info("원문에서 참여기관 명단을 찾지 못했습니다. (사모 배정표가 원문에 없을 수 있어요)")
            st.caption("※ AI 추출값입니다. 신탁은행·증권사 명의 뒤의 실제 운용사까지는 다를 수 있으니 원문과 대조하세요.")

    # ---------- 재무(연속적자) 데이터: 한 번만 받아 3)·결론 공용 ----------
    ann_year = today.year - 1
    fin_cache_key = f"{key_prefix}_findata"
    _cached = st.session_state.get(fin_cache_key)
    if not _cached or _cached[0] != code:
        try:
            fin = fetch_company_financials(api_key, code, ann_year, today.year)
        except Exception:
            fin = {}
        st.session_state[fin_cache_key] = (code, fin)
    else:
        fin = _cached[1]

    # ---------- 3) 연속적자 등 재무상태 제외 (선택 기업 최근 3개년 영업이익) ----------
    st.divider()
    st.markdown("#### 3) 위험 재무상태 분석")
    annual_ps = [f"{ann_year-2}년", f"{ann_year-1}년", f"{ann_year}년"]
    op_vals = [(fin.get(p) or {}).get("영업이익") for p in annual_ps]
    op_df = pd.DataFrame([{"사업연도": p, "영업이익(억)": v} for p, v in zip(annual_ps, op_vals)])
    show_table(op_df, f"재무상태_{name}", f"{key_prefix}_fin_dl")
    nums = [v for v in op_vals if v is not None]
    if len(nums) == 3 and all(v < 0 for v in nums):
        st.warning("⚠️ 최근 3개 사업연도 **연속 영업적자** → '연속적자 제외' 필터 적용 시 후보에서 **제외**됩니다. "
                   "(바이오·로봇 등 특정업종은 별도 판단 필요)")
    elif len(nums) == 3:
        st.caption("최근 3개 사업연도 연속 영업적자 아님 → '연속적자 제외' 필터와 무관합니다.")
    else:
        st.caption("영업이익 자료가 부족해 연속적자 여부를 판정하기 어렵습니다. (미제출·금융업 등)")

    # ---------- 결론 (AI 딜소싱 리포트) ----------
    st.divider()
    st.markdown("#### 결론")
    gaps2 = [_months_between(issues[i - 1], issues[i]) for i in range(1, len(issues))]
    avg_gap2 = round(sum(gaps2) / len(gaps2)) if gaps2 else None
    near6 = [r for r in mats if r["만기일"] <= today + dt.timedelta(days=183)]
    rep_key = f"{key_prefix}_report"
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 위 수치(발행이력·재무)를 종합해 딜소싱 판단 결론을 생성합니다.")
    else:
        if st.button("결론(딜소싱 판단) 생성", type="primary", key=f"{key_prefix}_report_btn"):
            try:
                with st.spinner("최신 재무를 받아 종합 판단 중..."):
                    la = f"{ann_year}년"
                    lp = f"{today.year}년 상반기" if f"{today.year}년 상반기" in fin else la

                    def _g(period, m):
                        return (fin.get(period) or {}).get(m)
                    fin_lines = (
                        f"- 현금성자산({lp}): {_g(lp, '현금성자산')}\n"
                        f"- 직전 영업이익({la}): {_g(la, '영업이익')}\n"
                        f"- 이자비용({la}): {_g(la, '이자비용')}\n"
                        f"- 매출액({la}): {_g(la, '매출액')}\n"
                        f"- 부채총계/자본총계({lp}): {_g(lp, '부채총계')} / {_g(lp, '자본총계')}"
                    )
                    issue_lines = (
                        f"- 총 발행 회차: {len(recs)}회, 누적발행액: {total_amt}억\n"
                        f"- 만기전 발행잔액(미상환 추정): {outstanding}억\n"
                        f"- 직전 발행 후 경과: {elapsed}개월, 과거 평균 발행주기: {avg_gap2}개월\n"
                        f"- 6개월 내 만기: {len(near6)}건, 18개월 내 만기: {len(upcoming)}건"
                    )
                    memo = company_report_ai(anthropic_key, ai_model, name, kind, issue_lines, fin_lines)
                st.session_state[rep_key] = memo
            except DartError as e:
                st.error(str(e))
        if rep_key in st.session_state:
            st.success(st.session_state[rep_key])
            st.caption("※ 투자권유가 아니라 영업(딜소싱) 참고용입니다. 미상환 잔액은 전환·조기상환 미반영 추정치이니 원문과 대조하세요.")


def tab_company(corp_df):
    st.header("📄 발행내역 확인 (기업별)")
    st.caption("특정 기업명을 입력하면 그 기업의 CB/BW 발행 누적현황·회차별 일정·상세·배정기관을 보여주고, "
               "아래 'AI 딜소싱 리포트'로 한 줄 결론까지 뽑습니다. "
               "(여러 후보를 한 번에 비교·추천받으려면 'Ⅲ. Analysis' 탭을 이용하세요.)")

    c1, c2 = st.columns([3, 1])
    name = c1.text_input("회사명", "", key="co_name")
    kind = c2.radio("유형", ["CB", "BW"], key="co_kind")

    if st.button("조회", type="primary", key="co_btn"):
        row = resolve_corp(name, corp_df)
        if row is None:
            st.warning("회사를 찾지 못했습니다. 이름을 정확히 입력해 보세요.")
            st.session_state.pop("co_data", None)
            return
        es = dt.date.today().strftime("%Y%m%d")
        with st.spinner("회차별 발행내역을 모으는 중..."):
            recs = build_company_bonds(api_key, row["corp_code"], kind, "20120101", es)
        st.session_state["co_data"] = {"name": row["corp_name"], "code": row["corp_code"],
                                       "kind": kind, "recs": recs}
        st.session_state.pop("co_uw", None)
        st.session_state.pop("co_report", None)

    data = st.session_state.get("co_data")
    if not data:
        return
    render_company_detail(data["name"], data["code"], data["kind"], data["recs"], key_prefix="co")


# ==================================================================
#  탭 9) CB 차환수요 발굴 (만기 임박 → 재발행 영업 타깃을 AI가 추천)
# ==================================================================
def demand_ai_opinion(anthropic_key, model, summary_text, n_within, within_label):
    """만기 임박 CB 후보 리스트를 받아 영업 우선순위 의견을 생성."""
    try:
        import anthropic
    except ImportError:
        raise DartError("anthropic 라이브러리가 없습니다. 'python -m pip install anthropic' 후 다시 시도하세요.")
    prompt = f"""당신은 CB(전환사채) 발행 주선 영업을 하는 증권/투자사의 심사역입니다.
아래는 '{within_label} 내 CB 만기가 도래해 차환(재발행) 수요가 예상되는' 기업 {n_within}곳의 데이터입니다.
제공된 숫자만 근거로, CB 발행 영업 관점에서 우선순위를 매기고 이유를 쓰세요. 숫자를 지어내지 마세요.

고려 기준: ① 만기가 임박할수록(시급) ② 도래 금액이 클수록(딜 규모) ③ 과거 발행횟수가 많을수록(재발행 성향) ④ 시가총액(규모·신뢰도)
⑤ 재무상 차환 필요성: 현금성자산이 도래액보다 적을수록(자체 상환 어려움=차환 수요↑), 영업이익이 적자이거나 이자비용 부담이 클수록(현금창출력 약함=외부조달 의존↑). 단, 재무가 과도하게 부실하면 발행 성사 리스크도 언급.

[후보 기업 데이터]
{summary_text}

다음 형식의 한국어 메모로:
1) 최우선 영업 타깃 Top 5 (회사명 + 한 줄 이유)
2) 그 외 주목 기업 (간단히)
3) 접근 시 유의점 (예: 만기 전 조기상환 가능성, 업황 등 — 일반론)
마지막에 '투자 권유가 아니라 영업 참고용'임을 한 줄로 명시."""
    try:
        msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
            model=model, max_tokens=1800, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        raise DartError(f"AI 호출 실패: {e}")
    return "".join(getattr(b, "text", "") for b in msg.content)


DEMAND_FIN_METRICS = ["매출액", "영업이익", "현금성자산", "부채총계", "자본총계", "이자비용"]


def _fs_pick(items, sj_set, match_names, match_ids):
    """fetch_full_fs 결과에서 특정 계정의 (당기, 전기, 전전기) 금액 문자열을 뽑는다."""
    for it in items:
        if it.get("sj_div") not in sj_set:
            continue
        nm = (it.get("account_nm") or "").replace(" ", "")
        aid = it.get("account_id") or ""
        if (aid in match_ids) or any(mn in nm for mn in match_names):
            return (it.get("thstrm_amount"), it.get("frmtrm_amount"), it.get("bfefrmtrm_amount"))
    return (None, None, None)


def _to_eok(v):
    n = _mznum(v)
    return round(n / 1e8) if n is not None else None


_REV_NAMES = ["매출액", "수익(매출액)", "영업수익"]
_REV_IDS = ["ifrs-full_Revenue", "ifrs_Revenue"]
_OP_NAMES = ["영업이익", "영업이익(손실)"]
_OP_IDS = ["dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"]
_CASH_NAMES = ["현금및현금성자산"]
_CASH_IDS = ["ifrs-full_CashAndCashEquivalents"]
_LIAB_NAMES = ["부채총계"]
_LIAB_IDS = ["ifrs-full_Liabilities"]
_EQ_NAMES = ["자본총계"]
_EQ_IDS = ["ifrs-full_Equity"]
# 이자비용: 요약 손익계산서에 '이자비용'이 없으면 '금융비용(FinanceCosts)'을 대용으로 사용
_INT_NAMES = ["이자비용", "금융비용"]
_INT_IDS = ["ifrs-full_FinanceCosts", "dart_InterestExpense", "dart_FinanceCosts"]


def _fs_five(items, idx):
    """한 재무제표(items)에서 지표들을 idx(0=당기,1=전기,2=전전기) 기준으로 뽑아 억원 dict."""
    rev = _fs_pick(items, {"IS", "CIS"}, _REV_NAMES, _REV_IDS)
    op = _fs_pick(items, {"IS", "CIS"}, _OP_NAMES, _OP_IDS)
    cash = _fs_pick(items, {"BS"}, _CASH_NAMES, _CASH_IDS)
    liab = _fs_pick(items, {"BS"}, _LIAB_NAMES, _LIAB_IDS)
    eq = _fs_pick(items, {"BS"}, _EQ_NAMES, _EQ_IDS)
    intr = _fs_pick(items, {"IS", "CIS"}, _INT_NAMES, _INT_IDS)
    return {
        "매출액": _to_eok(rev[idx]), "영업이익": _to_eok(op[idx]),
        "현금성자산": _to_eok(cash[idx]), "부채총계": _to_eok(liab[idx]),
        "자본총계": _to_eok(eq[idx]), "이자비용": _to_eok(intr[idx]),
    }


@st.cache_data(show_spinner=False)
def fetch_company_financials(api_key_arg, corp_code, ann_year, cur_year):
    """후보기업 연도별 재무(억원): {기간라벨: {5개 지표}}.
    - 사업보고서(ann_year) 1건으로 ann_year/-1/-2 3개년
    - 당해(cur_year) 반기보고서로 '상반기' 1개
    둘 다 연결(CFS) 우선, 없으면 별도(OFS)."""
    out = {}
    # 1) 연간 3개년
    items = []
    for fs in ("CFS", "OFS"):
        try:
            items = fetch_full_fs(api_key_arg, corp_code, ann_year, "11011", fs)
        except DartError:
            items = []
        if items:
            break
    if items:
        for i, y in enumerate([ann_year, ann_year - 1, ann_year - 2]):
            out[f"{y}년"] = _fs_five(items, i)
    # 2) 당해 반기
    items2 = []
    for fs in ("CFS", "OFS"):
        try:
            items2 = fetch_full_fs(api_key_arg, corp_code, cur_year, "11012", fs)
        except DartError:
            items2 = []
        if items2:
            break
    if items2:
        out[f"{cur_year}년 상반기"] = _fs_five(items2, 0)
    return out


def tab_demand(corp_df):
    st.header("🎯 Ⅱ. Look-up - 2. 발행후보 기업 - look-up")
    st.caption("【Flow 2단계】 발행가능성 있는 기업을 **구체적으로** 찾습니다. 과거 CB/BW 발행 이력이 있는 기업 중, "
               "① 시가총액 ② 영업이익 규모 ③ 현금성자산 ④ 이자비용 조건을 직접 걸어 후보 리스트를 추립니다. "
               "추린 기업은 → 'Ⅲ. Analysis'에서 발행여부·조건·시기를 판단하세요.")

    st.subheader("1) 일반적 발행 검토")
    c0, c1, c2, c3 = st.columns([1.2, 2, 2, 2])
    kind = c0.radio("발행 유형", ["CB", "BW"], horizontal=True, key="dm_kind",
                    help="CB=전환사채 / BW=신주인수권부사채. 선택한 유형의 발행 이력을 기준으로 후보를 찾습니다.")
    scan = c1.selectbox("스캔 대상 (발행 시점)",
                        ["최근 3년 발행분", "최근 5년 발행분", "최근 2년 발행분", "연도 범위 지정"],
                        help="곧 만기인 CB/BW는 보통 3~5년 전에 발행됐습니다. DB 적재분에서 즉시 조회합니다. "
                             "'연도 범위 지정'으로 특정 연도(예: 2018~2021)에 발행한 기업만 볼 수도 있습니다.")
    within = c2.selectbox("만기 도래 기간", ["앞으로 6개월", "앞으로 12개월", "앞으로 18개월", "앞으로 24개월"])
    mincap = c3.number_input("시가총액 최소 (억, 0=전체)", value=0.0, step=500.0, format="%.0f")

    _today = dt.date.today()
    if scan == "연도 범위 지정":
        _yrs = list(range(2017, _today.year + 1))
        sc1, sc2 = st.columns(2)
        sy_from = sc1.selectbox("발행 시작 연도", _yrs, index=max(0, len(_yrs) - 4), key="dm_yfrom")
        sy_to = sc2.selectbox("발행 종료 연도", _yrs, index=len(_yrs) - 1, key="dm_yto")
        if sy_from > sy_to:
            sy_from, sy_to = sy_to, sy_from
        scan_bs = f"{sy_from}0101"
        scan_es = min(_today, dt.date(sy_to, 12, 31)).strftime("%Y%m%d")
    else:
        scan_years = {"최근 2년 발행분": 2, "최근 3년 발행분": 3, "최근 5년 발행분": 5}[scan]
        scan_bs = (_today - dt.timedelta(days=365 * scan_years)).strftime("%Y%m%d")
        scan_es = _today.strftime("%Y%m%d")

    add_fin = st.checkbox("후보기업 연도별 재무 추가 (매출·영업이익·현금성자산·부채·자본 / 최신 보고서 기준)",
                          value=True, key="dm_fin")

    within_days = {"앞으로 6개월": 183, "앞으로 12개월": 365, "앞으로 18개월": 548, "앞으로 24개월": 730}[within]
    st.caption("※ '🗄️ 데이터 관리(DB)'에서 백필한 범위 안에서 조회됩니다. 재무 추가는 후보 수에 따라 30초~2분 걸릴 수 있습니다.")

    if st.button("수요기업 발굴", type="primary", key="dm_btn"):
        bs, es = scan_bs, scan_es
        pbar = st.progress(0.0, "준비 중...")
        try:
            df = build_screener_df(kind, bs, es, progress=lambda f, t: pbar.progress(f, t))
            if not df.empty:
                pbar.progress(1.0, "시가총액 계산 중...")
                df = _attach_market_cap(df, corp_df, kind)
        except DartError as e:
            pbar.empty()
            st.error(str(e))
            return
        pbar.empty()
        st.session_state["dm_df"] = df
        st.session_state["dm_cfg"] = (within_days, within, mincap, add_fin, kind)
        st.session_state.pop("dm_ai", None)
        st.session_state.pop("dm_cdf", None)        # 재계산 유도

    if "dm_df" not in st.session_state:
        return
    df = st.session_state["dm_df"]
    _cfg = st.session_state["dm_cfg"]
    within_days, within_label, mincap, add_fin = _cfg[:4]
    kind = _cfg[4] if len(_cfg) > 4 else "CB"
    price_col = "전환가액(원)" if kind == "CB" else "행사가액(원)"
    if df is None or df.empty:
        st.info("스캔 결과가 없습니다. '🗄️ 데이터 관리(DB)' 탭에서 먼저 백필했는지 확인하거나, 스캔 범위를 넓혀보세요.")
        return

    # ---------- 후보 집계 + (선택) 연도별 재무 — 한 번만 계산해 세션 저장 ----------
    if "dm_cdf" not in st.session_state:
        today = dt.date.today()
        horizon = today + dt.timedelta(days=within_days)
        cap_col = "시가총액(억)"
        cand = []
        for name, grp in df.groupby("종목명"):
            total_cnt = len(grp)
            up = grp[grp["만기일"].notna()].copy()
            up["_mat"] = pd.to_datetime(up["만기일"], errors="coerce").dt.date
            up = up[(up["_mat"] >= today) & (up["_mat"] <= horizon)]
            if up.empty:
                continue
            cap = None
            if cap_col in grp.columns:
                vals = pd.to_numeric(grp[cap_col], errors="coerce").dropna()
                cap = int(vals.iloc[0]) if len(vals) else None
            if mincap and (cap is None or cap < mincap):
                continue
            amt = pd.to_numeric(up["사채총액(억)"], errors="coerce").dropna().sum()
            corp_code = str(grp["_corp_code"].iloc[0]) if "_corp_code" in grp.columns else None
            # 미상환 추정 = 스캔범위 발행분 중 '아직 만기 전'인 CB 발행액 합계 (전환·조기상환 미반영)
            g2 = grp.copy()
            g2["_mat"] = pd.to_datetime(g2["만기일"], errors="coerce").dt.date
            alive = g2[g2["_mat"].notna() & (g2["_mat"] >= today)]
            outstanding = pd.to_numeric(alive["사채총액(억)"], errors="coerce").dropna().sum()
            # 가장 최근 CB의 발행조건(표시용)
            latest = grp.sort_values("접수일", ascending=False).iloc[0] if "접수일" in grp.columns else grp.iloc[0]
            cand.append({
                "종목명": name, "_corp_code": corp_code,
                # 표시: 발행조건(전체 screen과 동일 성격) — 가장 최근 CB 기준
                "최근 공시일": latest.get("접수일"),
                "표면이자율(%)": latest.get("표면이자율(%)"),
                "만기이자율(%)": latest.get("만기이자율(%)"),
                "만기(년)": latest.get("만기(년)"),
                price_col: latest.get(price_col),
                "리픽싱하한(%)": latest.get("리픽싱하한(%)"),
                "희석비율(%)": latest.get("희석비율(%)"),
                "사채총액(억)": latest.get("사채총액(억)"),
                "과거 총 발행": total_cnt,
                "시가총액(억)": cap,
                # 내부용(Analysis 탭에서 사용 · look-up 표에는 숨김)
                "가장 가까운 만기": min(up["_mat"]).strftime("%Y-%m-%d"),
                "도래 예정액(억)": int(amt) if amt else None,
                "만기전 발행잔액(억)": int(outstanding) if outstanding else None,
                "도래 회차수": len(up),
            })
        cdf = pd.DataFrame(cand).sort_values("가장 가까운 만기").reset_index(drop=True) if cand else pd.DataFrame()

        # 연도별 재무 붙이기
        fin_cols = []
        if add_fin and not cdf.empty:
            ann_year = dt.date.today().year - 1
            cur_year = dt.date.today().year
            periods = [f"{ann_year-2}년", f"{ann_year-1}년", f"{ann_year}년", f"{cur_year}년 상반기"]
            fin_cols = [f"{p} {m}" for p in periods for m in DEMAND_FIN_METRICS]
            pbar = st.progress(0.0, "후보기업 최신 보고서에서 재무 추출 중...")
            tot_n = len(cdf)
            fin_rows = []
            for i, r in cdf.iterrows():
                cc = r["_corp_code"]
                fin = fetch_company_financials(api_key, cc, ann_year, cur_year) if cc else {}
                row = {}
                for p in periods:
                    pdata = fin.get(p, {})
                    for m in DEMAND_FIN_METRICS:
                        row[f"{p} {m}"] = pdata.get(m)
                fin_rows.append(row)
                pbar.progress((i + 1) / tot_n, f"재무 추출 중... {i+1}/{tot_n}개사")
            pbar.empty()
            cdf = pd.concat([cdf, pd.DataFrame(fin_rows, index=cdf.index)], axis=1)

        st.session_state["dm_cdf"] = cdf
        st.session_state["dm_fincols"] = fin_cols
        st.session_state["dm_periods"] = periods if add_fin else []

    cdf = st.session_state["dm_cdf"]
    fin_cols = st.session_state.get("dm_fincols", [])
    periods = st.session_state.get("dm_periods", [])
    if cdf is None or cdf.empty:
        st.info("해당 조건으로 만기 임박 CB 기업을 찾지 못했습니다. 기간·범위를 넓혀보세요.")
        return

    # ---------- 재무 조건으로 후보 좁히기 ----------
    fcdf = cdf
    if fin_cols and periods:
        annuals = [p for p in periods if "상반기" not in p]
        last_annual = annuals[-1] if annuals else periods[-1]

        def _ncol(df_, name):
            if name in df_.columns:
                return pd.to_numeric(df_[name], errors="coerce")
            return pd.Series([float("nan")] * len(df_), index=df_.index)

        with st.expander("🔍 재무 조건으로 후보 좁히기 (선택)", expanded=False):
            fmode = st.radio("필터 방식", ["직접 지정", "딜소싱 후보 필터링"],
                             horizontal=True, key="dm_fmode")

            if fmode == "딜소싱 후보 필터링":
                st.caption(f"기준 연도: **{last_annual}** (직전 사업연도). "
                           "재무가 약해 외부조달(발행) 가능성이 높은 기업을 자동으로 추립니다. (수치는 조정 가능)")
                v1, v2, v3, v4 = st.columns(4)
                cap_min = v1.number_input("① 시가총액 ≥ (억)", value=1500.0, step=100.0, format="%.0f", key="dm_vp_cap")
                cash_lim = v2.number_input("② 현금성자산 ≤ (억)", value=100.0, step=50.0, format="%.0f", key="dm_vp_cash")
                t1 = v3.number_input("③ 현금성자산 + 직전영업이익 < (억)", value=200.0, step=50.0, format="%.0f", key="dm_vp_t1")
                t2 = v4.number_input("④ 현금성자산 + 직전영업이익 − 이자비용 < (억)", value=300.0, step=50.0, format="%.0f", key="dm_vp_t2")
                st.caption("판정: ① 시가총액 기준 이상 · 최근 3개년 연속 영업적자 **제외** · "
                           "그리고 아래 중 하나 이상 충족 — "
                           "② 현금성자산 ≤ 기준  또는  ③ (현금성자산 > ② & 현금성자산+직전영업이익 < ③)  또는  "
                           "④ (현금성자산 > ② & 현금성자산+직전영업이익−이자비용 < ④)")

                cash = _ncol(fcdf, f"{last_annual} 현금성자산")
                opp = _ncol(fcdf, f"{last_annual} 영업이익")
                intr = _ncol(fcdf, f"{last_annual} 이자비용")
                capv = _ncol(fcdf, "시가총액(억)")

                mask = capv.notna() & (capv >= cap_min)                      # ①
                # ② 3개년 연속적자 제외 (연간 3개 값이 모두 있고 모두 <0 이면 제외)
                ann_cols = [f"{p} 영업이익" for p in annuals[-3:] if f"{p} 영업이익" in fcdf.columns]
                if len(ann_cols) == 3:
                    allneg = pd.Series(True, index=fcdf.index)
                    for c in ann_cols:
                        vv = pd.to_numeric(fcdf[c], errors="coerce")
                        allneg &= vv.notna() & (vv < 0)
                    mask &= ~allneg
                # ②③④ 유동성 부족 (아래 중 하나라도)
                liq = cash.notna() & (cash <= cash_lim)                                         # ②
                liq |= cash.notna() & (cash > cash_lim) & opp.notna() & ((cash + opp) < t1)      # ③ 미만
                liq |= (cash.notna() & (cash > cash_lim) & opp.notna() & intr.notna()
                        & ((cash + opp - intr) < t2))                                            # ④ 미만
                mask &= liq
                fcdf = fcdf[mask]
                st.caption(f"딜소싱 후보: **{len(fcdf)}개사** / 전체 {len(cdf)}개사")

            else:
                base_p = st.selectbox("기준 기간", periods, index=len(periods) - 1, key="dm_fp",
                                      help="현금성자산·이자비용·영업이익 조건을 이 기간 값으로 판단합니다.")
                fc1, fc2 = st.columns(2)
                cash_max = fc1.number_input("현금성자산 최대 (억, 0=미적용)", value=0.0, step=50.0,
                                            format="%.0f", key="dm_cash", help="이 값 이하인 기업만")
                int_min = fc2.number_input("이자비용 최소 (억, 0=미적용)", value=0.0, step=10.0,
                                           format="%.0f", key="dm_int", help="이 값 이상인 기업만")

                st.markdown("**영업이익 범위 (기준 기간, 단위: 억원)**")
                oc0, oc1, oc2 = st.columns([1, 1, 1])
                op_use = oc0.checkbox("범위 적용", key="dm_opuse",
                                      help="영업이익이 아래 범위 안인 기업만. 적자 구간은 음수로 입력(예: -200 ~ 0). "
                                           "최대가 최소 이하면 상한 없음으로 처리(예: 최소 200·최대 0 → 200억 이상).")
                op_min = oc1.number_input("최소(억)", value=0.0, step=50.0, format="%.0f",
                                          key="dm_opmin", disabled=not op_use)
                op_max = oc2.number_input("최대(억)", value=0.0, step=50.0, format="%.0f",
                                          key="dm_opmax", disabled=not op_use)
                loss3_excl = st.checkbox("추가: 최근 3개년 연속 영업적자 제외", key="dm_loss3")

                mask = pd.Series(True, index=fcdf.index)
                cC = f"{base_p} 현금성자산"
                if cash_max and cC in fcdf.columns:
                    v = pd.to_numeric(fcdf[cC], errors="coerce")
                    mask &= v.notna() & (v <= cash_max)
                cI = f"{base_p} 이자비용"
                if int_min and cI in fcdf.columns:
                    v = pd.to_numeric(fcdf[cI], errors="coerce")
                    mask &= v.notna() & (v >= int_min)
                cO = f"{base_p} 영업이익"
                if op_use and cO in fcdf.columns:
                    v = pd.to_numeric(fcdf[cO], errors="coerce")
                    mask &= v.notna() & (v >= op_min)
                    if op_max > op_min:                       # 최대 ≤ 최소면 상한 없음
                        mask &= v <= op_max
                if loss3_excl:
                    ann_cols = [f"{p} 영업이익" for p in annuals[-3:] if f"{p} 영업이익" in fcdf.columns]
                    if len(ann_cols) == 3:
                        allneg = pd.Series(True, index=fcdf.index)
                        for c in ann_cols:
                            v = pd.to_numeric(fcdf[c], errors="coerce")
                            allneg &= v.notna() & (v < 0)
                        mask &= ~allneg          # 3개년 모두 적자인 기업은 제외
                fcdf = fcdf[mask]
                st.caption(f"필터 적용: **{len(fcdf)}개사** / 전체 {len(cdf)}개사")

    st.divider()
    st.subheader(f"발행 후보 기업  ({len(fcdf)}개사)")
    m1, m2 = st.columns(2)
    m1.metric("후보 기업 수", f"{len(fcdf)}개사")
    tot = pd.to_numeric(fcdf["도래 예정액(억)"], errors="coerce").dropna().sum() if "도래 예정액(억)" in fcdf.columns else 0
    m2.metric("도래 예정액 합계", f"{int(tot):,}억")

    # 표시 컬럼: 발행조건(전체 screen 성격) + 연도별 재무. 만기/도래액 등 집계치는 숨김(Analysis 탭에서 사용)
    hide = ["_corp_code", "가장 가까운 만기", "도래 예정액(억)", "만기전 발행잔액(억)", "도래 회차수"]
    cond_cols = ["종목명", "최근 공시일", "표면이자율(%)", "만기이자율(%)", "만기(년)",
                 price_col, "리픽싱하한(%)", "희석비율(%)", "사채총액(억)", "과거 총 발행", "시가총액(억)"]
    ordered = [c for c in cond_cols if c in fcdf.columns] + [c for c in fin_cols if c in fcdf.columns]
    show = fcdf[[c for c in ordered if c not in hide]] if ordered else fcdf.drop(columns=[c for c in hide if c in fcdf.columns])
    st.caption(f"발행조건은 각 기업의 **가장 최근 {kind}** 기준입니다. (만기·도래액 등 집계치는 'Ⅲ. Analysis' 탭에서 확인)"
               + ("  · 재무 단위: 억원, 연결 우선(없으면 별도), 빈칸은 미제출/금융업." if fin_cols else ""))
    show_table(show, f"발행후보_{dt.date.today():%Y%m%d}", "dm_dl")
    st.caption("→ 이 후보 리스트는 'Ⅲ. Analysis' 탭으로 자동 연결됩니다. 거기서 유력 딜소싱 후보를 순위·추천받으세요.")

    # ---------- 2) 차환발행 검토 ----------
    st.divider()
    st.subheader("2) 차환발행 검토")
    st.caption("위 **1) 일반적 발행 검토**로 추려진 기업을 대상으로, 직전 발행의 **만기까지 잔존 개월수**와 "
               "**만기 전 잔존 금액**을 기준으로 차환(만기 상환자금 재조달) 필요성을 봅니다. "
               "만기가 가까울수록·잔존 금액이 클수록 차환 수요가 큽니다.")
    rc1, rc2 = st.columns(2)
    mos_max = rc1.number_input("만기까지 잔존 개월수 ≤ (개월)", value=12.0, step=3.0, format="%.0f",
                               key="dm_ref_mos", help="직전 발행분 중 가장 가까운 만기까지 남은 개월수")
    bal_min = rc2.number_input("만기 전 잔존 금액 ≥ (억, 0=미적용)", value=0.0, step=50.0, format="%.0f",
                               key="dm_ref_bal", help="만기 전 미상환(발행잔액). 클수록 상환·차환 부담이 큼")

    ref_today = dt.date.today()
    rrows = []
    for _, r in fcdf.iterrows():
        d = _parse_date(r.get("가장 가까운 만기"))
        mos = round((d - ref_today).days / 30.44, 1) if d else None
        bal = _safe_num(r.get("만기전 발행잔액(억)"))
        due = _safe_num(r.get("도래 예정액(억)"))
        cap = _safe_num(r.get("시가총액(억)"))
        ratio = round(bal / cap * 100, 1) if (bal and cap) else None
        if mos is not None and mos <= 6 and (ratio is not None and ratio >= 10):
            need = "높음"
        elif mos is not None and mos <= 12:
            need = "중간"
        else:
            need = "낮음"
        rrows.append({
            "종목명": r.get("종목명"), "가장 가까운 만기": r.get("가장 가까운 만기"),
            "잔존 개월수": mos, "만기전 잔존금액(억)": bal, "도래 예정액(억)": due,
            "도래 회차수": r.get("도래 회차수"), "최근 사채총액(억)": r.get("사채총액(억)"),
            "시가총액(억)": cap, "잔액/시총(%)": ratio, "차환 필요성": need,
        })
    refdf = pd.DataFrame(rrows)
    if not refdf.empty:
        m = pd.to_numeric(refdf["잔존 개월수"], errors="coerce")
        keep = m.notna() & (m <= mos_max)
        if bal_min:
            bb = pd.to_numeric(refdf["만기전 잔존금액(억)"], errors="coerce")
            keep &= bb.notna() & (bb >= bal_min)
        refdf = refdf[keep].sort_values(["잔존 개월수", "만기전 잔존금액(억)"],
                                        ascending=[True, False]).reset_index(drop=True)
    rm1, rm2 = st.columns(2)
    rm1.metric("차환 검토 대상", f"{len(refdf)}개사")
    rtot = pd.to_numeric(refdf["만기전 잔존금액(억)"], errors="coerce").dropna().sum() if not refdf.empty else 0
    rm2.metric("잔존 금액 합계", f"{int(rtot):,}억")
    if refdf.empty:
        st.info("해당 잔존 개월수·금액 조건에 맞는 차환 대상이 없습니다. 조건을 넓혀보세요.")
    else:
        st.caption("차환 필요성: 잔존 ≤6개월 & 잔액/시총 ≥10% → **높음**, 잔존 ≤12개월 → **중간**, 그 외 **낮음**. "
                   "조기상환(풋) 조항이 있으면 실제 차환 시점은 더 빨라질 수 있습니다.")
        show_table(refdf, f"차환검토_{dt.date.today():%Y%m%d}", "dm_ref_dl")

    # ---------- AI 영업 우선순위 ----------
    st.divider()
    st.subheader("🤖 AI 영업 우선순위 의견")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 위 후보를 영업 우선순위로 정리한 의견을 받을 수 있습니다.")
        return
    if st.button("AI 우선순위 의견 생성", key="dm_ai_btn"):
        top = fcdf.head(20)
        lp = periods[-1] if periods else None
        lines = []
        for _, r in top.iterrows():
            base = (f"- {r['종목명']}: 가까운 만기 {r['가장 가까운 만기']}, 도래액 {r['도래 예정액(억)']}억, "
                    f"도래 {r['도래 회차수']}회, 과거발행 {r['과거 총 발행']}회, 시총 {r['시가총액(억)']}억")
            if lp:
                def _g(m):
                    c = f"{lp} {m}"
                    return r[c] if c in r and pd.notna(r[c]) else "—"
                base += (f" | [{lp}] 영업이익 {_g('영업이익')}억, 현금성 {_g('현금성자산')}억, "
                         f"이자비용 {_g('이자비용')}억, 부채 {_g('부채총계')}억")
            lines.append(base)
        try:
            with st.spinner("AI 심사역이 영업 우선순위를 정리하는 중..."):
                memo = demand_ai_opinion(anthropic_key, ai_model, "\n".join(lines), len(fcdf), within_label)
            st.session_state["dm_ai"] = memo
        except DartError as e:
            st.error(str(e))
            return
    if "dm_ai" in st.session_state:
        st.markdown(st.session_state["dm_ai"])
        st.caption("※ 영업 참고용입니다. 만기 전 조기상환(풋)이 있으면 실제 차환 시점은 더 빠를 수 있으니 원문·동향 탭으로 확인하세요.")


# ==================================================================
#  탭) 기관 분석 (배정기관 추출·누적 → 최우선 마케팅 타깃)
# ==================================================================
def tab_institution(corp_df):
    st.header("🏦 기관 분석 (배정기관)")
    st.caption("과거 CB/BW 발행에 참여한 배정(인수)기관을 원문에서 AI로 추출·누적해 '자주·많이 참여한 기관'을 집계합니다. "
               "성공 사례에 참여한 기관을 최우선 영업 타깃으로 활용하세요. "
               "추출 결과는 DB에 저장되어, 한 번 돌린 공시는 다시 추출하지 않습니다.")

    c1, c2 = st.columns([1, 1])
    kind = c1.radio("유형", ["전체", "CB", "BW"], horizontal=True, key="uw_kind")
    period = c2.selectbox("기간", ["최근 1년", "최근 2년", "최근 3년", "최근 5년",
                                  "2026", "2025", "2024", "2023"], key="uw_period")
    today = dt.date.today()
    presets = {"최근 1년": 365, "최근 2년": 730, "최근 3년": 1095, "최근 5년": 1825}
    if period in presets:
        bs = (today - dt.timedelta(days=presets[period])).strftime("%Y%m%d")
        es = today.strftime("%Y%m%d")
    else:
        bs = f"{period}0101"
        es = min(today, dt.date(int(period), 12, 31)).strftime("%Y%m%d")

    done, total = db_uw_scanned_count(kind, bs, es)
    st.caption(f"이 범위 추출 진행: **{done:,} / {total:,}건** 완료"
               + ("  · DB를 먼저 백필해야 대상 공시가 생깁니다." if total == 0 else ""))

    # ---- 추출(갱신) ----
    with st.expander("🔎 배정기관 추출/갱신 (AI · 원문 파싱 · 비용 발생)", expanded=(done == 0 and total > 0)):
        st.caption("아직 추출 안 한 공시 중 최근 N건을 AI로 추출합니다(건당 AI 1회 호출=비용). "
                   "한 번 추출하면 DB에 저장되어 다시 안 받으니, 여러 번 나눠 눌러 쌓으면 됩니다.")
        npick = st.number_input("한 번에 추출할 건수", value=30, min_value=1, max_value=200, step=10, key="uw_n")
        if not anthropic_key:
            st.warning("배정기관 추출은 Anthropic API 키가 필요합니다. 사이드바에 키를 입력하세요.")
        elif st.button("배정기관 추출 실행", type="primary", key="uw_run"):
            pend = db_uw_pending(kind, bs, es, int(npick))
            if not pend:
                st.info("이 범위에서 추출할 새 공시가 없습니다. (이미 모두 추출 완료)")
            else:
                pbar = st.progress(0.0, "원문에서 배정기관 추출 중...")
                ok = 0
                for i, d in enumerate(pend, 1):
                    try:
                        txt = fetch_dart_document(api_key, d["rcept_no"])
                        insts = extract_underwriters_list(anthropic_key, ai_model, txt, d["corp_name"])
                    except Exception:
                        insts = []
                    db_uw_store(d["rcept_no"], d["kind"], d["corp_code"], d["corp_name"], d["rcept_dt"], insts)
                    if insts:
                        ok += 1
                    pbar.progress(i / len(pend), f"추출 {i}/{len(pend)}")
                pbar.empty()
                st.success(f"{len(pend)}건 처리 완료 (기관 확인 {ok}건). 아래 집계가 갱신됩니다.")

    # ---- 집계 ----
    agg = db_uw_aggregate(kind, bs, es)
    st.divider()
    st.subheader(f"기관별 참여 집계 — {kind} · {period}")
    if agg.empty:
        st.info("아직 집계할 배정기관 데이터가 없습니다. 위 '배정기관 추출 실행'을 먼저 돌려주세요.")
        return
    m1, m2 = st.columns(2)
    m1.metric("집계된 기관 수", f"{len(agg):,}개")
    m2.metric("최다 참여 기관", str(agg.iloc[0]["기관명"]), help=f"{int(agg.iloc[0]['참여건수'])}건 참여")
    show_table(agg, f"기관분석_{kind}_{dt.date.today():%Y%m%d}", "uw_agg_dl")

    # ---- 기관 드릴다운 ----
    st.divider()
    st.subheader("🔍 기관별 참여 딜 보기")
    pick = st.selectbox("기관 선택", agg["기관명"].tolist(), key="uw_pick")
    if pick:
        deals = db_uw_by_inst(pick, kind, bs, es)
        if deals.empty:
            st.info("해당 기관의 참여 딜이 없습니다.")
        else:
            st.caption(f"**{pick}** 참여 딜 {len(deals)}건")
            show_table(deals, f"기관_{pick}", "uw_deal_dl", link_cols=("원문",))
    st.caption("※ 배정기관은 공시 원문을 AI로 해석한 값입니다. 신탁/증권 명의 뒤의 실제 운용사는 다를 수 있으니 원문과 대조하세요.")


# ==================================================================
#  로컬 DB (SQLite) — CB/BW를 적재해 조회를 즉시로
# ==================================================================
import os as _os
import sqlite3

DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "dart.db")


def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def db_init():
    con = db_connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS bond (
      rcept_no TEXT PRIMARY KEY,
      kind TEXT, corp_code TEXT, corp_name TEXT,
      rcept_dt TEXT,              -- YYYYMMDD (접수일)
      issue_date TEXT,           -- YYYY-MM-DD (발행일)
      maturity TEXT,             -- YYYY-MM-DD (만기일)
      coupon REAL, ytm REAL, price REAL,
      conv_start TEXT, conv_end TEXT,
      refix_floor REAL, refix_pct REAL,
      dilution REAL, amount_eok REAL, shares REAL, round_no TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_bond_kind_dt ON bond(kind, rcept_dt);
    CREATE INDEX IF NOT EXISTS ix_bond_corp ON bond(kind, corp_code);
    CREATE INDEX IF NOT EXISTS ix_bond_mat ON bond(kind, maturity);
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    -- 배정(인수)기관: 발행 1건에서 추출한 참여기관들
    CREATE TABLE IF NOT EXISTS underwriter (
      rcept_no TEXT, kind TEXT, corp_code TEXT, corp_name TEXT, rcept_dt TEXT,
      inst TEXT, amount_eok REAL,
      PRIMARY KEY (rcept_no, inst)
    );
    CREATE INDEX IF NOT EXISTS ix_uw_inst ON underwriter(inst);
    CREATE INDEX IF NOT EXISTS ix_uw_dt ON underwriter(kind, rcept_dt);
    -- 이미 배정기관 추출을 끝낸 공시(기관 0건이어도 기록 → 재추출 방지)
    CREATE TABLE IF NOT EXISTS uw_done (rcept_no TEXT PRIMARY KEY, ts TEXT);
    """)
    con.commit()
    con.close()


def db_get_meta(key, default=None):
    con = db_connect()
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default


def db_set_meta(key, value):
    con = db_connect()
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    con.commit()
    con.close()


def db_counts():
    con = db_connect()
    out = {}
    for k in ("CB", "BW"):
        out[k] = con.execute("SELECT COUNT(*) c FROM bond WHERE kind=?", (k,)).fetchone()["c"]
    con.close()
    return out


# ---------- 배정(인수)기관 DB ----------
def db_uw_pending(kind, bgn, es, limit):
    """아직 배정기관 추출을 안 한 발행공시 목록(최근순). kind='전체'면 CB·BW 모두."""
    con = db_connect()
    q = ("SELECT rcept_no, kind, corp_code, corp_name, rcept_dt FROM bond "
         "WHERE rcept_dt BETWEEN ? AND ? AND rcept_no NOT IN (SELECT rcept_no FROM uw_done)")
    args = [bgn, es]
    if kind in ("CB", "BW"):
        q += " AND kind=?"
        args.append(kind)
    q += " ORDER BY rcept_dt DESC LIMIT ?"
    args.append(int(limit))
    rows = con.execute(q, args).fetchall()
    con.close()
    return [dict(r) for r in rows]


def db_uw_store(rcept_no, kind, corp_code, corp_name, rcept_dt, insts):
    """추출된 기관 리스트를 저장하고 uw_done에 기록. insts=[{'inst','amount_eok'}]."""
    con = db_connect()
    for it in insts:
        name = (it.get("inst") or "").strip()
        if not name:
            continue
        con.execute("INSERT OR REPLACE INTO underwriter"
                    "(rcept_no,kind,corp_code,corp_name,rcept_dt,inst,amount_eok) VALUES(?,?,?,?,?,?,?)",
                    (rcept_no, kind, corp_code, corp_name, rcept_dt, name, it.get("amount_eok")))
    con.execute("INSERT OR REPLACE INTO uw_done(rcept_no,ts) VALUES(?,?)",
                (rcept_no, dt.datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()


def db_uw_scanned_count(kind, bgn, es):
    """범위 내에서 추출 완료된 공시 수 / 전체 공시 수."""
    con = db_connect()
    base = "FROM bond WHERE rcept_dt BETWEEN ? AND ?"
    args = [bgn, es]
    if kind in ("CB", "BW"):
        base += " AND kind=?"
        args.append(kind)
    total = con.execute("SELECT COUNT(*) c " + base, args).fetchone()["c"]
    done = con.execute("SELECT COUNT(*) c " + base + " AND rcept_no IN (SELECT rcept_no FROM uw_done)",
                       args).fetchone()["c"]
    con.close()
    return done, total


def db_uw_aggregate(kind, bgn, es):
    """기관별 집계: 참여건수·참여기업수·누적배정액(억)·최근참여일."""
    con = db_connect()
    q = ('SELECT inst AS "기관명", COUNT(*) AS "참여건수", '
         'COUNT(DISTINCT corp_code) AS "참여기업수", '
         'SUM(COALESCE(amount_eok,0)) AS "누적배정액(억)", '
         'MAX(rcept_dt) AS "최근참여일" '
         "FROM underwriter WHERE rcept_dt BETWEEN ? AND ?")
    args = [bgn, es]
    if kind in ("CB", "BW"):
        q += " AND kind=?"
        args.append(kind)
    q += ' GROUP BY inst ORDER BY "참여건수" DESC, "누적배정액(억)" DESC'
    rows = con.execute(q, args).fetchall()
    con.close()
    return pd.DataFrame([dict(r) for r in rows])


def db_uw_by_inst(inst, kind, bgn, es):
    """특정 기관이 참여한 발행 건 목록."""
    con = db_connect()
    q = ('SELECT corp_name AS "기업", kind AS "유형", rcept_dt AS "접수일", '
         'amount_eok AS "배정액(억)", rcept_no '
         "FROM underwriter WHERE inst=? AND rcept_dt BETWEEN ? AND ?")
    args = [inst, bgn, es]
    if kind in ("CB", "BW"):
        q += " AND kind=?"
        args.append(kind)
    q += " ORDER BY rcept_dt DESC"
    rows = con.execute(q, args).fetchall()
    con.close()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        df["원문"] = DART_VIEWER + df["rcept_no"].astype(str)
        df = df.drop(columns=["rcept_no"])
    return df


def db_bond_count(kind):
    """특정 유형(CB/BW)이 DB에 몇 건 있는지. 0이면 아직 백필 전."""
    try:
        con = db_connect()
        n = con.execute("SELECT COUNT(*) c FROM bond WHERE kind=?", (kind,)).fetchone()["c"]
        con.close()
        return n
    except Exception:
        return 0


def _parse_bond_detail(r, kind):
    """DART 발행결정 1건(raw) → bond 테이블 한 행(dict)."""
    def g(keys):
        for k in keys:
            if k in r and r[k] not in (None, ""):
                return r[k]
        return None
    rcept = r.get("rcept_no")
    if not rcept:
        return None
    acpt = str(rcept)[:8]
    issue = _parse_date(g(["pymd", "bddd"])) or _parse_date(acpt)
    price = _mznum(g(["cv_prc", "cvprc", "ex_prc", "exprc"]))
    floor = _mznum(g(["act_mktprcfl_cvprc_lwtrsprc"]))
    refix_pct = round(floor / price * 100, 1) if (floor and price) else None
    mat = _parse_date(g(["bd_mtd"]))
    amt = _mznum(g(["bd_fta"]))
    return {
        "rcept_no": rcept, "kind": kind,
        "corp_code": r.get("corp_code"), "corp_name": r.get("corp_name"),
        "rcept_dt": acpt,
        "issue_date": issue.strftime("%Y-%m-%d") if issue else None,
        "maturity": mat.strftime("%Y-%m-%d") if mat else None,
        "coupon": _mznum(g(["bd_intr_ex"])), "ytm": _mznum(g(["bd_intr_sf"])),
        "price": price,
        "conv_start": g(["cvrqpd_bgd", "expd_bgd"]), "conv_end": g(["cvrqpd_edd", "expd_edd"]),
        "refix_floor": floor, "refix_pct": refix_pct,
        "dilution": _mznum(g(["cvisstk_tisstk_vs", "nstk_isstk_tisstk_vs", "exstk_tisstk_vs"])),
        "amount_eok": round(amt / 1e8) if amt else None,
        "shares": _est_total_shares(r, kind), "round_no": g(["bd_tm"]),
    }


_BOND_COLS = ["rcept_no", "kind", "corp_code", "corp_name", "rcept_dt", "issue_date",
              "maturity", "coupon", "ytm", "price", "conv_start", "conv_end",
              "refix_floor", "refix_pct", "dilution", "amount_eok", "shares", "round_no"]


def db_upsert_bonds(records):
    if not records:
        return 0
    con = db_connect()
    con.executemany(
        f"INSERT OR REPLACE INTO bond ({','.join(_BOND_COLS)}) "
        f"VALUES ({','.join(['?'] * len(_BOND_COLS))})",
        [tuple(rec.get(c) for c in _BOND_COLS) for rec in records])
    con.commit()
    con.close()
    return len(records)


def db_collect(api_key_arg, bgn, es, progress=None):
    """bgn~es 기간의 CB·BW 발행결정을 수집해 DB에 적재한다. 반환: {CB:n, BW:n}."""
    counts = {}
    kinds = [("CB", "cvbdIsDecsn.json", "전환사채"), ("BW", "bdwtIsDecsn.json", "신주인수권부사채")]
    for ki, (kind, ep, kw) in enumerate(kinds):
        if progress:
            progress(ki / len(kinds), f"{kind} 공시 목록 조회 중...")
        all_rows = []
        for cb, ce in _date_chunks(bgn, es, 90):
            try:
                rows, _, _ = dart_list_all({"bgn_de": cb, "end_de": ce, "pblntf_ty": "B"})
                all_rows.extend(rows)
            except DartError:
                continue
        ldf = pd.DataFrame(all_rows)
        if ldf.empty:
            counts[kind] = 0
            continue
        ldf = ldf[ldf["report_nm"].str.contains(kw, na=False, regex=False)]
        codes = list(dict.fromkeys(ldf["corp_code"].tolist())) if not ldf.empty else []
        total = len(codes)
        saved = 0
        batch = []
        for idx, code in enumerate(codes, 1):
            if progress and (idx % 5 == 0 or idx == total):
                progress((ki + idx / max(total, 1)) / len(kinds),
                         f"{kind} 상세 수집·적재 중... {idx}/{total}개사")
            try:
                drows = dart_get(ep, {"corp_code": code, "bgn_de": bgn, "end_de": es})
            except DartError:
                continue
            for r in drows:
                rec = _parse_bond_detail(r, kind)
                if rec:
                    batch.append(rec)
            if len(batch) >= 300:
                saved += db_upsert_bonds(batch)
                batch = []
        if batch:
            saved += db_upsert_bonds(batch)
        counts[kind] = saved
    return counts


def db_query_bond(kind, bgn, es):
    """스크리너/차환수요용: 기간 내 kind 발행을 build_screener_df와 동일한 컬럼으로 반환."""
    con = db_connect()
    rows = con.execute(
        "SELECT * FROM bond WHERE kind=? AND rcept_dt BETWEEN ? AND ? ORDER BY rcept_dt DESC",
        (kind, bgn, es)).fetchall()
    con.close()
    if not rows:
        return pd.DataFrame()
    price_col = "전환가액(원)" if kind == "CB" else "행사가액(원)"
    recs = []
    for r in rows:
        iss = _parse_date(r["issue_date"]); mat = _parse_date(r["maturity"])
        years = round((mat - iss).days / 365.25, 1) if (iss and mat) else None
        recs.append({
            "종목명": r["corp_name"], "_corp_code": r["corp_code"], "_shares": r["shares"],
            "접수일": r["rcept_dt"], "만기일": r["maturity"],
            "표면이자율(%)": r["coupon"], "만기이자율(%)": r["ytm"], "만기(년)": years,
            price_col: r["price"], "리픽싱하한(%)": r["refix_pct"],
            "리픽싱유무": "있음" if r["refix_pct"] is not None else "없음",
            "희석비율(%)": r["dilution"], "사채총액(억)": r["amount_eok"],
            "원문": (DART_VIEWER + r["rcept_no"]) if r["rcept_no"] else None,
        })
    return pd.DataFrame(recs)


def db_query_issue(type_label, bgn, es):
    """발행내역 탭(전체 회사)용: DB의 CB/BW를 ISSUE_SPECS 컬럼 순서와 동일하게 반환."""
    kind = "CB" if "CB" in type_label else "BW"
    con = db_connect()
    rows = con.execute(
        "SELECT * FROM bond WHERE kind=? AND rcept_dt BETWEEN ? AND ? ORDER BY rcept_dt DESC",
        (kind, bgn, es)).fetchall()
    con.close()
    if not rows:
        return pd.DataFrame()
    price_lbl = "전환가액(원)" if kind == "CB" else "행사가액(원)"
    start_lbl = "전환청구 시작" if kind == "CB" else "행사 시작"
    end_lbl = "전환청구 종료" if kind == "CB" else "행사 종료"
    recs = []
    for r in rows:
        rec = {
            "회사": r["corp_name"], "접수일": r["rcept_dt"],
            "_corp_code": r["corp_code"], "_shares": r["shares"],
            "사채총액(억)": r["amount_eok"], "표면이자율(%)": r["coupon"],
            "만기이자율(%)": r["ytm"], price_lbl: r["price"],
            start_lbl: r["conv_start"], end_lbl: r["conv_end"],
            "사채만기일": r["maturity"],
        }
        if kind == "CB":
            rec["리픽싱 최저가(원)"] = r["refix_floor"]
        rec["희석비율(%)"] = r["dilution"]
        rec["원문"] = (DART_VIEWER + r["rcept_no"]) if r["rcept_no"] else None
        recs.append(rec)
    return pd.DataFrame(recs)


def db_query_company_bond(corp_code, kind):
    """기업 발행 동향용: build_company_bonds와 동일한 리스트 형태로 반환."""
    con = db_connect()
    rows = con.execute(
        "SELECT * FROM bond WHERE kind=? AND corp_code=? ORDER BY issue_date",
        (kind, corp_code)).fetchall()
    con.close()
    price_lbl = "최초전환가(원)" if kind == "CB" else "최초행사가(원)"
    recs = []
    for r in rows:
        iss = _parse_date(r["issue_date"])
        if not iss:
            continue
        recs.append({
            "회차": r["round_no"], "발행일": iss,
            "발행액(억)": r["amount_eok"], "표면(%)": r["coupon"],
            "만기이자율(%)": r["ytm"], price_lbl: r["price"],
            "리픽싱하한(원)": r["refix_floor"], "만기일": _parse_date(r["maturity"]),
            "_rcept": r["rcept_no"],
        })
    recs.sort(key=lambda x: x["발행일"])
    return recs


# ==================================================================
#  탭) 데이터 관리 (DB 백필 · 업데이트 · 상태)
# ==================================================================
def tab_data(corp_df):
    st.header("🗄️ 데이터 관리 (로컬 DB)")
    st.caption("DART에서 CB/BW 발행내역을 로컬 DB(dart.db)에 적재합니다. 적재해두면 스크리너·차환수요·기업동향이 "
               "DART를 실시간으로 긁지 않고 DB에서 즉시 조회합니다.")

    cnt = db_counts()
    last = db_get_meta("last_update", "아직 없음")
    bf = db_get_meta("last_backfill", "아직 없음")
    m1, m2, m3 = st.columns(3)
    m1.metric("적재된 CB", f"{cnt.get('CB', 0):,}건")
    m2.metric("적재된 BW", f"{cnt.get('BW', 0):,}건")
    m3.metric("마지막 업데이트", last if last != "아직 없음" else "—")
    st.caption(f"최초 백필 시점: {bf}")

    st.divider()
    st.subheader("① 최초 백필 (한 번만) — 터미널에서 실행하세요")
    st.markdown(
        "최초 백필은 받을 양이 많아 **대시보드 버튼이 아니라 별도 터미널에서 `backfill.py`로** 실행합니다.\n"
        "(대시보드 버튼으로 돌리면, 화면을 건드리거나 버튼을 다시 누르는 순간 처음부터 재시작되어 잘 끝나지 않습니다. "
        "그래서 백필 버튼은 없앴습니다.)\n\n"
        "**방법**\n"
        "1. VS Code 상단 메뉴 `Terminal → New Terminal` 로 **새 터미널**을 엽니다.\n"
        "2. 아래 명령을 붙여넣고 Enter → 이어서 **DART 인증키**를 붙여넣고 Enter.\n"
        "3. 진행 상황이 글자로 표시됩니다. 끝날 때까지 그 터미널을 **닫지 마세요** "
        "(그동안 대시보드는 계속 사용해도 됩니다)."
    )
    st.code("python backfill.py 5", language="powershell")
    st.caption("끝의 숫자는 받을 연수입니다(3·5·10 중). 5년 ≈ 30분~1시간, 10년 ≈ 1~2시간. "
               "중간에 꺼져도 받은 만큼 저장되고, 다시 실행하면 이어서 받습니다. "
               "완료되면 이 화면을 새로고침(F5)하면 위 '적재된 CB/BW' 숫자가 올라가 있습니다.")

    st.divider()
    st.subheader("② 증분 업데이트")
    st.caption("마지막 업데이트 이후의 새 공시만 받아 DB에 더합니다. 보통 1분 안쪽입니다.  "
               "**백필을 한 번 해두면, 이후에는 앱을 켤 때 하루 1회 자동으로 최신화됩니다.** "
               "아래 버튼은 지금 당장 다시 받고 싶을 때만 누르세요.")
    if st.button("지금 업데이트", key="db_update"):
        last_u = db_get_meta("last_update")
        today = dt.date.today()
        if last_u:
            start = _parse_date(last_u) or (today - dt.timedelta(days=30))
            start = start - dt.timedelta(days=14)   # 정정·지연공시 보완용 겹침
        else:
            start = today - dt.timedelta(days=90)
        bs, es = start.strftime("%Y%m%d"), today.strftime("%Y%m%d")
        pbar = st.progress(0.0, "준비 중...")
        try:
            res = db_collect(api_key, bs, es, progress=lambda f, t: pbar.progress(min(f, 1.0), t))
        except DartError as e:
            pbar.empty(); st.error(str(e)); return
        pbar.empty()
        db_set_meta("last_update", es)
        st.success(f"업데이트 완료 — CB {res.get('CB',0):,}건 · BW {res.get('BW',0):,}건 반영")

    st.divider()
    st.caption("※ 스크리너·차환수요·기업동향은 DB에 데이터가 있으면 DB에서 즉시, 없으면 DART에서 실시간으로 조회합니다. "
               "즉 백필을 한 번 돌리면 그때부터 자동으로 빨라집니다. "
               "유상증자(스크리너)와 시가총액·AI 분석은 종전처럼 실시간으로 동작합니다.")


def auto_daily_update(api_key_arg):
    """백필이 되어 있으면, 앱을 연 날 기준 하루 1회 증분 업데이트를 자동 실행한다.
    - DB가 비어 있으면(백필 전) 아무 것도 하지 않음
    - 같은 날 이미 최신화됐으면 건너뜀 (세션/DB 메타 이중 체크)
    - 실패해도 조용히 넘어가고, 수동 '지금 업데이트' 버튼으로 재시도 가능"""
    if db_bond_count("CB") == 0 and db_bond_count("BW") == 0:
        return
    today_d = dt.date.today()
    today = today_d.strftime("%Y%m%d")
    if st.session_state.get("_auto_upd_done") == today:
        return
    if db_get_meta("last_update") == today:
        st.session_state["_auto_upd_done"] = today
        return
    last_u = db_get_meta("last_update")
    if last_u:
        start = (_parse_date(last_u) or (today_d - dt.timedelta(days=30))) - dt.timedelta(days=14)
    else:
        start = today_d - dt.timedelta(days=90)
    bs, es = start.strftime("%Y%m%d"), today
    try:
        with st.spinner("최신 공시를 반영하는 중입니다... (하루 1회 자동 최신화)"):
            db_collect(api_key_arg, bs, es)
        db_set_meta("last_update", es)
    except Exception:
        pass
    st.session_state["_auto_upd_done"] = today


# ------------------------------------------------------------------
# 3. 메뉴 라우팅
# ------------------------------------------------------------------
def _db_bond_df(bgn, es):
    """bond 테이블을 기간으로 조회해 보기 좋은 DataFrame으로."""
    con = db_connect()
    rows = con.execute(
        "SELECT kind 유형, corp_name 회사, corp_code _corp_code, rcept_dt 공시일, issue_date 발행일, maturity 만기일, "
        "round_no 회차, amount_eok '사채총액(억)', coupon '표면이자율(%)', ytm '만기이자율(%)', "
        "price '전환/행사가(원)', refix_floor '리픽싱하한(원)', refix_pct '리픽싱하한(%)', "
        "dilution '희석비율(%)', rcept_no "
        "FROM bond WHERE rcept_dt BETWEEN ? AND ? ORDER BY rcept_dt DESC",
        (bgn, es)).fetchall()
    con.close()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        df["원문"] = DART_VIEWER + df["rcept_no"].astype(str)
        df = df.drop(columns=["rcept_no"])
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def _krx_marcap_map():
    """KRX 상장목록에서 종목코드→시가총액(억) 맵. (best-effort)"""
    try:
        import FinanceDataReader as fdr
        lst = fdr.StockListing("KRX")
    except Exception:
        return {}
    code_col = next((c for c in ["Code", "Symbol", "종목코드"] if c in lst.columns), None)
    cap_col = next((c for c in ["Marcap", "MarketCap", "시가총액"] if c in lst.columns), None)
    if not code_col or not cap_col:
        return {}
    m = {}
    for _, r in lst.iterrows():
        try:
            m[str(r[code_col]).zfill(6)] = round(float(r[cap_col]) / 1e8)
        except Exception:
            pass
    return m


def _enrich_db_export(df, corp_df, with_fin=True, with_cap=True, progress=None):
    """발행내역 DB export 에 연도별 재무(2023~2025·당해 상반기)·시가총액을 붙인다.
       (AI발표 '2023년발행내역' 시트와 동일 구성)"""
    if df.empty or "_corp_code" not in df.columns:
        return df
    today = dt.date.today()
    fin_periods = ["2023년", "2024년", "2025년", f"{today.year}년 상반기"]
    metrics = ["매출액", "영업이익", "현금성자산", "부채총계", "자본총계"]
    codes = [c for c in df["_corp_code"].dropna().astype(str).unique() if c and c != "None"]
    cap_map = {}
    fin_map = {}
    marcap = _krx_marcap_map() if with_cap else {}
    name_to_stock = {}
    if corp_df is not None and not corp_df.empty:
        name_to_stock = {str(r["corp_code"]): str(r.get("stock_code", "") or "").strip()
                         for _, r in corp_df.iterrows()}
    n = len(codes)
    for i, cc in enumerate(codes, 1):
        if with_fin:
            try:
                fin_map[cc] = fetch_company_financials(api_key, cc, 2025, today.year)
            except Exception:
                fin_map[cc] = {}
        if with_cap:
            sc = name_to_stock.get(cc, "")
            cap_map[cc] = marcap.get(sc.zfill(6)) if sc else None
        if progress:
            progress(i / max(n, 1), f"재무·시가총액 수집 {i}/{n}")
    out = df.copy()
    if with_cap:
        out["시가총액(억)"] = out["_corp_code"].astype(str).map(cap_map)
    if with_fin:
        for p in fin_periods:
            for m in metrics:
                out[f"{p} {m}"] = out["_corp_code"].astype(str).map(
                    lambda cc, _p=p, _m=m: (fin_map.get(cc, {}).get(_p) or {}).get(_m))
    return out


def tab_db(corp_df):
    st.header("🗂️ Ⅰ. DB (Data Base)")
    st.caption("과거 CB·BW 발행내역 DB를 Excel로 내보내고, 외부 Excel/CSV를 업로드해 현재 대시보드에 없는 자유로운 분석을 수행합니다.")

    # ================= ① 발행내역 DB → Excel 내보내기 =================
    st.subheader("① 발행내역 DB 내보내기")
    cnt = db_counts()
    st.caption(f"적재된 발행내역: CB {cnt.get('CB',0):,}건 · BW {cnt.get('BW',0):,}건  "
               "(적재는 '데이터 관리 (DB)' 메뉴에서 백필)")
    today = dt.date.today()
    pmode = st.radio("기간 선택 방식", ["연도 범위", "최근 N년"], horizontal=True, key="db_pmode")
    if pmode == "연도 범위":
        yrs = list(range(2017, today.year + 1))
        yc1, yc2 = st.columns(2)
        y_from = yc1.selectbox("시작 연도", yrs, index=0, key="db_yfrom")
        y_to = yc2.selectbox("종료 연도", yrs, index=len(yrs) - 1, key="db_yto")
        if y_from > y_to:
            y_from, y_to = y_to, y_from
        bs = f"{y_from}0101"
        es = min(today, dt.date(y_to, 12, 31)).strftime("%Y%m%d")
        plabel = f"{y_from}-{y_to}" if y_from != y_to else f"{y_from}"
    else:
        yr = st.selectbox("최근 기간", ["최근 3년", "최근 5년", "최근 10년"], index=1, key="db_exp_yr")
        years = {"최근 3년": 3, "최근 5년": 5, "최근 10년": 10}[yr]
        bs = (today - dt.timedelta(days=365 * years)).strftime("%Y%m%d")
        es = today.strftime("%Y%m%d")
        plabel = yr

    with_fin = st.checkbox("연도별 재무(매출·영업이익·현금성·부채·자본)·시가총액 포함 (느림 · 기업 수에 비례)",
                           value=False, key="db_exp_fin",
                           help="2023·2024·2025년 및 당해 상반기 재무와 시가총액을 기업별로 붙입니다. "
                                "기업 수가 많으면 수십 초~수 분 걸릴 수 있습니다. (AI발표 '발행내역' 시트 구성)")
    if st.button("발행내역 Excel 생성", type="primary", key="db_exp_btn"):
        df = _db_bond_df(bs, es)
        if df.empty:
            st.info("해당 기간에 적재된 발행내역이 없습니다. '데이터 관리 (DB)'에서 먼저 백필하세요.")
            st.session_state.pop("db_export_df", None)
        else:
            if with_fin:
                pbar = st.progress(0.0, "재무·시가총액 수집 중...")
                df = _enrich_db_export(df, corp_df, with_fin=True, with_cap=True,
                                       progress=lambda f, t: pbar.progress(f, t))
                pbar.empty()
            df = df.drop(columns=[c for c in ["_corp_code"] if c in df.columns])
            st.session_state["db_export_df"] = df
            st.session_state["db_export_label"] = plabel
    if "db_export_df" in st.session_state:
        edf = st.session_state["db_export_df"]
        lbl = st.session_state.get("db_export_label", plabel)
        st.caption(f"총 {len(edf):,}건")
        _download_buttons(edf, f"발행내역DB_{lbl}_{today:%Y%m%d}", "db_export_dl")

    st.divider()

    # ================= ② Excel/CSV 업로드 → 자유 분석 =================
    st.subheader("② Excel/CSV 업로드 → 자유 분석")
    st.caption("보유하신 엑셀(또는 위에서 내보낸 발행내역)을 올리면, 미리보기·기초통계·그룹 집계·AI 질의로 자유롭게 분석할 수 있습니다.")
    up = st.file_uploader("파일 업로드 (.xlsx / .csv)", type=["xlsx", "csv"], key="db_up")
    if not up:
        return
    try:
        if up.name.lower().endswith(".csv"):
            udf = pd.read_csv(up)
        else:
            udf = pd.read_excel(up)       # openpyxl 필요
    except Exception as e:
        st.error(f"파일을 읽지 못했습니다: {e}  (xlsx는 'python -m pip install openpyxl' 필요)")
        return
    if udf.empty:
        st.info("빈 파일입니다.")
        return

    st.success(f"업로드 완료 — {len(udf):,}행 × {len(udf.columns)}열")
    with st.expander("미리보기 (상위 200행)", expanded=True):
        show_table(udf.head(200), f"업로드_{up.name}", "db_up_prev")

    num_cols = [c for c in udf.columns if pd.api.types.is_numeric_dtype(pd.to_numeric(udf[c], errors="coerce"))
                and pd.to_numeric(udf[c], errors="coerce").notna().any()]

    with st.expander("기초 통계 (숫자 열)"):
        if num_cols:
            desc = udf[num_cols].apply(pd.to_numeric, errors="coerce").describe().T
            desc.index.name = "항목"
            show_fs_table(desc.rename_axis("항목"), dl_stem="기초통계", dl_key="db_desc_dl")
        else:
            st.caption("숫자 열이 없습니다.")

    # --- 그룹 집계 (코드 실행 · 무료) ---
    with st.expander("그룹 집계 (피벗)", expanded=True):
        gc1, gc2, gc3 = st.columns(3)
        group_col = gc1.selectbox("그룹 기준(행)", ["(없음)"] + list(udf.columns), key="db_grp")
        val_col = gc2.selectbox("집계 값", ["(개수)"] + num_cols, key="db_val")
        aggf = gc3.selectbox("집계 방식", ["합계", "평균", "최대", "최소", "개수"], key="db_agg")
        if group_col != "(없음)":
            g = udf.copy()
            if val_col != "(개수)":
                g["_v"] = pd.to_numeric(g[val_col], errors="coerce")
                func = {"합계": "sum", "평균": "mean", "최대": "max", "최소": "min", "개수": "count"}[aggf]
                res = g.groupby(group_col)["_v"].agg(func).reset_index()
                res.columns = [group_col, f"{val_col}·{aggf}"]
                res = res.sort_values(res.columns[1], ascending=False)
            else:
                res = g.groupby(group_col).size().reset_index(name="개수").sort_values("개수", ascending=False)
            show_table(res, "그룹집계", "db_grp_dl")

    # --- AI 질의 (선택 · 비용) ---
    st.markdown("##### 🤖 AI에게 이 데이터 분석 요청")
    if not anthropic_key:
        st.caption("사이드바에 Anthropic API 키를 넣으면, 업로드한 데이터에 대해 자유롭게 질문·분석을 요청할 수 있습니다.")
        return
    q = st.text_area("질문/요청 (예: 연도별 발행금액 추이와 특징을 요약해줘 / 금리가 높은 상위 기업은?)", key="db_q")
    if st.button("AI 분석 실행", type="primary", key="db_ai_btn") and q.strip():
        try:
            import anthropic
            # 비용 관리: 스키마 + 상위 60행 + 숫자열 기초통계만 전달
            head_csv = udf.head(60).to_csv(index=False)
            stats = ""
            if num_cols:
                stats = udf[num_cols].apply(pd.to_numeric, errors="coerce").describe().T.to_csv()
            prompt = (f"다음은 사용자가 업로드한 표 데이터입니다(전체 {len(udf)}행 중 상위 60행 + 숫자열 통계).\n"
                      f"이 데이터만 근거로 질문에 답하세요. 데이터에 없는 값은 추정하지 말고 '자료 없음'이라 하세요.\n\n"
                      f"[열 목록]\n{list(udf.columns)}\n\n[상위 60행 CSV]\n{head_csv}\n\n"
                      f"[숫자열 통계]\n{stats}\n\n[질문]\n{q.strip()}\n\n"
                      "한국어로 핵심 먼저, 근거 수치와 함께 간결히 답하세요.")
            with st.spinner("AI가 데이터를 분석 중..."):
                msg = anthropic.Anthropic(api_key=anthropic_key).messages.create(
                    model=ai_model, max_tokens=1500, messages=[{"role": "user", "content": prompt}])
            st.session_state["db_ai"] = "".join(getattr(b, "text", "") for b in msg.content)
        except Exception as e:
            st.error(f"AI 분석 실패: {e}")
    if "db_ai" in st.session_state:
        st.markdown(st.session_state["db_ai"])
        st.caption("※ 업로드 데이터의 상위 일부·통계만 근거로 한 요약입니다. 전수 계산이 필요하면 위 '그룹 집계'를 쓰세요.")


# 메뉴 순서 = Mezzanine 탐색 Flow
#   Ⅰ.DB → Ⅱ-1 전체 screen → Ⅱ-2 후보 look-up → Ⅲ Analysis → 발행내역 확인 → 기관분석
# 메인 메뉴 = 섹션 헤더 + 하위 항목(버튼). 각 섹션(Ⅰ~Ⅳ)마다 헤더를 붙여 통일.
#   ※ 라디오 대신 '버튼'으로 구현 → 탭 안의 버튼(AI 등)을 눌러도 메뉴가 바뀌지 않음.
NAV_GROUPS = [
    ("Ⅰ. DB", {"🗂️ DB (업로드 분석)": tab_db}),
    ("Ⅱ. Look-up", {
        "　1. 발행내역 - 전체 screen": tab_screener,
        "　2. 발행 후보 기업 - look-up": tab_demand,
    }),
    ("Ⅲ. Analysis", {"🧭 Analysis": tab_analysis}),
    ("Ⅳ. 밸류에이션", {"💹 밸류에이션": tab_mezz_val}),
    ("개별 조회", {
        "📄 발행내역 확인 (기업별)": tab_company,
        "🏦 기관 분석 (배정기관)": tab_institution,
    }),
]
MAIN_TABS = {}
for _hdr, _grp in NAV_GROUPS:
    MAIN_TABS.update(_grp)
OTHER_TABS = {
    "🧮 밸류에이션 (공모가 산정근거 · VC)": tab_valuation,
    "📊 상장사 실적 비교": tab_financials,
    "🆕 최근 상장/공모 현황": tab_ipo,
    "🧬 메자닌 벤치마킹": tab_mezzanine,
    "🔁 기타공시 (자사주 등)": tab_other,
    "🗄️ 데이터 관리 (DB)": tab_data,
}
TABS = {**MAIN_TABS, **OTHER_TABS}

# 활성 탭(단일 소스).
_default_tab = "　1. 발행내역 - 전체 screen"
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = _default_tab


def _nav_section(container, header, items):
    """섹션 헤더 + 메뉴 버튼들. 선택된 항목은 primary 로 강조."""
    if header:
        container.markdown(
            f"<div class='nav-sec'>{header}</div>", unsafe_allow_html=True)
    for label in items:
        selected = (st.session_state["active_tab"] == label)
        if container.button(label, key=f"nav_btn::{label}",
                            use_container_width=True,
                            type="primary" if selected else "secondary"):
            st.session_state["active_tab"] = label
            st.rerun()


st.sidebar.markdown("### 시스템 구성")
for _hdr, _grp in NAV_GROUPS:
    _nav_section(st.sidebar, _hdr, list(_grp.keys()))
with st.sidebar.expander("➕ 기타 메뉴", expanded=(st.session_state["active_tab"] in OTHER_TABS)):
    _nav_section(st, None, list(OTHER_TABS.keys()))
choice = st.session_state["active_tab"]
st.sidebar.divider()
st.sidebar.caption("데이터 출처: 금융감독원 OpenDART")

if not api_key:
    st.info("👈 왼쪽 사이드바 맨 위 **DART 인증키** 칸에 키를 붙여넣고 **'적용'** 버튼(또는 Enter)을 누르면 대시보드가 열립니다.")
else:
    try:
        corp_df = load_corp_codes(api_key)
    except Exception as e:
        st.error(f"기업 목록을 불러오지 못했습니다. 인증키를 확인해 주세요. ({e})")
        st.stop()
    db_init()
    auto_daily_update(api_key)   # 백필돼 있으면 하루 1회 자동 최신화
    TABS[choice](corp_df)
