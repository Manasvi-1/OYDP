from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/healthz").json() == {"status": "ok"}

def test_property_create_fails_closed_without_oidc():
    r = client.post("/v1/properties", json={"label": "Test", "jurisdiction": "KA"})
    assert r.status_code == 503

def test_property_read_fails_closed_without_oidc():
    r = client.get("/v1/properties/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 503
