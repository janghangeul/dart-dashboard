# 안다아시아벤처스 · Mezzanine Look-up & Analysis — 온라인 배포 가이드

이 문서는 **내 PC에서만 돌아가던 대시보드를 인터넷(온라인)에서도 열 수 있게** 만드는 방법을,
코딩을 전혀 몰라도 따라 할 수 있도록 순서대로 설명합니다.

---

## 0. 큰 그림 — 무엇을, 왜 하는가

지금은 내 PC에서 `streamlit run app.py` 를 켜야만 대시보드가 보입니다. (내 PC를 끄면 안 보임)

온라인으로 만들려면 **두 가지**가 필요합니다.

1. **GitHub(깃허브)** — 내 코드(app.py 등)를 인터넷 저장소에 올려두는 곳. (구글 드라이브의 '코드 버전'이라고 생각하세요)
2. **Streamlit Community Cloud** — 그 GitHub 코드를 읽어서 **24시간 켜진 웹사이트로 띄워 주는 무료 서비스**.

> 흐름: **내 PC의 파일 → GitHub에 올림 → Streamlit Cloud가 GitHub를 읽어 웹사이트로 실행 → 팀원은 링크로 접속**

그리고 **키(비밀번호) 보안**이 핵심입니다. DART 인증키·Anthropic 키는 **코드와 분리해서, 깃허브에 올리지 않고, Streamlit Cloud에만 따로 넣습니다.** (인턴분이 말한 `.env`/`.gitignore` 개념과 같습니다 — 아래 2번에서 자세히)

---

## 1. 올릴 파일 준비 (폴더 구성)

깃허브에 올릴 폴더(예: `dart-dashboard`)는 아래처럼 생겨야 합니다.

```
dart-dashboard/
├─ app.py                      ← 대시보드 본체
├─ backfill.py                 ← 발행내역 DB 적재 스크립트(로컬에서만 실행)
├─ requirements.txt            ← 필요한 라이브러리 목록
├─ README.md                   ← (이 파일)
├─ .gitignore                  ← '올리면 안 되는 파일' 목록
├─ dart.db                     ← (선택) 발행내역 DB. 올리면 온라인에서도 빠름
└─ .streamlit/
   ├─ config.toml              ← 화면 테마 설정
   └─ secrets.toml.example     ← 키 예시(실제 키 X, 올라가도 안전)
   # secrets.toml  ← 실제 키 파일. 있으면 '절대' 올리지 않음(.gitignore가 막아줌)
```

- 제가 드린 `.gitignore`, `.streamlit/config.toml`, `.streamlit/secrets.toml.example` 을 기존 폴더에 넣으세요.
- `app.py`, `backfill.py`, `requirements.txt` 는 이미 가지고 계신 최신본을 씁니다.

---

## 2. 🔑 보안 — 키는 이렇게 다룹니다 (가장 중요)

**원칙: 실제 키(DART·Anthropic)는 코드/깃허브에 절대 넣지 않는다.**

- **왜?** 깃허브는 (공개 저장소면) 누구나 볼 수 있어, 키가 올라가면 남이 내 키로 비용을 쓰거나 악용할 수 있습니다. 치명적입니다.
- **어디에 두나?**
  - **내 PC(로컬)**: `.streamlit/secrets.toml` 파일에 넣습니다. 이 파일은 `.gitignore` 에 등록돼 있어 **깃허브에 안 올라갑니다.** (인턴분이 말한 `.env` 와 같은 역할 — Streamlit은 `.env` 대신 `secrets.toml` 을 씁니다)
  - **온라인(Streamlit Cloud)**: 파일로 올리지 않고, **Streamlit Cloud 화면의 'Secrets' 입력칸**에 붙여넣습니다. (아래 5번)
- 앱 코드(`app.py`)는 이미 이렇게 동작합니다:
  - secrets에 키가 있으면 → 자동으로 채워 사용
  - 없으면 → 사이드바에서 사용자가 직접 입력
  - 즉 **키가 코드 안에 하드코딩돼 있지 않습니다.** (안전)

> ✅ 정리: 깃허브에 올라가는 것 = app.py, requirements.txt, config.toml, .gitignore, secrets.toml.**example**(예시), (선택)dart.db
> ❌ 절대 안 올라가는 것 = 실제 키가 든 **secrets.toml**, .env

---

## 3. GitHub에 올리기

> 명령어(터미널) 없이 할 수 있는 **GitHub Desktop(데스크톱 앱)** 방식을 권장합니다.

### 3-1. GitHub 계정 만들기
1. https://github.com 접속 → **Sign up** → 이메일·비밀번호로 가입(무료).

### 3-2. GitHub Desktop 설치
1. https://desktop.github.com 에서 다운로드·설치 → 방금 만든 계정으로 로그인.

### 3-3. 저장소(repository) 만들고 파일 올리기
1. GitHub Desktop → `File → New repository`
2. Name: `dart-dashboard`, Local path: **내 대시보드 폴더의 상위 폴더**를 지정(또는 폴더를 그대로 끌어다 넣기).
   - 더 쉬운 방법: `File → Add local repository` 로 **기존 dart-dashboard 폴더를 통째로** 선택해도 됩니다.
3. 창 왼쪽 아래에 올라갈 파일 목록이 뜹니다.
   - **여기서 `secrets.toml` 이 목록에 보이면 안 됩니다.** (`.gitignore` 가 있으면 자동으로 빠집니다. 혹시 보이면 멈추고 알려주세요.)
4. 아래 `Summary` 칸에 `first commit` 입력 → **Commit to main** 클릭.
5. 오른쪽 위 **Publish repository** 클릭.
   - **'Keep this code private' 체크 권장**(사내용). → **Publish** 클릭.

이제 내 코드가 GitHub에 올라갔습니다.

> (대안) 앱이 설치하기 번거로우면 github.com 에서 `New repository` 만든 뒤, 'uploading an existing file' 로 **파일을 드래그&드롭**해도 됩니다. 단, `.streamlit` 폴더와 `.gitignore` 같은 점(.)으로 시작하는 파일은 웹 업로드가 까다로우니 Desktop 방식을 권장합니다.

---

## 4. Streamlit Community Cloud 로 배포

1. https://share.streamlit.io 접속 → **Continue with GitHub** 로 로그인(방금 만든 계정 연결/허용).
2. **Create app → Deploy a public app from GitHub** (또는 'Yup, I have an app') 클릭.
3. 입력:
   - **Repository**: `본인아이디/dart-dashboard`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **Deploy!** 클릭 → 잠깐 기다리면(수십 초~몇 분) 설치가 끝나고 대시보드가 뜹니다.
   - 설치 중 오류가 나면 보통 `requirements.txt` 문제입니다. 화면 로그를 캡처해 알려주시면 잡아드릴게요.

배포되면 `https://이름.streamlit.app` 같은 **고정 주소(URL)** 가 생깁니다. 이 링크를 팀원에게 주면 접속 가능합니다.

---

## 5. 🔑 Secrets(키) 넣기 — 배포 후 1회

1. 배포된 앱 화면 오른쪽 아래 **⋮ (Manage app)** 또는 streamlit.io 대시보드에서 내 앱 → **Settings → Secrets**.
2. 입력칸에 아래를 **실제 키로 바꿔서** 붙여넣고 **Save**:
   ```
   DART_API_KEY = "실제_DART_인증키_40자리"
   ANTHROPIC_API_KEY = "실제_Anthropic_키"
   ```
3. 저장하면 앱이 자동 재시작되고, 사이드바 키 입력칸이 **자동으로 채워집니다.**

> 이렇게 하면 **키는 Streamlit Cloud 안에만 저장**되고, 깃허브·코드 어디에도 노출되지 않습니다.

---

## 6. 🔒 아무나 못 들어오게 — 접근 제한(사내 공유)

**중요**: Secrets에 Anthropic 키를 넣으면, 그 앱을 여는 **누구나 내 키로 AI 기능(=비용)을 쓸 수 있습니다.** 그래서 **반드시 접근 제한**을 거세요.

- Streamlit Cloud → 앱 → **Settings → Sharing** 에서 **"Only specific people can view this app"** 로 바꾸고, **팀원 이메일**(구글/깃허브 계정)을 초대합니다.
- 그러면 초대받은 사람만 로그인해서 볼 수 있습니다.

> 만약 "회사 전체에 공개하되 비용은 막고 싶다" 면 → Secrets에 Anthropic 키를 **넣지 말고**, 각자 사이드바에 자기 키를 입력하게 하면 됩니다. (앱은 그 경우도 지원)

---

## 7. 데이터(발행내역 DB)와 주가 — 온라인에서의 한계와 운영법

온라인(무료 클라우드)은 **디스크가 임시**라서, 몇 가지 알아둘 점이 있습니다.

- **발행내역 DB(dart.db)**
  - 클라우드에서는 `backfill.py`(30분~2시간짜리)를 **돌릴 수 없고**, '데이터 관리' 탭의 적재/업데이트도 **다시 켜지면 사라집니다.**
  - ✅ **해결**: 내 PC에서 `backfill.py` 로 `dart.db` 를 만든 뒤, **그 `dart.db` 를 깃허브에 함께 올리세요.** (공개 DART 자료라 보안 문제 없음)
    - 그러면 온라인 앱이 그 DB를 읽어 **스크리너·후보·Analysis가 빠르게** 나옵니다.
    - 데이터를 갱신하려면: 내 PC에서 `backfill.py` 다시 실행 → 바뀐 `dart.db` 를 깃허브에 다시 올림(Commit→Push) → 앱 자동 반영.
  - `dart.db` 없이 올리면: 앱은 돌아가지만 DB가 비어, 조회 시 **매번 DART에서 실시간**으로 받아 느립니다(기간을 짧게 쓰면 OK).
- **주가(밸류에이션 탭)**: FinanceDataReader가 **조회할 때마다 실시간**으로 받으므로 별도 관리 불필요. 다만 클라우드(해외 서버)에서 간혹 느리거나 막힐 수 있으니, 안 되면 알려주세요(대체 소스 적용).

---

## 8. 코드/데이터를 고친 뒤 온라인에 반영하기

1. 내 PC에서 `app.py`(또는 `dart.db`) 수정/교체.
2. GitHub Desktop → 바뀐 파일이 목록에 뜸 → `Summary` 입력 → **Commit to main** → **Push origin**.
3. Streamlit Cloud가 **자동으로 감지해 재배포**합니다. (1~2분 후 새로고침)

---

## 9. 자주 겪는 문제

- **"키가 노출될까 봐 걱정"** → `.gitignore` 에 `secrets.toml`, `.env` 가 들어 있으면 실제 키 파일은 절대 안 올라갑니다. GitHub Desktop 커밋 목록에 `secrets.toml` 이 보이지 않는지만 확인하세요.
- **배포 중 빨간 에러** → 대개 `requirements.txt` 문제. 로그 캡처해서 공유해 주세요.
- **AI 기능이 안 됨** → Settings → Secrets 에 `ANTHROPIC_API_KEY` 넣었는지 확인.
- **발행내역이 느림/비어 있음** → `dart.db` 를 깃허브에 올렸는지 확인(7번).
- **주가 조회 실패** → 클라우드에서 FinanceDataReader가 막힌 경우일 수 있음(알려주시면 대체).

---

### 요약 체크리스트
- [ ] `.gitignore`, `.streamlit/config.toml`, `secrets.toml.example` 폴더에 추가
- [ ] (권장) 로컬에서 `backfill.py` 실행해 `dart.db` 생성
- [ ] GitHub Desktop 으로 **private** 저장소에 올리기 (secrets.toml 안 올라가는지 확인)
- [ ] Streamlit Cloud 에서 `app.py` 배포
- [ ] Settings → **Secrets** 에 실제 키 2개 입력
- [ ] Settings → **Sharing** 에서 팀원만 접근 가능하게 제한
