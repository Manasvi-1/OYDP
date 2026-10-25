"""Regenerate the checked-in contract from the application's actual routes."""
import json
from pathlib import Path
from oydp.api import create_app


if __name__ == '__main__':
    # Schema generation never connects to the database or verifies a token.
    schema = create_app(None, None).openapi()
    target = Path(__file__).resolve().parents[1] / 'docs' / 'openapi.json'
    target.write_text(json.dumps(schema, indent=2) + '\n')
