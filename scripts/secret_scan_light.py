#!/usr/bin/env python3
"""Fail closed on obvious committed secrets. Placeholders and synthetic fixtures are allowed."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOTS = ('apps', 'tests', 'scripts', 'docs', 'infra', '.github')
SUFFIXES = {'.py', '.md', '.json', '.mjs', '.ts', '.tsx', '.yml', '.yaml', '.env.example', '.txt'}
PATTERNS = (
    re.compile(r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY'),
    re.compile(r'(?i)client_secret\s*=\s*[^\s#]+'),
    re.compile(r'(?i)password\s*=\s*[\'\"][^\'\"]{12,}'),
)
ALLOW = (
    'replace-with',
    'synthetic-test-only',
    'PASSWORD = ',
    'PASSWORD@',
    'example',
    'placeholder',
    'not-a-secret',
    'disposable-',
    'web-e2e-runtime-',
    'at-least-24-random-characters',
    'OWNER:SECRET',
    'postgres:PASSWORD',
    'secrets.token',
)


def main() -> int:
    hits: list[str] = []
    for name in ROOTS:
        root = Path(name)
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            if any(part in {'node_modules', '.next', '.venv'} for part in path.parts):
                continue
            try:
                text = path.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if any(token in line for token in ALLOW):
                    continue
                if any(pattern.search(line) for pattern in PATTERNS):
                    hits.append(f'{path}:{line_no}')
    print(f'SECRET_SCAN_HITS {len(hits)}')
    for hit in hits[:30]:
        print(hit)
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
