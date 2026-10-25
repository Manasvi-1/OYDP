"""Export/check the active API contract. Run with PYTHONPATH=apps/api:."""
import argparse
import json
from pathlib import Path

from app.main import app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    path=Path(__file__).resolve().parents[1]/'apps/api/openapi.json'
    content=json.dumps(app.openapi(),indent=2,sort_keys=True,ensure_ascii=False)+'\n'
    if args.check:
        if not path.exists() or path.read_text()!=content:
            raise SystemExit('Active OpenAPI contract is stale; run scripts/export_active_openapi.py')
        print('Active OpenAPI contract matches')
    else:
        path.write_text(content)
        print('Exported apps/api/openapi.json')


if __name__=='__main__': main()
