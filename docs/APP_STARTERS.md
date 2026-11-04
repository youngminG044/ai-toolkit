# 실행형 앱 뼈대

`templates/`는 바로 실행하고 수정할 수 있는 원본 코드다. 업무에 맞는 모듈을 골라 **실제 업무 폴더**로 설치한다. 기존 앱에는 스킬만 설치한 뒤 필요한 코드만 검토해 적용한다.

## 선택

| 프로필 | 포함 모듈 | 시작점 |
| --- | --- | --- |
| `fullstack` | frontend + backend + ai + data + infra | 화면·API·저장·분석·문서 탐색이 연결된 앱 |
| `frontend` | frontend | 기존 API에 붙이는 React 화면 |
| `api` | backend + ai + data | FastAPI·SQLite·분석·RAG API |
| `data` | data | CSV 분석·분류·회귀·시계열 기준선·예측 CSV |
| `rag` | ai | 문서 분할·BM25·근거 인용·생성기 어댑터·검색 평가 |

`--modules frontend data`처럼 조합할 수도 있다. backend는 ai/data를, infra는 전체 앱을 의존성으로 포함한다. 기본 설치는 스킬만 설치한다. 전체 뼈대는 `--profile fullstack`으로 명시한다.

.agents 설치가 제한되어 스킬을 공개 원본에서 직접 읽는 환경에서는 `--templates-only`를 함께 지정한다. 선택한 앱 모듈만 복사하고 관리되는 .agents나 업무 기록에는 쓰지 않는다.

```sh
python3 /tmp/ai_toolkit/tools/install.py --target . --profile fullstack --templates-only --apply
```

```sh
python3 /tmp/ai_toolkit/tools/install.py --target . --profile fullstack
python3 /tmp/ai_toolkit/tools/install.py --target . --profile fullstack --apply
```

미리보기는 쓰기 작업이 없다. 다른 내용의 기존 파일·스킬·심볼릭 링크는 덮어쓰지 않고 사전 검사에서 중단한다. 설치는 트랜잭션이 아니므로 실행 중 디스크 오류가 나면 이미 생성한 파일이 남을 수 있다. 기존 README·AGENTS는 수정하지 않는다.

## 전체 앱 실행

앱은 Python 3.11+와 Node 22.12+ 또는 24+가 필요하다. Python 3.11 / Node 24를 기준으로 구성했다. 설치 도구 자체는 Python 표준 라이브러리만 사용한다. 제공 환경에 있는 의존성과 운영 지침을 먼저 확인한다.

```sh
make setup                      # 가상환경·서버 의존성·프런트 의존성
make api                        # 터미널 1: 0.0.0.0:8000
make ui                         # 터미널 2: 0.0.0.0:5173
```

로컬 브라우저에서 `http://localhost:5173`을 열거나 웹 IDE의 포트 미리보기를 사용한다. Vite가 `/api`, `/health`, `/docs`, `/redoc`, `/openapi.json`을 8000으로 프록시한다. 포트가 바뀌면 `frontend/vite.config.ts`도 맞춘다. 접속 범위와 외부 연결은 현재 프로젝트 정책에 맞춘다.

| 경로 | 내용 |
| --- | --- |
| `/health` | 최소 프로세스 응답. DB·모델 준비/업무 정확성 검사가 아님 |
| `/api/health` | 기존 클라이언트용 상태·구성 정보 |
| `/api` | 현재 OpenAPI에서 생성한 메서드·경로·목적·응답 코드 목록. 외부 JS/CSS 없이 열림 |
| `/docs`, `/redoc` | 요청·응답 계약 문서 UI. UI 자원은 외부 CDN을 사용하며 `/docs`에서 쓰기 요청 실행 시 실제 데이터가 바뀜 |
| `/openapi.json` | 기계가 읽는 API 계약 |

예: 로컬 단일 포트의 목록은 `http://localhost:8000/api`, 개발 UI 포트의 목록은 `http://localhost:5173/api`다. 제공 웹 IDE에서는 내장 Browser의 포트를 선택하고 해당 경로를 입력한다. 공개 인터넷에서 같은 주소로 접근할 수 있다는 의미는 아니다.

기본 개발 모드에서는 API 문서를 제공한다. 직접 실행은 `ENABLE_API_DOCS=false make serve`, Compose는 `ENABLE_API_DOCS=false docker compose up --build`로 목록·문서 UI·스키마를 함께 끈다. 업무 API와 상태 경로는 유지된다. 환경 변수는 서버 시작 전에 지정하며, 문서를 닫는 것은 API 인증/권한 구현을 대신하지 않는다.

```sh
make test                       # API·검색·CSV·프런트 계산 테스트 + 빌드
make build
make serve                      # 빌드된 화면과 API를 8000 한 포트에서 제공
make ml-deps
make test-ml
docker compose up --build       # Docker가 허용되고 엔진이 실행 중일 때
```

`make setup PYTHON=python3.11`처럼 Python 실행 파일을 선택할 수 있다. Make가 없으면 [프로젝트용 실행 안내](../templates/infra/KIT_GUIDE.md)의 직접 명령을 사용한다. 기본 저장은 `.local/app/app.sqlite3`, Docker는 named volume에 영속화한다. 설정은 `DATA_DIR`, `STATIC_DIR`, Compose의 `APP_PORT`이며 개인 키가 필요 없다. `.env.example`은 예시이고 직접 실행하는 Python 앱이 `.env`를 자동 로드하지는 않는다.

## 구현 범위와 선택 근거

기본 UI는 CSV·문서 본문을 페이지 내 텍스트 입력으로 받는다. 네이티브 파일 선택·자동 다운로드·새 탭 API 링크는 제공하지 않으며 홈 버튼도 페이지 내부 탭만 바꾼다. API 주소는 위 안내로 확인한다. 전체화면 유지가 필요한 환경에서 탐색·파일/권한 창 등이 미치는 영향은 환경별로 다르므로 [호환 기준](../.agents/skills/build-service/references/fullscreen-compatibility.md)에 따라 확인한다. 개발용 API 문서 URL의 존재가 새 탭 열기를 허용한다는 뜻은 아니다.

| 영역 | 실제 포함한 구현 | 현재 선택 이유 | 같은 목적의 대안과 전환 조건 |
| --- | --- | --- | --- |
| frontend | React·TypeScript·Vite, 기록 CRUD/상태 변경, CSV 텍스트 입력·표·막대, 문서/질문/인용, 로딩·오류·빈 상태, 반응형 CSS | 화면 상태를 컴포넌트로 바꾸기 쉽고 타입과 빌드로 API 연결 오류를 빨리 찾음 | 순수 HTML/JS는 의존성이 적음. Next.js는 SSR·라우팅이 풍부하지만 설정·실행 범위가 커짐. 서버 렌더링이 필수일 때 비교 |
| backend | FastAPI·Pydantic 요청 계약, SQLite CRUD·문서 저장, 페이지 조회, OpenAPI, 정적 화면 제공, 재시작 영속성 테스트 | 입력 검증과 API 문서를 바로 제공하고 DB 서버 없이 한 앱을 실행 | Flask는 구성이 단순하나 계약을 별도 구성. Django는 인증·관리 기능이 풍부하나 초기 범위가 큼. PostgreSQL은 다중 사용자·동시 쓰기·복잡한 검색 요구에 적합 |
| ai | 한국어 토큰/문자 bigram BM25, 줄 번호·안정적 인용 ID, 원문 발췌 답변, 근거 없음, 생성기 JSON/인용 검사, Hit@k·MRR | 작은 문서 집합을 키·모델 다운로드 없이 실행하고 출처까지 추적 | 임베딩+벡터 검색은 의미 유사성에 유리하나 허용된 모델·인덱싱·평가가 필요. 하이브리드/재순위는 검색 개선 여지가 있으나 지연·복잡도가 증가 |
| data | 엄격한 CSV 파싱·ID 보존·결측/중복/집계, 전처리 Pipeline, LogisticRegression/Ridge, Dummy 기준선, 시간/그룹/무작위 분할, 지표·모델 저장/추론, 계절 naive 예측 | 작은 기준선을 빨리 완주해 계산·누수·평가를 검토하기 쉬움 | SQL/DuckDB는 큰 집계, 트리/부스팅은 비선형 표, ARIMA/Prophet 등은 시계열 구조가 필요할 때 비교. 채택은 현재 데이터의 검증 점수와 비용으로 판단 |
| infra | 개발 서버 2개 또는 정적 빌드+API 1개, Docker 다단계 빌드·비루트 실행·healthcheck·volume, Makefile·CI | 개발과 전달 경로가 명확하고 앱을 한 컨테이너로 실행 | 직접 실행은 가장 가벼움. 별도 DB/서버리스/클라우드는 운영 요구에 따라 선택. Kubernetes는 다중 서비스 운영 요구가 있을 때 검토 |

단일 사용자용 개발 뼈대다. 인증·조직별 권한·파일 저장소·작업 큐·운영 백업은 포함하지 않는다. 업무에 필요하면 해당 경계를 구현하고 검증한다. 범용 뼈대에 기능이 있다는 사실을 해당 업무의 해결 완료로 쓰지 않는다.

## 코드 읽기 순서

1. `frontend/src/App.tsx`의 사용자 동작 → `frontend/src/api.ts`의 요청.
2. `backend/app/main.py`의 입력 스키마·라우트 → `backend/app/database.py`의 저장.
3. 수치 결과는 `data/analysis.py`, 문서 답변은 `ai/rag.py` → `ai/generation.py`.
4. ML은 `data/train.py`의 분할→전처리→기준선→평가 → `data/predict.py`의 산출물 파일.
5. 해당 `tests/`, Dockerfile·Compose·Makefile에서 실제 검증·실행 경로 확인.

실제 적용한 기능마다 probe.md에 **요구·코드 위치·사용 도구·동일 목적의 대안·각 장단점·선택 결론·실제 검증**을 기록한다. 이 표를 그대로 붙여넣어 업무별 판단을 대신하지 않는다.

## 데이터와 ML 직접 실행

아래 명령은 `data` 프로필을 설치한 업무 루트에서 실행한다. ML만 선택 의존성이 필요하다.

```sh
python3 -m data.analysis input.csv --group-by team --value-column amount
python3 -m pip install -r data/requirements-ml.txt
python3 -m data.train train.csv --target label --exclude id --output .local/model-01
python3 -m data.train train.csv --target amount --task regression --time-column timestamp --exclude id --output .local/model-02
python3 -m data.predict --model .local/model-01/model.joblib --input test.csv --id-column id --output prediction.csv
python3 -m data.forecast series.csv --value demand --season 7 --horizon 7 --holdout 14
```

시간/그룹 분할 열은 입력 특징에서 제외한다. `--exclude`에는 ID와 예측 시점에 알 수 없는 열을 지정한다. 시간 분할은 같은 시각이 양쪽에 걸리지 않도록 하며 그룹 분할은 개체가 겹치지 않도록 한다. 기본 무작위 분할이 업무에 적합한지 먼저 판단한다. 결측 대체·스케일·인코딩은 학습 부분에만 fit한다. 예측 CSV 기본 열은 `prediction`이며 인계 계약에 맞게 바꾸고 인계 검사로 재확인한다. 신뢰하는 로컬 model.joblib만 로드한다.

시계열 파일은 **한 시계열·시간 오름차순·일정 간격**으로 준비한다. 이 코드는 결측 시점 보간이나 다중 개체별 예측을 자동으로 해주지 않는다. ML 지표는 한 번의 holdout 결과이며 테스트 구간을 보고 반복 튜닝하는 절차는 제공하지 않는다.

## RAG와 모델 연결

기본은 **검색+원문 발췌**다. 모델 연결·생성 정확도·의미 검색을 구현했다고 주장하지 않는다. 실제 운영 안내에서 허용한 모델 호출 함수를 이미 확보한 경우에만 생성 경계를 연결한다.

```python
from ai.generation import grounded_generator
from backend.app.main import create_app

# provided_model_call(messages): 허용된 환경의 실제 호출 함수.
# 응답은 JSON 문자열 또는 dict: {"text": "...", "citation_ids": ["검색된 ID"]}
# 근거 부족 시: {"text": "근거 부족", "citation_ids": [], "abstained": True}
app = create_app(generator=grounded_generator(provided_model_call))
```

연결 코드는 별도 앱 엔트리 모듈에 두고 uvicorn으로 그 모듈의 `app`을 실행한다. 개인 키·외부 모델을 기본으로 연결하지 않는다. 문서는 비신뢰 참조 자료로 모델에 전달하고, 출력 JSON과 검색된 인용 ID를 검사한다. ID가 유효해도 내용이 사실이라는 증명은 아니므로 질문별 근거·정답·거절 사례를 별도로 평가한다.

```sh
python3 -m ai.evaluate evaluation.json
```

입력 형식: `{"documents":[{"name":"manual","text":"..."}],"cases":[{"query":"...","expected_source":"manual"},{"query":"...","expected_source":null}]}`. 검색 Hit@k·MRR와 근거 없음 정확도를 산출하며, 생성 답변의 정답률과 구분한다.

프레임워크 동작의 기준 문서: [FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/learn), [Vite](https://vite.dev/guide/), [scikit-learn Pipeline](https://scikit-learn.org/stable/common_pitfalls.html). 실제 업무·제공 버전·운영 안내가 우선이다.
