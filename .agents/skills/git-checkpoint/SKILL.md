---
name: git-checkpoint
description: Preserve recoverable local work with explicit Git checkpoints, concise commit conventions and optional file snapshots. Use for a requested checkpoint, autosave setup, or session recovery without remote transfer.
---

# Git 컨벤션과 로컬 보존

## 서로 다른 저장

에디터 저장은 디스크 반영, 스냅샷은 복구용 파일 사본, 커밋은 의미 있는 변경 기록, 업무 인계는 합의한 결과물과 검증·운영 정보를 담당자에게 전달하는 일이다. 서로 완료를 대신하지 않는다. 저장되지 않은 에디터 버퍼는 이 도구로 보존할 수 없다.

## Git 작업

- 먼저 `git status --short`, `git diff`, `git diff --cached`를 확인한다. 다른 사람/사용자의 기존 변경과 staging을 보존한다.
- `feat|fix|docs|test|refactor|chore(scope): 변경 목적` 형식을 사용한다. 실제 수행한 변경을 작은 의미 단위로 기록한다.
- `git add -- <확인한 경로>`로 범위를 지정한다. 기존 staging과 섞이면 임의로 해제·커밋하지 않는다. 커밋할 파일과 의미를 확인한다.
- 검증하지 않은 저장 지점은 `chore(checkpoint): ... (미검증)`처럼 상태를 밝힌다. 검증 완료로 꾸미지 않는다.
- reset/clean/강제 checkout·히스토리 재작성·전역 Git 설정 변경을 자동 수행하지 않는다. push·원격 업로드는 사용자 지시나 합의한 업무 흐름의 권한 범위에서 별도로 수행한다. 로컬 보존 요청만으로 원격 전송을 시작하지 않는다.

## 기본 자동저장과 선택형 수동 제어

solve-task로 시작한 작업은 해당 스킬의 session.py가 별도 설정 없이 자동저장을 시작한다. 사용자가 이 스킬에 자동저장 시작을 요청한 경우도 설치본 또는 공개 클론의 solve-task/scripts/session.py start를 우선 사용하고 상태·첫 사본을 확인한다. 중복 실행은 기존 세션을 재사용한다. Git 유무와 관계없이 업무 폴더의 `.local/ai-toolkit/snapshots/`에 보관하고 관리되는 `.git`을 수정하지 않는다. 업무 세션 종료 또는 해제 요청 시 session.py stop으로 마친다.

자동 세션이 없거나 선택 범위를 직접 지정할 때 `scripts/checkpoint.py --root . --include <실제 경로들> --once`로 1회 저장한다. `--watch --interval 180 --duration 10800`은 선택한 경로의 자동저장을 유한 시간 동안 켠다. 별도 터미널에서 실행하고 종료는 Ctrl+C다. 같은 저장 위치에서 여러 writer를 동시에 실행하지 않는다. solve-task가 설치되어 있지 않으면 이 수동 도구를 사용한다.

이 키트의 기본 작업 기록인 `devlog.md`와 `probe.md`도 실제 저장 경로에 맞춰 include 목록에 넣는다. 예: `--include src tests docs README.md devlog.md probe.md`.

- 기본 자동 세션은 `.local/ai-toolkit/snapshots/`, 선택형 수동 checkpoint.py는 `.git/ai-toolkit-snapshots/`에 ZIP으로 저장한다. 수동 도구는 Git 메타데이터 쓰기가 허용된 환경에서만 사용한다. 변경이 없으면 생략한다.
- 비밀 파일명·의존성/생성물·심볼릭 링크·외부 경로를 제외한다. 기본 파일당 2MiB·전체 20MiB 제한이며 제외 목록과 사유를 보고한다.
- 네트워크, 원격 전송, git add/commit, 인덱스·브랜치 변경을 수행하지 않는다. 보존 개수는 기본 20개다.
- 이름 필터는 비밀정보 탐지 보장이 아니다. 선택 범위를 직접 검토한다. 대용량/바이너리는 별도 업무의 저장 절차를 따른다.
- `--restore <snapshot.zip> --to <비어 있거나 없는 별도 폴더>`로 복구본을 만든 뒤 diff로 확인한다. 작업 원본에 자동 덮어쓰지 않는다.

## 세션 복구

작업 기록에 현재 상태·다음 행동·실행 명령·검증 위치를 남긴다. 재개 시 실제 파일·Git 상태·검증 근거를 대조하고 이전 스냅샷이나 완료 보고 이후 달라진 내용을 확인한다.
