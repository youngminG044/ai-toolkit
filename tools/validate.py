#!/usr/bin/env python3
"""Validate skill structure and local Markdown links; uses no external packages."""
import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git', 'node_modules', '.venv', '__pycache__', 'dist', 'build', '.local'}


def validate(root=ROOT):
    errors, names = [], set()
    if (root / '.toolkit-package').exists():
        for filename in ('devlog.md', 'probe.md'):
            if (root / filename).exists():
                errors.append(filename + ': task records belong in the actual task workspace')
    skills = list((root / '.agents' / 'skills').glob('*/SKILL.md'))
    if not skills:
        errors.append('no skills found')
    for path in skills:
        text = path.read_text()
        match = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
        if not match:
            errors.append(str(path) + ': frontmatter missing')
            continue
        fields = dict(re.findall(r'^(name|description):\s*(.+)$', match[1], re.M))
        name = fields.get('name', '')
        if name != path.parent.name or not re.fullmatch(r'[a-z0-9-]{1,64}', name) or name in names:
            errors.append(str(path) + ': invalid/duplicate name')
        names.add(name)
        if not fields.get('description') or len(fields['description']) > 1024:
            errors.append(str(path) + ': invalid description')
        if 'TODO' in text or '[INSERT' in text:
            errors.append(str(path) + ': unfinished scaffold')
    for path in root.rglob('*.md'):
        if any(part in IGNORED | {'vendor'} for part in path.relative_to(root).parts):
            continue
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            link = link.split('#')[0]
            if link and not re.match(r'[a-z]+:|^#', link) and not (path.parent / link).exists():
                errors.append(str(path.relative_to(root)) + ': missing link ' + link)
    for path in root.rglob('*.py'):
        if not any(part in IGNORED for part in path.relative_to(root).parts):
            try:
                ast.parse(path.read_text(), filename=str(path))
            except SyntaxError as e:
                errors.append(str(e))
    return errors, len(skills)


if __name__ == '__main__':
    errors, count = validate()
    for e in errors:
        print('ERROR: ' + e)
    print(str(count) + ' skills; ' + str(len(errors)) + ' structural errors')
    sys.exit(bool(errors))
