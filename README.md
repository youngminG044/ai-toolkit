# AI Toolkit

담당자와 업무 문제·요구를 확인하고 서비스·AI·데이터 구현, 검증·운영 설명과 인계까지 진행하는 **Codex 스킬 + 실행형 앱 뼈대**입니다.

현재 업무의 사용자·목표·운영규칙·완료 기준을 근거로 판단합니다. 업무 범위·예상 소요·마감·담당자 검토 일정을 확인하고 아래의 사용자 지정 기본 집중 세션과 현재 업무 조건을 함께 반영합니다. 특정 환경 규정은 해당 안내가 있는 경우에만 적용합니다.

## 기본 집중 세션: 180분을 60·60·60으로

사용자가 지정한 시간 운영안입니다. 담당자와 협업하는 업무 관점을 유지하면서 다음 구간을 지킵니다. 전체 프로젝트의 기간을 180분으로 제한하는 의미는 아니며 현재 사용자가 다른 기간을 명시하면 그 조건을 우선합니다.

| 경과 | 진행 |
| --- | --- |
| 0~60분 | 문제 분석·담당자 질의응답·상세 브리핑/계획 확인·1차 구현과 대표 검증, 읽을 자료 인계 |
| 60~120분 | 디벨롭·수정/보완과 코드 이해 병행. 관련 검증과 문서 정합 마무리 |
| 120~180분 | 온전히 코드 이해. 기능 추가·리팩터링·자동 오류 수정 중단, 현재 코드와 준비된 자료로 설명·추적 |

지연 시 1차 인계는 80분을 대안으로 하되 마지막 구간은 120~180분으로 유지합니다. 발견한 오류를 자동 수정하며 이해 시간을 사용하지 않습니다. 별도 후속 문항이 안내된 경우의 6문항·문항별 5분·총 30분과 도구 사용 조건은 [후속 절차 참고](.agents/skills/solve-task/references/followup-guidance.md)에 보존했으며, 180분과의 포함 관계·현재 마감은 실제 안내로 확인합니다. [시간 계획 상세](.agents/skills/solve-task/references/time-budget.md)를 따릅니다.

## Codex에서 한 문장으로 시작

업무 폴더에서 실행 중인 Codex에 다음처럼 입력합니다.

```text
https://github.com/ji0x0/ai_toolkit 를 설치해서 스킬을 파악하고 시작해줘
```

**이 요청을 받은 Codex는 [BOOTSTRAP.md](BOOTSTRAP.md)를 읽고 실행합니다.** 실제 업무 폴더를 보존한 채 키트를 `/tmp/ai_toolkit`에 받아 `tools/bootstrap.py --target <실제 업무 루트>`로 준비합니다. 스킬 설치가 허용되면 설치하고, .agents 쓰기가 제한되면 공개 원본을 직접 읽는 reference 모드로 반환합니다. 스킬 목록·설명을 파악하고 반환된 `entry_path`의 solve-task/SKILL.md를 읽어 **현재 대화에서** 이어갑니다. Codex를 다시 실행하지 않습니다.

문제 상황·업무 목표가 대화나 업무 README에 있으면 그 내용을 사용하고, 없으면 간단히 입력하도록 요청합니다. 이후 기록·자동저장 준비, 담당자 질문과 답변 반영, **구현 전 상세 브리핑·사용자 계획 확인**, 합의한 범위의 구현·검증으로 진행합니다. 이 안내는 요청을 해석한 Codex가 실행하는 절차이며 전역 자연어 명령을 등록하는 기능은 아닙니다.

reference 모드는 “스킬 설치 완료”가 아닙니다. 반환된 원본 스킬·스크립트 경로를 직접 사용하며 필요한 단계에서 해당 스킬을 읽습니다. 일곱 스킬이 준비됐다는 사실과 모두 실행했다는 주장은 구분합니다. 관리 폴더의 권한·마운트·전역 설정은 바꾸지 않습니다. 이미 읽기 전용임을 확인했다면 `bootstrap.py --target <업무 루트> --mode reference`로 시작할 수 있습니다.

| 영역 | 포함 코드 |
| --- | --- |
| frontend | React·TypeScript·Vite, 기록 CRUD·CSV 분석 화면·차트·문서 질문/인용·반응형 UI |
| backend | FastAPI·Pydantic·SQLite, 입력 검증·영속 저장·페이지 조회·OpenAPI·정적 화면 제공 |
| ai | BM25 문서 검색·한국어 토큰·근거 인용·근거 부족 처리·생성기 어댑터·검색 평가 |
| data | CSV 품질·그룹 집계, 분류·회귀·Dummy 비교, 시간/그룹 분할, 모델 저장/추론·시계열 기준선 |
| infra | Docker 다단계 빌드·Compose·영속 볼륨·healthcheck·Makefile·CI |

뼈대의 기록·분석·문서 탐색은 서로 연결되어 실행됩니다. 업무의 필수 기능으로 바꾸고 해당 업무의 데이터·수용 기준으로 검증합니다. [모듈별 구현·선택 근거·실행 안내](docs/APP_STARTERS.md)를 참고합니다.

서버/API가 있는 웹서비스를 구현할 때는 상태 URL·API 안내·실제 접속 정보도 함께 준비합니다. FastAPI 뼈대의 기본 경로는 `/health`, `/api`, `/docs`, `/redoc`, `/openapi.json`이며 기존 `/api/health`도 유지합니다. API 목록은 현재 라우트 계약에서 생성합니다. `ENABLE_API_DOCS=false`로 목록·문서 UI·스키마를 함께 끌 수 있고 업무 API의 인증·권한은 별도로 다룹니다. 실제 업무의 SERVICE.md에 포트·경로·확인 결과를 유지하고 필수 실행 문서는 연결합니다. [상태·API 안내 적용 기준](.agents/skills/build-service/references/service-access.md)을 참고합니다.

MCP·플러그인은 현재 도구로 접근할 수 없는 자료나 기능이 필요할 때 선택합니다. 앱 구현·CSV 분석·API 문서 생성에 필수는 아닙니다. [연결 선택 기준](.agents/skills/solve-task/references/tool-connections.md)에 따라 필요한 도구만 확인하며 일괄 설치하지 않습니다.

## 실제 업무 작업환경에 설치

아래 명령은 **실제 업무의 작업 폴더**에서 실행합니다. 키트는 별도 경로에 받습니다.

```sh
git clone --depth 1 https://github.com/ji0x0/ai_toolkit.git /tmp/ai_toolkit
python3 /tmp/ai_toolkit/tools/start.py --target .
```

시작 도구는 일곱 스킬을 설치하고 **제공된 Codex**에 짧은 시작 요청을 전달합니다. Codex는 업무 README·기존 지침·인계 제한을 읽은 뒤 기록 파일과 3분 간격 로컬 자동저장을 준비하고 **문제 입력→담당자 질문→답변 반영→상세 구현 브리핑→사용자 계획 확인→구현→검증→코드 이해 인계**로 진행합니다. 업무 답변과 설계 확인은 별도이며 확인 전에는 업무 코드·뼈대를 적용하지 않습니다. 모델·인증·Codex 버전·플랫폼 설정은 변경하지 않습니다. 설치 충돌은 덮어쓰지 않고 알립니다.

이미 Codex를 실행 중이면 위의 한 문장 설치 요청을 사용합니다. 수동으로 설치했다면 입력란에 `$solve-task`만 입력할 수도 있습니다. 스킬 인식이 안 되면 `.agents/skills/solve-task/SKILL.md를 읽고 실행해줘`라고 요청합니다. 실행 중인 Codex 안에서 start.py를 사용하지 않습니다.

설치를 먼저 검토하려면 다음 명령을 사용합니다.

```sh
python3 /tmp/ai_toolkit/tools/install.py --target .
python3 /tmp/ai_toolkit/tools/install.py --target . --apply
codex '$solve-task'
```

첫 설치 명령은 미리보기입니다. `--apply`하면 스킬을 작업 폴더의 `.agents/skills/`에 설치하고 **그 작업 폴더에 devlog.md와 probe.md를 생성**합니다. 기존 README·AGENTS·소스·기록 파일은 덮어쓰지 않습니다. 배포용 키트 폴더는 설치·기록 생성 대상으로 사용할 수 없습니다.

같은 이름의 다른 스킬이 있으면 자동 교체하지 않고 충돌을 알립니다. 선택 설치는 `--skills solve-task verify-result git-checkpoint`처럼 지정합니다. solve-task는 기록·저장에 필요한 record-work와 git-checkpoint를 함께 설치합니다. 업무가 추가 기록 파일을 금지하면 `--skip-records`로 설치하고 자동 세션에는 `--no-records`를 적용해 허용된 문서의 구획으로 관리합니다. start.py는 이 판단을 위해 업무 확인 전 기록 파일을 만들지 않습니다.

## 실행형 앱까지 설치

새 앱이 필요한 경우 실제 업무 폴더에서 프로필을 지정합니다. 기존 소스가 있다면 먼저 스킬만 설치하고 필요한 모듈을 선택합니다.

```sh
python3 /tmp/ai_toolkit/tools/install.py --target . --profile fullstack
python3 /tmp/ai_toolkit/tools/install.py --target . --profile fullstack --apply
make setup
make api    # 터미널 1: 8000
make ui     # 터미널 2: 5173
```

앱은 Python 3.11+ / Node 22.12+ 또는 24+가 필요합니다. 로컬 브라우저의 `http://localhost:5173` 또는 웹 IDE의 포트 미리보기에서 확인합니다. `make build` 후 `make serve`는 화면과 API를 8000 한 포트로 제공합니다. Docker는 선택입니다. `--profile api`, `--profile frontend`, `--profile data`, `--profile rag` 또는 `--modules frontend data`도 가능합니다. backend는 ai/data를 자동 포함합니다.

기존 파일이 다른 내용이면 덮어쓰기 전에 충돌을 알립니다. 의존성 설치·서버 실행·업무별 변경은 실제 작업환경에서 수행합니다. 기본 RAG는 **검색+원문 발췌**이며 실제 모델 생성은 허용된 호출 함수를 연결해야 합니다. 인증·조직별 권한·운영 백업은 업무 요구에 맞게 추가합니다.

스킬을 원본에서 직접 참조하는 환경에서는 `.agents`를 건드리지 않고 필요한 앱 코드만 복사합니다.

```sh
python3 /tmp/ai_toolkit/tools/install.py --target . --profile api --templates-only --apply
```

## 스킬

| 호출 | 역할 |
| --- | --- |
| `$solve-task` | 목표·요구·가정·담당자 질문·수용 기준·실행 계획 |
| `$build-service` | 기존 스택 또는 선택한 앱 뼈대의 UI·API·데이터 연결과 오류 처리 |
| `$analyze-data` | 데이터 의미·품질·누수·평가·수치 해석 |
| `$verify-result` | 요구별 검증·실패 조사·CSV 산출물 계약 검사 |
| `$explain-work` | 코드 추적·직접 실행·선택 이유와 한계 설명 |
| `$git-checkpoint` | Git 컨벤션·로컬 스냅샷·복구 |
| `$record-work` | 업무 작업환경의 devlog.md·probe.md 생성과 갱신 |

새로 설치한 스킬의 발견 여부는 제공 환경에서 확인합니다. 자동 발견이 안 되면 설치된 SKILL.md를 명시적으로 읽고 같은 대화에서 적용합니다. 이 설치·인계 흐름은 Codex 재실행이나 버전 업데이트를 요구하지 않습니다.

## 업무 시작 요청

```text
$solve-task
문제 상황: 업무에서 받은 설명
업무 목표: 요구된 목표와 결과물
```

문제 설명이 README나 기존 대화에 있으면 `$solve-task`만 입력해도 됩니다. 이 한 번의 호출에 아래 협업 흐름과 기록·자동저장이 포함됩니다. 예상 시간은 현재 범위·환경·외부 의존성을 근거로 제안하고 업무 마감·담당자 검토·사용자 코드 이해 시간을 함께 계획합니다.

1. **문제 정의·질문 제안:** 페르소나·페인포인트·원인 가설을 정리하고, 사용자가 업무 담당자에게 보낼 질문과 확인 이유·우선순위·구현 영향을 제안합니다. 첫 응답에서는 업무 기능 코드나 앱 뼈대를 작성·설치하지 않습니다.
2. **답변 전달·반영:** 사용자가 담당자에게 질문한 뒤 실제 답변을 같은 Codex 대화에 입력합니다. Codex는 답변·근거·충돌·열린 질문과 요구/수용 기준을 갱신합니다. 기존 대화에서 확인된 것을 다시 묻지 않습니다.
3. **상세 브리핑·사용자 확인:** 답변 반영 뒤 완성될 결과물의 모습과 사용 시나리오, 기능별 입출력/예외, 데이터 흐름·설계·변경 예정 위치, 추천 기술과 대안/장단점, 위험·검증·예상 시간을 설명합니다. 채팅에서 실제 내용을 보여주고 사용자가 계획을 확인할 때까지 구현을 기다립니다. [상세 브리핑 기준](.agents/skills/solve-task/references/implementation-brief.md)을 따릅니다.
4. **코드 작성·검증:** 사용자가 제시한 계획을 확인하면 합의 범위의 뼈대·기능을 구현하고 실제 동작을 검증합니다. 합의 계획과 현재 결과의 차이·재현된 오류·미검증 위험을 구분해 설명합니다. 같은 범위의 통상 구현은 반복 확인하지 않습니다.
5. **중간 판단:** 사용자 우선순위·업무 정책·범위·중요한 시간/품질 절충은 선택지·추천 이유·영향과 함께 묻고 해당 부분의 답을 기다립니다. 결과물·중요 규칙·저장/API 계약·기술 구조·인계 시점이 크게 달라지면 변경 부분을 다시 브리핑하고 확인받습니다. 함수명 등 통상적인 구현 선택은 매번 묻지 않습니다.

확인한 답변은 다음처럼 짧게 전달할 수 있습니다.

```text
담당자에게 확인한 답변이야.
Q1: 실제 받은 답변
Q2: 실제 받은 답변
추가 조건: 실제 확인한 내용
```

담당자 질문·답변과 상세 브리핑·사용자 확인 대기도 업무 경과시간에 포함합니다. 답변이나 계획 확인 시점에 인계 타이머를 다시 시작하지 않습니다. 시간이 부족하면 범위·인계 영향을 알리며 브리핑과 계획 확인을 생략하지 않습니다.

## 업무 작업 기록

- `SERVICE.md`: 업무 설명 README를 보존하면서 별도로 작성하는 구현 서비스 설명서. 실제 컴포넌트 관계·Mermaid 아키텍처/대표 흐름 다이어그램·API 명세·업무/운영 규칙과 근거·실행·검증·효과/한계를 담습니다. [작성 기준과 양식](.agents/skills/build-service/references/service-document.md)에 따라 서비스 구현 중 생성·갱신합니다.
- `devlog.md`: 실제 질의응답·사용자 판단·변경·실행·실패·수정·검증·다음 행동의 시간순 기록.
- `probe.md`: 페르소나·업무 맥락·페인포인트·원인/근거·해결 원리를 기능과 연결하고, 코드 위치·사용 기술·대안/장단점·선택 이유·검증·업무 효과·이해 확인까지 설명하는 현행 문서.

실제 업무 문서 내용은 배포 저장소에 미리 채워두지 않습니다. 기본 기록 설치는 **업무 작업 폴더**에 devlog.md와 probe.md의 구조를 만들고, SERVICE.md는 서비스 작업 중 실제 코드·규칙·실행 결과로 작성합니다. 기존 문서는 보존하며 생성 자체를 구현·검증·이해 완료로 취급하지 않습니다. 구조/상세 계약은 SERVICE.md, 문제·선택 이유/대안·검증 핵심은 probe.md, 시간순 이력은 devlog.md로 연결합니다.

서비스 작업에는 유스케이스·유저플로우·아키텍처, 화면/API 라우팅, 단계별 모듈 입출력 계약, 대표 입력을 따라 읽을 실제 코드 순서를 포함합니다. 코드 초보자를 위해 핵심 파일·함수·분기/수식·비동기 상태에 상세한 한국어 주석을 남기고 필요한 문법/용어도 설명합니다. [코드 이해 기준](.agents/skills/build-service/references/code-understanding.md)을 따릅니다.

선택/최적화가 있으면 [강제 조건·목표·대안과 조건 변화](.agents/skills/build-service/references/decision-criteria.md)를, 백그라운드 실행이 있으면 [중복 요청·실패·재시작과 결과 게시](.agents/skills/build-service/references/background-work.md)를 검토합니다. 생성과 독립 규칙 검사·가정의 경계를 구분합니다. AI 제안은 채택·수정 요청·기각과 실제 근거/재확인을 기록하며 없는 사례를 만들지 않습니다. 필요한 항목을 실제 기능에 적용하는 지침이며 완성된 최적화 엔진·영속 작업 큐를 포함한다는 뜻은 아닙니다.

기본 React UI는 같은 페이지 안에서 동작하며 CSV/문서 텍스트를 직접 입력합니다. 새 탭 API 링크·홈 페이지 새로고침·네이티브 파일 선택창을 기본 동작에서 제외했습니다. API URL은 개발 문서에 유지합니다. 전체화면이 필요한 환경에서는 [호환 기준](.agents/skills/build-service/references/fullscreen-compatibility.md)에 따라 UI 변경 후 코드 경로와 허용된 준비 환경의 실제 동작을 구분해 확인합니다. 브라우저/OS 전체의 절대 유지 보증이나 감독 동작 변경 기능은 제공하지 않습니다.

solve-task가 시작되면 별도 record-work 호출 없이 문제 분석·담당자 답변·사용자 판단·구현/선택 변경·검증·인계와 작업 턴 종료 전에 Codex가 해당 내용을 갱신합니다. 페르소나는 확인한 업무 역할로 작성하고 원인 가설·담당자 설명·관측을 구분합니다. 기술 테스트 통과를 측정하지 않은 업무 개선 효과로 바꾸지 않습니다. 자동 감시 도구는 devlog에 관측한 파일명·해시 변화만 기록합니다. 의미 있는 설명은 Codex가 실제 근거로 작성하며, 감시 프로그램이 AI를 따로 호출하지 않습니다.

테스트도 실행 전 무엇을 왜 확인하고 어떤 결과를 기대하는지 설명합니다. 실행 후에는 **테스트 목적·입력/조건·기대 결과/근거·실제 결과·판정·한계**를 쉬운 한국어 표로 보여줍니다. SERVICE.md의 목적별 테스트 목록/코드 위치, probe.md의 현재 결과 요약, devlog.md의 실행·실패/수정 이력으로 연결합니다. ‘N개 통과’만으로 설명을 마치지 않고 실제 케이스/비교 코드와 출력을 읽어 해석하며 미실행·건너뜀·수동 확인 대기도 표시합니다. [테스트 설명 기준](.agents/skills/verify-result/references/test-explanation.md)을 따릅니다.

수동 생성도 실제 업무 폴더에서 실행합니다.

```sh
python3 .agents/skills/record-work/scripts/init_records.py --root .
```

[구현·이해·검증 시간표](docs/UNDERSTAND_AND_VERIFY.md)를 참고합니다. 업무의 필수 문서·파일명·금지 조건이 우선입니다.

## 실행 도구

- `analyze-data/scripts/profile_csv.py`: CSV 구조·결측·중복·숫자 범위 요약.
- `verify-result/scripts/run_checks.py`: 명시한 검증 명령 실행과 결과 JSON 기록.
- `verify-result/scripts/check_submission.py`: 명시한 CSV 열·행·ID·필수 값 계약 검사.
- `record-work/scripts/init_records.py`: 작업 기록 파일 생성·기존 파일 보존.
- `git-checkpoint/scripts/checkpoint.py`: 선택 파일의 로컬 스냅샷과 별도 폴더 복구.

CSV 검사에서는 예시 행 수나 첫 열을 계약으로 추정하지 않습니다. 실제 업무에 맞는 옵션만 사용하며 정답·예측 품질은 별도로 검증합니다.

## 로컬 저장

solve-task는 별도 설정 없이 자동 세션을 시작합니다. 기본 3분 간격·최대 3시간·최근 20개이며 새 소스 폴더도 자동 발견합니다. Git 유무와 관계없이 **업무 폴더의 `.local/ai-toolkit/snapshots/`**에 보관하고 `.git`은 수정하지 않습니다. Git을 임의로 초기화하지 않습니다. 중복 시작은 기존 세션을 재사용합니다.

“자동저장 상태 확인해줘” 또는 “자동저장 꺼줘”로 제어할 수 있습니다. 산출물 확정 전에는 최종 스냅샷과 종료를 확인합니다. 직접 점검할 때는 다음 명령을 사용합니다.

```sh
python3 .agents/skills/solve-task/scripts/session.py status --root .
python3 .agents/skills/solve-task/scripts/session.py stop --root .
```

reference 모드에서는 위 경로 대신 bootstrap이 반환한 `session_script`를 사용합니다. 일반 작업 폴더에도 쓰기가 금지되면 자동저장 실패를 알리고 임의 권한 변경이나 우회를 하지 않습니다.

기본 자동 선택은 CSV·의존성·생성물·숨김 도구 폴더·비밀 파일명·바이너리·크기 초과 파일을 제외합니다. Linux/macOS에서 동작하며 제공 IDE에서 실제 시작 상태를 확인해야 합니다. 선택 경로를 직접 지정하는 수동 도구도 유지합니다.

```sh
python3 .agents/skills/git-checkpoint/scripts/checkpoint.py --root . --include src tests docs README.md devlog.md probe.md --once
python3 .agents/skills/git-checkpoint/scripts/checkpoint.py --root . --include src tests docs README.md devlog.md probe.md --watch --interval 180 --duration 10800
```

앱 뼈대를 사용하면 `--include frontend/src backend ai data Makefile Dockerfile compose.yaml devlog.md probe.md`처럼 실제 소스를 지정합니다. 경로는 실제 업무에 맞춥니다. 저장소 내부의 로컬 ZIP 사본이며 자동 커밋·원격 전송을 하지 않습니다. 미저장 에디터 버퍼는 보존하지 않습니다. [저장·복구 설명](docs/GIT_AND_SAVE.md)을 참고합니다.

## 소스 관리·CI/CD·보안 범위

| 영역 | 포함 | 현재 포함하지 않는 것 |
| --- | --- | --- |
| 소스 작성·관리 | 앱 뼈대, 요구별 구현/검증, Git 컨벤션, 로컬 스냅샷·복구 | 자동 stage/commit/push, 원격 저장 보장 |
| CI | GitHub Actions의 Python·프런트 테스트, 타입/빌드 검사, 설치된 앱의 컨테이너 빌드 정의 | 저장소 권한·비밀 값·브랜치 정책에 맞춘 개별 CI 연결 보장 |
| CD | Docker/Compose 실행·영속 볼륨·healthcheck, 단일 포트 전달 경로 | 클라우드 자동 배포·운영 자격증명·배포 승인·롤백 파이프라인 |
| 보안 | 입력 검증·매개변수 SQL·클라이언트 키 분리 지침·비루트 컨테이너·RAG 비신뢰 문서 구분 | 인증/권한 완성본, SAST/DAST·의존성 취약점·전체 비밀정보 자동 검사 |
| 컴플라이언스 | 프로젝트의 자료 접근·전송 정책 확인, 실제 포함 원본의 라이선스 고지 | 법률 준수 판정·감사·인증 자동화 |
| AI 개발 흐름 | 업무 분석·담당자 질의응답→상세 브리핑·계획 확인→구현→검증→기록·인계, 일정 협의 | 모든 운영 조건에서의 정확성·업무 효과·사용자 이해 보장 |

표의 CI/CD는 구성과 실행 경로다. 검사·배포가 실제 성공했는지는 해당 환경의 실행 근거로 확인한다. 필요한 보안·권한과 개인정보 취급 조건은 실제 업무의 요구에 따라 추가 구현·검증한다.

## 검증

```sh
python3 tools/validate.py
python3 -m unittest discover -s tests -v
```

[검증 범위](docs/VALIDATION.md)를 확인합니다. 현재 프로젝트의 자료 접근·외부 전송·AI 도구·배포 정책과 사용자 권한 범위를 따릅니다. 필요한 도구 연결과 운영 검증은 실제 환경에서 확인하고, 기밀 값과 원시 민감 자료는 문서나 공개 저장소에 옮기지 않습니다.

배포에 포함된 외부 원본과 라이선스는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), 고정 버전은 [sources.json](sources.json)에 있습니다.
