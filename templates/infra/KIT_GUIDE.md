# 앱 실행과 수정

이 파일은 전체 앱 뼈대와 함께 업무 폴더에 설치된다. 기존 업무 README와 AGENTS.md의 요구를 먼저 확인한다.

## 실행

Python 3.11+ / Node 22.12+ 또는 24+를 사용한다. 기본 조합은 Python 3.11 / Node 24다.

```sh
make setup
make api    # 터미널 1, 8000
make ui     # 터미널 2, 5173
```

로컬 브라우저에서 `http://localhost:5173`을 연다. 웹 IDE를 사용하면 해당 환경의 포트 미리보기로 확인한다. 직접 명령은 다음과 같다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci --no-audit --no-fund
.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
# 다른 터미널
npm --prefix frontend run dev
```

단일 포트 실행: `make build` 후 `make serve`, 8000에서 화면과 API를 함께 제공한다. Docker가 허용되고 실행 중이면 `docker compose up --build`로 실행할 수 있다. 직접 실행의 저장은 `.local/app/app.sqlite3`, Docker는 named volume이다. 개발 포트를 변경하면 `frontend/vite.config.ts`의 프록시도 맞춘다.

## 상태와 API 안내

현재 서버 포트에서 `/health`는 프로세스 응답, `/api`는 API 목록, `/docs`·`/redoc`은 문서 UI, `/openapi.json`은 요청·응답 계약을 제공한다. 기존 `/api/health`는 호환용으로 유지한다. 5173 개발 서버도 이 경로를 8000으로 프록시한다.

목록은 현재 OpenAPI에서 생성하며 외부 리소스 없이 읽을 수 있다. Swagger/ReDoc UI는 외부 CDN을 사용한다. 문서 UI에서 쓰기 요청을 실행하면 실제 데이터를 변경할 수 있다. 상태 응답 성공은 DB·모델 준비나 업무 규칙 충족 검증을 의미하지 않는다.

로컬 단일 포트 예시는 `http://localhost:8000/health`, `http://localhost:8000/api`, `http://localhost:8000/docs`다. 웹 IDE에서는 실제 실행 포트와 경로를 내장 Browser에서 선택한다. 외부 공개 주소를 추정하지 않는다.

문서 공개를 끄려면 시작 전에 `ENABLE_API_DOCS=false`를 지정한다. 직접 실행은 `ENABLE_API_DOCS=false make serve`, Compose는 `ENABLE_API_DOCS=false docker compose up --build`를 사용할 수 있다. API 목록·문서 UI·스키마만 비활성화하며 업무 API의 인증/권한은 별도다.

업무 설명 README.md/readme.md는 보존하고 별도 SERVICE.md를 작성한다. 실제 컴포넌트 관계·아키텍처/대표 흐름 다이어그램·API 명세·업무/운영 규칙과 근거·검증·효과/한계, 실행 명령·접속 정보를 유지한다. 필수 RUN.md가 있으면 상세 절차를 연결한다. 이 안내의 기본 포트가 실제 실행 결과와 같다고 가정하지 않는다. Markdown API 명세 작성은 HTTP 문서 공개 설정을 변경하지 않는다.

## 검증

```sh
make test
make ml-deps
make test-ml
docker compose config --quiet
```

Docker 구성 검사와 이미지 빌드·실행은 서로 다른 검사다. CI는 API·검색·CSV·ML·프런트 테스트와 프런트 빌드를 수행한다. UI의 실제 클릭·좁은 화면·오류 복구는 현재 환경에서 허용된 브라우저 검사 또는 사용자 수동 확인으로 점검하고 수행한 범위를 구분한다.

## 코드 경로

| 사용자 동작 | 화면 | 서버·계산 |
| --- | --- | --- |
| 기록 추가·진행 변경·삭제 | frontend/src/App.tsx | backend/app/main.py → database.py |
| CSV 텍스트·그룹별 평균 | App.tsx → api.ts | data/analysis.py |
| 문서 등록·질문·출처 | App.tsx → api.ts | database.py → ai/rag.py |
| 분류·회귀·예측 CSV | CLI | data/train.py → predict.py |
| 시계열 기준선 | CLI | data/forecast.py |

RAG 기본은 BM25 검색과 원문 발췌다. `ai/generation.py`는 이미 허용된 모델 호출 함수를 주입하는 어댑터다. 기본 앱에 외부 모델·개인 키 연결은 없다. ML은 Dummy 기준선과 같은 분할로 비교하며, 시간/그룹/무작위 분할 중 실제 사용과 맞는 것을 고른다. 시계열은 한 개체·오름차순·일정 간격 데이터를 전제로 한다.

## 업무에 맞게 바꾸기

기본 화면은 내부 탭을 사용한다. CSV·문서는 페이지 안에 텍스트를 입력하며 네이티브 파일창·자동 다운로드·새 탭을 열지 않는다. API URL은 이 문서에서 확인한다. 전체화면 유지가 요구되면 UI 수정 후 정상·오류·닫기·출력의 이벤트 경로를 점검한다. 실제 확인은 허용된 준비 공간에서만 수행하고 감독 이벤트/로그·플랫폼 설정을 변경하지 않는다. 브라우저/OS까지 앱이 통제할 수는 없다.

SERVICE.md에 유스케이스·사용 흐름·구성도·화면/API 라우팅·모듈 계약·실제 코드 읽는 순서를 작성한다. 핵심 파일/함수·분기/계산·비동기 상태에는 한국어로 입력/단위·출력·이유·실패 주석을 남긴다. 최적화 기준과 독립 검사, 백그라운드 중복/실패/재시작 정책, 조건 변화 입력/지표는 해당 기능이 있을 때 실제 구현·미확인을 구분해 설명한다.

현재 앱은 단일 사용자용 뼈대다. 실제 용어·필수 계산·단위·데이터·인계 계약으로 교체한다. 인증·조직 권한·백업·대규모 작업 큐는 요구가 있을 때 구현한다. 예시 기능은 필수 기능과 연결되지 않으면 제거한다.

- React/TypeScript: 화면 상태·타입 확인을 빠르게 구성. 단순 정적 화면이면 HTML/JS, SSR이 필수면 서버 렌더링 대안을 비교.
- FastAPI/SQLite: 계약·API 문서·저장을 서버 하나로 제공. 다중 사용자·동시 쓰기 요구면 PostgreSQL 등 비교.
- BM25: 키·모델 다운로드 없는 근거 검색. 의미 검색이 중요하면 허용된 임베딩/하이브리드 검색을 평가.
- LogisticRegression/Ridge: 빠르고 읽기 쉬운 표 데이터 기준선. 비선형 관계면 트리/부스팅을 같은 검증 분할에서 비교.
- Docker: 한 컨테이너 전달·영속 볼륨. 제공 환경에서 직접 실행이면 Docker 없이 진행.

업무 시작 시 문제 상황을 입력하면 solve-task가 담당자에게 보낼 질문·확인 이유·구현 영향을 먼저 정리한다. 확인한 답변을 같은 대화에 입력하면 범위·업무 규칙·수용 기준을 반영한 뒤 예상 화면/결과물·사용 흐름·기능별 동작·데이터/설계·추천 기술과 대안·위험/검증·시간을 상세 브리핑한다. 사용자가 제시된 계획을 확인할 때까지 업무 코드·뼈대 적용을 기다린다. 확인 뒤 합의 범위를 구현하며 중요한 결과물/구조 변경은 다시 설명하고 확인받는다.

기본 집중 세션은 180분이며 0~60분 1차 구현·검증/자료 인계, 60~120분 보완/수정+코드 이해, 120~180분 변경 없는 코드 이해로 진행한다. 지연 시 1차 인계가 80분이 되어도 마지막 60분은 120분부터 유지한다. 마지막 구간에 새 기능·리팩터링·자동 오류 수정·장시간 문서 보완을 진행하지 않는다. 다른 기간/마감은 현재 사용자 지시를 따르고, 후속 문항 절차는 실제 안내가 있을 때만 별도로 적용한다.

devlog.md에는 실제 질문·답변·판단·변경·실행·실패·수정을 기록한다. probe.md에는 **페르소나→페인포인트→원인/근거→해결 원리→적용 기능/코드→기술 선택/대안→검증과 업무 효과**를 연결한다. 근거 없는 인물 설정·원인 단정·개선율은 만들지 않는다. 기본 표를 업무 판단의 근거로 대신하지 않는다.

원격 저장이 허용되는지 먼저 확인한다. `.local/`, `.venv/`, `.env`, `node_modules/`, 빌드 결과는 기존 `.gitignore`에 병합하고 비밀·원본 데이터·모델 파일을 무심코 추가하지 않는다. solve-task는 별도 설정 없이 기록 준비와 3분 간격 로컬 자동저장을 시작하고, 단계별로 devlog/probe를 갱신한다. 상태 확인과 종료는 solve-task/scripts/session.py의 status/stop을 사용한다. 인계 확정 전에 최종 사본과 종료를 확인한다. 실제 업무 코드를 공개 키트로 전송하지 않는다.

.agents 설치가 제한되면 공개 클론의 스킬·스크립트 경로를 직접 사용한다. 자동 세션은 `.git`을 수정하지 않고 업무 폴더의 `.local/ai-toolkit/snapshots/`에 저장한다. 앱 코드만 복사할 때는 install.py의 `--templates-only`를 사용한다. 일반 작업 폴더의 쓰기까지 차단되면 해당 오류를 알리고 관리 영역의 권한이나 설정을 바꾸지 않는다.
