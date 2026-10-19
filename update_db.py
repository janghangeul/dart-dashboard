# -*- coding: utf-8 -*-
"""
update_db.py — 최근 공시만 받아 dart.db 를 '증분 갱신'하는 스크립트.

용도:
  1) GitHub Actions 가 매일 자동으로 실행 (내 PC 불필요)
  2) 필요하면 로컬에서 수동 실행도 가능: python update_db.py <DART키>

동작: 최근 N일(기본 45일) 치 CB/BW 발행공시를 받아 dart.db 에 upsert(있으면 갱신, 없으면 추가).
      backfill.py 의 함수를 그대로 재사용하므로 로직이 본체와 동일합니다.
"""

import os
import sys
import datetime as dt

import backfill as bf   # 같은 폴더의 backfill.py 재사용


def main():
    # 키: 환경변수(DART_API_KEY) 우선, 없으면 실행 인자
    key = os.environ.get("DART_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not key or len(key) < 20:
        print("DART_API_KEY 가 없습니다. 환경변수 또는 실행 인자로 전달하세요.")
        sys.exit(1)

    days = int(os.environ.get("UPDATE_DAYS", "45"))   # 정정·지연공시 보완 위해 넉넉히
    today = dt.date.today()
    bgn = (today - dt.timedelta(days=days)).strftime("%Y%m%d")
    es = today.strftime("%Y%m%d")

    print(f"[update] 최근 {days}일 증분 갱신: {bgn} ~ {es}")
    bf.db_init()
    con = bf.db_connect()

    # 주요사항보고(B) 목록은 CB·BW 공용 → 한 번만 수집
    b_rows = bf.fetch_b_list(key, bgn, es)

    total = 0
    for kind, ep, kw in bf.KINDS:
        seen, corps = set(), []
        for r in b_rows:
            nm = r.get("report_nm") or ""
            cc = r.get("corp_code")
            if cc and cc not in seen and kw in nm:
                seen.add(cc)
                corps.append(cc)
        batch = []
        for cc in corps:
            try:
                drows = bf.get_detail(key, ep, cc, bgn, es)
            except Exception as e:
                print(f"    ! {cc} 건너뜀: {e}")
                drows = []
            for r in drows:
                rec = bf._parse_bond_detail(r, kind)
                if rec:
                    batch.append(rec)
        saved = bf.db_upsert(con, batch)
        total += saved
        print(f"  {kind}: 대상 {len(corps)}개사 · {saved}건 반영")

    bf.db_set_meta(con, "last_update", es)
    con.close()
    print(f"[update] 완료 — 총 {total}건 upsert, last_update={es}")


if __name__ == "__main__":
    main()
