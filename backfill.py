# -*- coding: utf-8 -*-
"""
DART CB/BW 백필 전용 스크립트  (대시보드와 별개로 '터미널에서' 실행)

왜 따로 실행하나:
  - 5~10년치 전체 시장 데이터를 받는 작업은 30분~2시간이 걸립니다.
  - 이런 긴 작업을 대시보드(Streamlit) 버튼 안에서 돌리면, 화면을 건드리거나
    버튼을 다시 누르는 순간 처음부터 재시작되어 끝나지 않습니다.
  - 이 스크립트는 터미널에서 혼자 돌면서 진행 상황을 글자로 보여주고,
    받는 즉시 dart.db 에 저장합니다. (중간에 꺼져도 받은 만큼은 남고, 다시 돌리면 이어서 받습니다)

실행 방법 (대시보드가 있는 폴더에서):
    python backfill.py            →  인증키·기간을 물어봄 (가장 쉬움)
    python backfill.py 5          →  최근 5년치 (키는 물어봄)
    python backfill.py 5 4자리인증키...  →  키까지 한 번에

끝나면 대시보드를 켜기만 하면 스크리너·차환수요·기업동향이 DB에서 즉시 조회됩니다.
"""

import os
import io
import re
import sys
import time
import zipfile
import sqlite3
import datetime as dt
import xml.etree.ElementTree as ET

import requests

DART_API = "https://opendart.fss.or.kr/api"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dart.db")

# 발행공시 분류: CB=전환사채, BW=신주인수권부사채 (둘 다 '주요사항보고 pblntf_ty=B' 안에 있음)
KINDS = [
    ("CB", "cvbdIsDecsn.json", "전환사채"),
    ("BW", "bdwtIsDecsn.json", "신주인수권부사채"),
]


# ----------------------------------------------------------------------
# 작은 도우미 (대시보드 app.py 와 동일한 규칙)
# ----------------------------------------------------------------------
def _mznum(s):
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


def _date_chunks(bgn, es, max_days=90):
    d0, d1 = _parse_date(bgn), _parse_date(es)
    if not d0 or not d1:
        return [(bgn, es)]
    out, cur = [], d0
    while cur <= d1:
        nxt = min(d1, cur + dt.timedelta(days=max_days - 1))
        out.append((cur.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")))
        cur = nxt + dt.timedelta(days=1)
    return out


def _est_total_shares(r, kind):
    def g(keys):
        for k in keys:
            if k in r and r[k] not in (None, ""):
                return r[k]
        return None
    if kind == "CB":
        cnt, vs = _mznum(g(["cvisstk_cnt"])), _mznum(g(["cvisstk_tisstk_vs"]))
    else:  # BW
        cnt, vs = _mznum(g(["nstk_isstk_cnt"])), _mznum(g(["nstk_isstk_tisstk_vs", "exstk_tisstk_vs"]))
    if cnt and vs and vs > 0:
        return cnt * 100.0 / vs
    return None


def _parse_bond_detail(r, kind):
    """DART 발행결정 1건(raw) → bond 테이블 한 행(dict). app.py 와 동일."""
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


# ----------------------------------------------------------------------
# DART 호출 (네트워크 오류 시 몇 번 재시도)
# ----------------------------------------------------------------------
def _get(url, params, tries=4):
    last = None
    for i in range(tries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            return resp.json()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"네트워크 오류(재시도 실패): {last}")


def list_page(key, base_params, page):
    q = dict(base_params)
    q.update({"crtfc_key": key, "page_no": str(page), "page_count": "100"})
    data = _get(f"{DART_API}/list.json", q)
    status = data.get("status")
    if status == "000":
        return data
    if status == "013":           # 데이터 없음
        return {"list": [], "total_page": 0, "total_count": 0}
    raise RuntimeError(f"목록 조회 오류({status}) {data.get('message', '')}")


def get_detail(key, endpoint, corp_code, bgn, es):
    q = {"crtfc_key": key, "corp_code": corp_code, "bgn_de": bgn, "end_de": es}
    data = _get(f"{DART_API}/{endpoint}", q)
    status = data.get("status")
    if status == "000":
        return data.get("list", [])
    if status == "013":
        return []
    raise RuntimeError(f"상세 조회 오류({status}) {data.get('message', '')}")


# ----------------------------------------------------------------------
# DB
# ----------------------------------------------------------------------
def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.row_factory = sqlite3.Row
    return con


def db_init():
    con = db_connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS bond (
      rcept_no TEXT PRIMARY KEY,
      kind TEXT, corp_code TEXT, corp_name TEXT,
      rcept_dt TEXT, issue_date TEXT, maturity TEXT,
      coupon REAL, ytm REAL, price REAL,
      conv_start TEXT, conv_end TEXT,
      refix_floor REAL, refix_pct REAL,
      dilution REAL, amount_eok REAL, shares REAL, round_no TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_bond_kind_dt ON bond(kind, rcept_dt);
    CREATE INDEX IF NOT EXISTS ix_bond_corp ON bond(kind, corp_code);
    CREATE INDEX IF NOT EXISTS ix_bond_mat ON bond(kind, maturity);
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    con.commit()
    con.close()


def db_upsert(con, records):
    if not records:
        return 0
    con.executemany(
        f"INSERT OR REPLACE INTO bond ({','.join(_BOND_COLS)}) "
        f"VALUES ({','.join(['?'] * len(_BOND_COLS))})",
        [tuple(rec.get(c) for c in _BOND_COLS) for rec in records])
    con.commit()
    return len(records)


def db_set_meta(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    con.commit()


def db_corp_has(con, kind, corp_code):
    row = con.execute("SELECT 1 FROM bond WHERE kind=? AND corp_code=? LIMIT 1",
                      (kind, corp_code)).fetchone()
    return row is not None


def db_count(con, kind):
    return con.execute("SELECT COUNT(*) c FROM bond WHERE kind=?", (kind,)).fetchone()["c"]


# ----------------------------------------------------------------------
# 백필 본체
# ----------------------------------------------------------------------
def fetch_b_list(key, bgn, es):
    """기간 내 '주요사항보고(B)' 전체 목록을 받아온다. (CB·BW 공용 → 한 번만 받음)"""
    chunks = _date_chunks(bgn, es, 90)
    all_rows = []
    for ci, (cb, ce) in enumerate(chunks, 1):
        first = list_page(key, {"bgn_de": cb, "end_de": ce, "pblntf_ty": "B"}, 1)
        rows = list(first.get("list", []))
        total_page = int(first.get("total_page", 1) or 1)
        pages = min(total_page, 100)        # 안전장치: 구간당 최대 1만건
        for p in range(2, pages + 1):
            rows.extend(list_page(key, {"bgn_de": cb, "end_de": ce, "pblntf_ty": "B"}, p).get("list", []))
        all_rows.extend(rows)
        print(f"  [목록] 구간 {ci}/{len(chunks)} ({cb}~{ce}) · {len(rows):,}건 · 누적 {len(all_rows):,}건")
        sys.stdout.flush()
    return all_rows


def run(key, years):
    today = dt.date.today()
    bgn = (today - dt.timedelta(days=365 * years)).strftime("%Y%m%d")
    es = today.strftime("%Y%m%d")
    print("=" * 64)
    print(f"DART CB/BW 백필 시작 — 최근 {years}년 ({bgn} ~ {es})")
    print(f"저장 위치: {DB_PATH}")
    print("=" * 64)

    db_init()
    con = db_connect()

    # 1) 주요사항보고(B) 목록 한 번만 수집 → CB·BW 로 나눠 사용
    print("\n[1단계] 전체 '주요사항보고' 목록을 받는 중... (가장 오래 걸리는 단계)")
    t0 = time.time()
    b_rows = fetch_b_list(key, bgn, es)
    print(f"  → 목록 {len(b_rows):,}건 수집 완료 ({time.time()-t0:.0f}초)")

    for kind, ep, kw in KINDS:
        # 이 유형에 해당하는 회사만 추림
        corps = []
        seen = set()
        for r in b_rows:
            nm = r.get("report_nm") or ""
            cc = r.get("corp_code")
            if cc and (cc not in seen) and (kw in nm):
                seen.add(cc)
                corps.append(cc)
        total = len(corps)
        print(f"\n[2단계] {kind}: 대상 회사 {total:,}개사 — 회사별 상세를 받아 저장합니다.")
        saved = 0
        skipped = 0
        t1 = time.time()
        for idx, cc in enumerate(corps, 1):
            # 이미 받은 회사면 건너뜀(= 중간에 끊겨도 다시 돌리면 이어서 받음)
            if db_corp_has(con, kind, cc):
                skipped += 1
            else:
                try:
                    drows = get_detail(key, ep, cc, bgn, es)
                except Exception as e:
                    print(f"    ! {cc} 건너뜀: {e}")
                    drows = []
                batch = [rec for r in drows if (rec := _parse_bond_detail(r, kind))]
                saved += db_upsert(con, batch)
            if idx % 20 == 0 or idx == total:
                done_cnt = db_count(con, kind)
                el = time.time() - t1
                rate = idx / el if el > 0 else 0
                eta = (total - idx) / rate if rate > 0 else 0
                print(f"  {kind} {idx:,}/{total:,}개사 · DB적재 {done_cnt:,}건 "
                      f"(신규 {saved:,}·건너뜀 {skipped:,}) · 남은시간 ~{eta/60:.0f}분")
                sys.stdout.flush()
        print(f"  → {kind} 완료 · DB 누적 {db_count(con, kind):,}건 ({time.time()-t1:.0f}초)")

    db_set_meta(con, "last_backfill", f"{bgn}~{es} ({today})")
    db_set_meta(con, "last_update", es)
    cb_n, bw_n = db_count(con, "CB"), db_count(con, "BW")
    con.close()
    print("\n" + "=" * 64)
    print(f"백필 완료!  CB {cb_n:,}건 · BW {bw_n:,}건  →  이제 대시보드를 켜면 즉시 조회됩니다.")
    print("=" * 64)


def main():
    args = sys.argv[1:]
    years = None
    key = None
    # 인자 해석: 숫자=연수, 그 외(긴 문자열)=인증키
    for a in args:
        if a.isdigit():
            years = int(a)
        elif len(a) >= 20:
            key = a
    if years is None:
        raw = input("몇 년치를 받을까요? (예: 5) [기본 5]: ").strip()
        years = int(raw) if raw.isdigit() else 5
    if not key:
        key = input("DART 인증키(40자리)를 붙여넣고 Enter: ").strip()
    if not key or len(key) < 20:
        print("인증키가 올바르지 않습니다. 다시 실행해 주세요.")
        return
    try:
        run(key, years)
    except KeyboardInterrupt:
        print("\n중단되었습니다. 받은 만큼은 저장돼 있고, 다시 실행하면 이어서 받습니다.")


if __name__ == "__main__":
    main()
