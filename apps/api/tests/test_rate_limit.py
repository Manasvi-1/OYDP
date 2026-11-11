import os

from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import reset_rate_limit_state


def test_mutating_routes_are_throttled_when_configured(monkeypatch):
    monkeypatch.setenv('OYDP_RATE_LIMIT', '1')
    monkeypatch.setenv('OYDP_RATE_LIMIT_WINDOW_SECONDS', '60')
    monkeypatch.setenv('OYDP_RATE_LIMIT_MAX', '2')
    reset_rate_limit_state()
    client = TestClient(app)
    headers = {'Authorization': 'Bearer synthetic-rate-limit-token'}
    first = client.post('/v1/properties', headers=headers, json={'label': 'One', 'jurisdiction': 'KA'})
    second = client.post('/v1/properties', headers=headers, json={'label': 'Two', 'jurisdiction': 'KA'})
    third = client.post('/v1/properties', headers=headers, json={'label': 'Three', 'jurisdiction': 'KA'})
    # Fail closed on auth/config before rate limit is not required; once past auth path, 429 must appear.
    assert first.status_code != 429
    assert second.status_code != 429
    assert third.status_code == 429
    assert third.json()['detail'] == 'Too many requests'
    reset_rate_limit_state()


def test_health_get_is_not_throttled_by_mutation_budget(monkeypatch):
    monkeypatch.setenv('OYDP_RATE_LIMIT', '1')
    monkeypatch.setenv('OYDP_RATE_LIMIT_MAX', '1')
    reset_rate_limit_state()
    client = TestClient(app)
    assert client.get('/healthz').status_code == 200
    assert client.get('/healthz').status_code == 200
    reset_rate_limit_state()
