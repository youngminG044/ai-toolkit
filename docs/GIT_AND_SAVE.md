# Git 컨벤션과 자동저장

## 작업 기록과 커밋

`feat(scope): 필수 사용자 동작 구현`, `fix(scope): 잘못된 경계값 처리 수정`, `test(scope): 실패 사례 검증`, `docs(scope): 실행 방법 기록`처럼 실제 변화와 목적을 쓴다. 정해진 커밋 수를 채울 필요는 없다.

```sh
git status --short
git diff
git diff --cached
git add -- src/main.py tests/test_main.py
git diff --cached
git commit -m "feat(core): 핵심 입력 처리 구현"
```

경로는 실제 파일로 바꾼다. 기존 staging이 있으면 다른 변경과 섞어 커밋하지 않는다. 로컬 커밋은 원격 전송과 별개다. `git push`·PR·원격 저장은 사용자 지시나 합의한 업무 흐름과 저장소 접근 정책에 따라 수행한다.

## 자동저장이 하는 일

solve-task 호출은 session.py로 자동저장을 시작한다. 별도 설정 없이 소스·설정·문서를 3분 간격·최대 3시간·최근 20개로 보관하며, 새 경로를 매번 발견한다. 실행 중인 세션을 중복 시작하지 않는다. Python 3.9+와 Linux/macOS를 사용하며 플랫폼에서 실제 시작 결과를 확인한다.

Git 유무와 관계없이 업무 폴더의 `.local/ai-toolkit/snapshots/`를 사용한다. 관리되는 `.git`을 수정하거나 Git을 임의로 초기화하지 않는다. 파일명 필터·UTF-8·크기 제한을 적용하며 기본 자동 선택에서 CSV와 숨김 도구 폴더·생성물·의존성·바로 아래의 배포 키트 클론을 제외한다. 작업 소스·인덱스·브랜치·원격은 바꾸지 않는다. 기록이 허용된 작업에서는 devlog에 관측 파일명·해시 변화를 추가한다.

```sh
python3 .agents/skills/solve-task/scripts/session.py status --root .
python3 .agents/skills/solve-task/scripts/session.py stop --root .
```

.agents 설치가 제한된 환경에서는 공개 클론의 session.py 또는 bootstrap이 반환한 session_script 경로를 사용한다. 일반 작업 폴더 자체에 쓰기가 금지됐다면 자동저장 미작동을 알리고 권한·설정을 변경하지 않는다.

status는 실제 잠금·상태·마지막 사본·제외 항목을 확인한다. 실행이 중단되었으면 interrupted로 표시하며 원인 확인 뒤 start로 재시작할 수 있다. stop은 해당 세션에 종료 요청을 보내 최종 사본을 만들고 종료를 확인한다. 관련 없는 프로세스를 kill하지 않는다. 업무 세션 종료나 사용자 요청 시 종료하고, 자동 실행이 차단된 환경에서는 우회하지 않고 상태와 영향을 알린다. 최대 3시간은 감시 프로세스의 안전 상한이며 업무 마감이 아니다.

아래의 선택형 checkpoint.py는 기존 동작을 유지하며 Git 작업 트리 루트와 메타데이터 쓰기 권한을 요구한다. `.git`이 관리되는 읽기 전용 환경에서는 기본 session.py를 사용한다. 같은 작업을 여러 watcher로 중복 저장하지 않는다.

```sh
python3 .agents/skills/git-checkpoint/scripts/checkpoint.py --root . --include src tests docs README.md devlog.md probe.md --once
```

- `saved`: 새 스냅샷 경로와 파일 수를 확인한다.
- `unchanged`: 선택 파일 내용이 직전 사본과 같아 새 ZIP이 필요 없었다.
- `no-files`: 저장한 파일이 없으며 종료 코드 2다. 저장 성공으로 읽지 않는다.
- `skipped`: 누락 경로·제외 디렉터리·비밀 파일명·비텍스트·크기 초과 등을 확인한다.

## 선택 경로의 수동 주기 저장

별도 터미널에서 실행한다. 3분 간격·최대 3시간·최근 20개가 기본값이다.

```sh
python3 .agents/skills/git-checkpoint/scripts/checkpoint.py --root . --include src tests docs README.md devlog.md probe.md --watch --interval 180 --duration 10800
```

Ctrl+C로 종료하면 잠금을 정리한다. 갑작스러운 강제 종료로 `writer.lock`이 남을 수 있다. 파일에 적힌 PID의 프로세스가 종료되었는지 확인한 뒤 그 잠금 파일만 정리한다. 실행 중인 프로세스를 확인 없이 죽이거나 잠금을 지우지 않는다.

에디터 버퍼는 먼저 저장해야 한다. 여러 파일을 편집하는 순간의 사본은 의미상 한 변경 단위가 아닐 수 있으므로, 검증된 마일스톤은 Git 쓰기가 허용된 환경에서 별도 커밋으로 남긴다. 자동 스냅샷은 테스트 통과를 뜻하지 않으며 플랫폼 인계 완료를 대신하지 않는다.

## 별도 폴더로 복구

```sh
python3 .agents/skills/git-checkpoint/scripts/checkpoint.py --restore .local/ai-toolkit/snapshots/실제파일.zip --to /tmp/recovered-work
```

대상은 새 폴더 또는 빈 폴더여야 한다. 경로·체크섬을 확인한 뒤 복구하고 원본을 덮어쓰지 않는다. `diff`로 비교한 후 필요한 파일만 작업 폴더로 반영한다. 스냅샷에서 빠진 파일은 복구되지 않는다. 파일 삭제도 원본에 자동 적용하지 않는다.

기본 한도는 파일당 2MiB·총 20MiB, UTF-8 텍스트다. 이름 필터는 파일 안의 모든 비밀을 검출하지 못하므로 선택 범위를 검토한다. 이 도구에는 네트워크 기능이 없다.
