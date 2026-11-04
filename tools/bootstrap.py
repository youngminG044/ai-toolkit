#!/usr/bin/env python3
"""Install skills and return a handoff for the already-running coding agent."""
import argparse
import errno
import json
from pathlib import Path
import re
import sys
from install import SOURCE, install


def catalog():
    result = []
    for path in sorted(SOURCE.glob('*/SKILL.md')):
        match = re.match(r'\A---\n(.*?)\n---\n', path.read_text(encoding='utf-8'), re.S)
        fields = dict(re.findall(r'^(name|description):\s*(.+)$', match[1], re.M)) if match else {}
        name, description = fields.get('name'), fields.get('description')
        if name != path.parent.name or not description:
            raise ValueError('invalid skill metadata: ' + str(path))
        result.append({'name': name, 'description': description})
    if not result or not any(skill['name'] == 'solve-task' for skill in result):
        raise ValueError('solve-task entry skill is missing')
    return result


def prepare(target, mode='auto'):
    target = Path(target).resolve()
    if mode not in {'auto', 'install', 'reference'}:
        raise ValueError('mode must be auto, install or reference')
    if not target.is_dir() or any((path / '.toolkit-package').is_file() for path in (target, *target.parents)):
        raise ValueError('choose the existing task workspace outside the toolkit distribution')
    skills = catalog()
    installation_status, install_error = 'not_requested', None
    skill_root = SOURCE
    actions = {skill['name']: 'reference' for skill in skills}
    if mode != 'reference':
        try:
            # Read task instructions before extra record files or a watcher are allowed.
            plan = install(target, [skill['name'] for skill in skills], apply=True, create_records=False)
            actions = dict(plan)
            skill_root = target / '.agents/skills'
            installation_status = 'complete'
        except OSError as error:
            failed = Path(error.filename).absolute() if error.filename else None
            boundary = target / '.agents'
            protected_install = failed is not None and (failed == boundary or boundary in failed.parents)
            if mode != 'auto' or error.errno not in {errno.EROFS, errno.EACCES, errno.EPERM} or not protected_install:
                raise
            # Read public instructions in place; do not change permissions or agent configuration.
            installation_status = 'not_completed'
            install_error = {'errno': error.errno, 'path': str(failed), 'message': str(error)}
    for skill in skills:
        skill['path'] = str(skill_root / skill['name'] / 'SKILL.md')
        skill['action'] = actions[skill['name']]
    entry = skill_root / 'solve-task/SKILL.md'
    return {
        'status': 'ready',
        'mode': 'installed' if installation_status == 'complete' else 'reference',
        'installation_status': installation_status,
        'install_error': install_error,
        'target': str(target),
        'toolkit': str(SOURCE.parents[1]),
        'continue_in_current_session': True,
        'skills': skills,
        'entry_skill': 'solve-task',
        'entry_path': str(entry),
        'session_script': str(skill_root / 'solve-task/scripts/session.py'),
        'task_instruction_paths': [str(target / name) for name in ['AGENTS.md', 'README.md'] if (target / name).is_file()],
        'next_instruction': (
            '현재 Codex 대화를 유지한다. '
            '새 Codex를 실행하지 말고 entry_path의 SKILL.md를 실제로 읽어 참조 문서와 기본 흐름을 적용한다. '
            'reference 모드는 설치 완료가 아니라 공개 원본을 직접 읽는 방식이며 모든 스킬과 스크립트는 반환된 경로를 사용한다. '
            '이 모드에서 앱 뼈대가 필요하면 install.py의 --templates-only를 사용해 관리되는 .agents 폴더를 수정하지 않는다. '
            '사용자가 현재 대화에 제공한 문제 상황·업무 목표를 우선하고 업무 README와 기존 지침을 확인한다. '
            '정보가 없으면 문제 설명을 간단히 요청한다. '
            '업무 제약을 확인한 뒤 기록·자동저장을 준비하고, 먼저 담당자 질문을 제안해 확인한 답변을 기다린다. '
            '답변을 반영한 뒤 구현 전 상세 브리핑으로 결과물·기능·설계/기술·대안·검증·시간을 설명한다. '
            '사용자가 제시한 계획을 확인하기 전에는 업무 코드 작성이나 앱 뼈대 적용을 시작하지 않는다. '
            '기본 집중 세션은 180분으로, 60분 1차 인계(지연 시 80분), 120분까지 보완/수정과 이해 병행, '
            '120~180분은 코드 변경 없는 이해에 사용한다. 현재 사용자의 다른 기간 지시는 우선한다.'
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, help='actual task root; keep it separate from the toolkit clone')
    parser.add_argument('--mode', choices=['auto', 'install', 'reference'], default='auto',
                        help='auto uses public source references if skill installation is denied')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.target, args.mode), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
