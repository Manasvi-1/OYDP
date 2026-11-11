"""Machine-checkable boundary between the active API and the PR #1 reference backend."""
from pathlib import Path
import ast
import importlib
import sys

import pytest

from scripts.migrate import REFERENCE_MIGRATIONS, ROOT, migrate


REPO = Path(__file__).resolve().parents[3]


def test_active_api_does_not_import_reference_package():
    main_path = REPO / 'apps' / 'api' / 'app' / 'main.py'
    tree = ast.parse(main_path.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert 'oydp' not in imported
    # Importing the active app must not pull the reference package into the process.
    before = {name for name in sys.modules if name == 'oydp' or name.startswith('oydp.')}
    module = importlib.import_module('app.main')
    after = {name for name in sys.modules if name == 'oydp' or name.startswith('oydp.')}
    assert after == before
    assert module.__name__ == 'app.main'
    assert 'app.main' in sys.modules
    assert not any(name == 'oydp' or name.startswith('oydp.') for name in sys.modules)


def test_canonical_migrations_live_under_infra_db():
    assert ROOT == REPO / 'infra' / 'db'
    assert ROOT.is_dir()
    files = sorted(p.name for p in ROOT.glob('[0-9][0-9][0-9]_*.sql'))
    assert files[0] == '001_property_identity.sql'
    assert files[-1] == '019_review_document_identifier_attribution.sql'
    assert len(files) == 19


def test_migrate_rejects_reference_migrations_directory():
    assert REFERENCE_MIGRATIONS == REPO / 'migrations'
    assert REFERENCE_MIGRATIONS.is_dir()
    with pytest.raises(ValueError, match='reference tree'):
        migrate('postgresql://unused', REFERENCE_MIGRATIONS)


def test_reference_package_is_not_mounted_by_active_openapi():
    from app.main import app

    schema = app.openapi()
    assert schema['info']['title'] == 'OYDP Property Identity API'
    # Diligence routes ship with the active contract; version must stay aligned.
    assert schema['info']['version'] == '0.15.0'
    dumped = str(schema)
    assert 'oydp schema' not in dumped.lower()
    assert '/v1/properties' in schema['paths']
