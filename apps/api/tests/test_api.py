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


def test_privacy_response_headers():
    response=client.get('/healthz')
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-content-type-options']=='nosniff'


def test_correction_contract_isolates_records_and_pages():
    spec = client.get('/openapi.json').json()
    schemas = spec['components']['schemas']
    correction = schemas['CorrectionRecord']
    assert {'id', 'tenant_id', 'property_id', 'previous_label', 'previous_jurisdiction', 'label', 'jurisdiction', 'actor_subject', 'recorded_at'} <= set(correction['required'])
    assert correction['properties']['tenant_id']['format'] == 'uuid'
    assert correction['properties']['property_id']['format'] == 'uuid'
    writers = schemas['WriteGrantPage']
    assert writers['required'] == ['items', 'next_cursor']
    assert 'next_cursor' in writers['properties']
    parameters = spec['paths']['/v1/properties/{property_id}/writers']['get']['parameters']
    assert {'limit', 'cursor'} <= {item['name'] for item in parameters}
    patch = spec['paths']['/v1/properties/{property_id}']['patch']
    assert patch['requestBody']['content']['application/json']['schema']['$ref'] == '#/components/schemas/PropertyCorrection'
    body = schemas['PropertyCorrection']
    assert body['additionalProperties'] is False
    assert set(body['required']) == {'label', 'jurisdiction'}
    assert set(body['properties']) == {'label', 'jurisdiction'}
