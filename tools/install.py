#!/usr/bin/env python3
"""Preview or install selected repository-scoped skills, preserving existing content."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1] / '.agents' / 'skills'
TEMPLATES = SOURCE.parents[1] / 'templates'
IGNORED = {'node_modules', '.venv', '__pycache__', '.git', 'dist', 'build', '.local', '.DS_Store'}
SKILL_DEPENDENCIES = {'solve-task': ['record-work', 'git-checkpoint']}


def resolve_skills(names):
    result = list(dict.fromkeys(names))
    for name in result:
        for dependency in SKILL_DEPENDENCIES.get(name, []):
            if dependency not in result:
                result.append(dependency)
    return result


def template_plan(target, profile=None, modules=()):
    if not profile and not modules:
        return []
    manifest = json.loads((TEMPLATES / 'profiles.json').read_text())
    if profile and modules:
        raise ValueError('choose --profile or --modules')
    if profile and profile not in manifest['profiles']:
        raise ValueError('unknown profile: ' + profile)
    selected = list(manifest['profiles'][profile] if profile else modules)
    resolved = set()
    def include(name):
        if name not in manifest['modules']:
            raise ValueError('unknown module: ' + name)
        if name in resolved:
            return
        resolved.add(name)
        for dependency in manifest['modules'][name]['requires']:
            include(dependency)
    for name in selected:
        include(name)
    plan = []
    for name in sorted(resolved):
        config = manifest['modules'][name]
        root = TEMPLATES / config['source']
        for source in sorted(root.rglob('*')):
            if any(p in IGNORED for p in source.relative_to(root).parts) or source.suffix == '.pyc' or not source.is_file():
                continue
            relative = Path(config['destination']) / source.relative_to(root)
            destination = target / relative
            for ancestor in [destination, *destination.parents]:
                if ancestor == target:
                    break
                if ancestor.is_symlink() or (ancestor != destination and ancestor.exists() and not ancestor.is_dir()):
                    raise ValueError('template path conflict preserved: ' + str(ancestor))
            if destination.exists() and (not destination.is_file() or destination.read_bytes() != source.read_bytes()):
                raise ValueError('existing different file preserved; nothing installed: ' + str(destination))
            plan.append((source, destination, 'unchanged' if destination.exists() else 'install'))
    return plan


def identical(a, b):
    def files(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
                if p.is_file() and '__pycache__' not in p.relative_to(root).parts
                and p.suffix != '.pyc' and p.name != '.DS_Store'}
    aa, bb = files(a), files(b)
    return aa == bb


def run_records(target, check_only=False):
    command = [sys.executable, str(SOURCE / 'record-work/scripts/init_records.py'), '--root', str(target)]
    if check_only:
        command.append('--check')
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'could not initialize task records')


def install(target, names, apply=False, create_records=True, profile=None, modules=()):
    names = resolve_skills(names)
    target = Path(target).resolve()
    if not target.is_dir():
        raise ValueError('target directory must already exist')
    package_root = SOURCE.parents[1]
    if target == package_root or package_root in target.parents:
        raise ValueError('install into the actual task workspace, outside the toolkit distribution')
    dest = target / '.agents' / 'skills'
    for p in (target / '.agents', dest) if names else ():
        if p.is_symlink():
            raise ValueError('installation directory must not be a symlink')
    plan = []
    for name in names:
        if Path(name).name != name or name in {'.', '..'} or not (SOURCE / name / 'SKILL.md').is_file():
            raise ValueError('unknown skill: ' + name)
        d = dest / name
        if d.is_symlink() or (d.exists() and (not d.is_dir() or not identical(SOURCE / name, d))):
            raise ValueError('existing different skill preserved; nothing installed: ' + str(d))
        plan.append((name, 'unchanged' if d.exists() else 'install'))
    files = template_plan(target, profile, modules)
    wants_records = create_records and bool({'solve-task', 'record-work'} & set(names))
    if wants_records:
        run_records(target, check_only=True)
    if apply:
        if plan:
            dest.mkdir(parents=True, exist_ok=True)
        for name, action in plan:
            if action == 'install':
                shutil.copytree(SOURCE / name, dest / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
        for source, destination, action in files:
            if action == 'install':
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also protects a file created after the preflight.
                with destination.open('xb') as stream:
                    stream.write(source.read_bytes())
        if wants_records:
            run_records(target)
    return plan + [('file:' + destination.relative_to(target).as_posix(), action) for _, destination, action in files]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', default='.')
    p.add_argument('--skills', nargs='+')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--skip-records', action='store_true', help='install skills without creating task records')
    p.add_argument('--templates-only', action='store_true', help='copy selected app modules without installing skills or records')
    selection = p.add_mutually_exclusive_group()
    selection.add_argument('--profile', choices=['fullstack', 'frontend', 'api', 'rag', 'data'])
    selection.add_argument('--modules', nargs='+', choices=['frontend', 'backend', 'ai', 'data', 'infra'])
    a = p.parse_args()
    if a.templates_only and (a.skills or not (a.profile or a.modules)):
        p.error('--templates-only requires --profile or --modules and cannot be combined with --skills')
    names = [] if a.templates_only else (a.skills or sorted(p.name for p in SOURCE.iterdir() if (p / 'SKILL.md').exists()))
    try:
        for name, action in install(a.target, names, a.apply, not a.skip_records, a.profile, a.modules or ()):
            print(('APPLIED' if a.apply else 'PREVIEW') + ' ' + action + ' ' + name)
        if not a.skip_records and {'solve-task', 'record-work'} & set(names):
            print(('APPLIED' if a.apply else 'PREVIEW') + ' task records: devlog.md, probe.md')
    except (OSError, ValueError) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
