# 코스닥 상장심사 사례집 (설치형 웹앱)

「코스닥 상장심사 이해와 실무」 2022~2026년판 심사사례 588건(고유 268건)을 검색하는 오프라인 웹앱입니다.

## GitHub Pages에 올리기
1. GitHub에서 새 저장소를 만듭니다(예: `kosdaq-cases`, Public).
2. 저장소 첫 화면의 **uploading an existing file**을 눌러 이 폴더 안의 파일을 모두 끌어다 놓고 Commit 합니다.
   (`index.html`, `manifest.webmanifest`, `sw.js`, `.nojekyll`, `icons/` 폴더)
3. **Settings → Pages**에서 Source를 `Deploy from a branch`, Branch를 `main` / `(root)`로 두고 Save.
4. 1~2분 뒤 `https://<아이디>.github.io/kosdaq-cases/` 주소가 열립니다.

## 안드로이드에 설치
1. 위 주소를 크롬으로 엽니다.
2. 메뉴(⋮) → **앱 설치**(또는 홈 화면에 추가) → 설치.
3. 앱 서랍에 '심사사례집' 아이콘이 생깁니다. 한 번 열어 두면 인터넷 없이도 열립니다.

## 내용 갱신
`index.html`을 새 파일로 바꿔 올리고 `sw.js`의 `VERSION` 값을 바꾸면, 폰에서 앱을 인터넷 연결 상태로 한 번 열 때 최신판으로 바뀝니다.

※ 공개 저장소의 GitHub Pages는 주소를 아는 사람 누구나 볼 수 있습니다(검색엔진 노출은 차단 설정됨).

---

# 신약 기술거래 딜북 (`deals/` 폴더, 별도 설치형 웹앱)

2021년 이후 총 계약규모 $200M 이상 글로벌 신약 기술거래(라이선스·옵션·공동개발·플랫폼) 검색과 단계별 조건 벤치마크.

- 주소: `https://<아이디>.github.io/kosdaq-cases/deals/`
- 안드로이드 설치: 위 주소를 크롬으로 열고 메뉴(⋮) → **앱 설치**. 앱 서랍에 '딜북' 아이콘이 생깁니다.
- 데이터: `deals/data/deals.json`(거래), `deals/data/runs.json`(업데이트 기록). 매월 1일 자동 작업이 갱신해 커밋합니다.
- 앱은 열 때마다 최신 데이터를 먼저 받아오고, 인터넷이 없으면 마지막으로 받은 데이터로 열립니다.
