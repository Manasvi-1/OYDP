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


def test_evidence_graph_fails_closed_without_oidc():
    r = client.get("/v1/properties/00000000-0000-0000-0000-000000000001/evidence-graph")
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


def _schema_values(schema):
    if 'enum' in schema:
        return set(schema['enum'])
    if 'const' in schema:
        return {schema['const']}
    if 'anyOf' in schema:
        return {item.get('const') for item in schema['anyOf']}
    return set()


def test_trusted_evidence_contract_does_not_grant_title():
    spec = client.get('/openapi.json').json()
    assert spec['info']['version'] == '0.14.0'
    paths = spec['paths']
    for path in (
        '/v1/properties/{property_id}/identifiers',
        '/v1/properties/{property_id}/reviews',
        '/v1/properties/{property_id}/consents',
        '/v1/properties/{property_id}/exports',
        '/v1/properties/{property_id}/evidence-graph',
        '/v1/properties/{property_id}/documents',
        '/v1/properties/{property_id}/audit',
        '/v1/sources',
        '/v1/sources/{source_id}/withdrawal',
    ):
        assert path in paths
    schemas = spec['components']['schemas']
    packet = schemas['EvidencePacket']
    assert packet['properties']['title_verified']['const'] is False
    assert 'not a title certificate' in packet['properties']['notice']['const']
    graph = schemas['EvidenceGraph']
    assert graph['properties']['title_verified']['const'] is False
    assert 'Evidence graph projection only' in graph['properties']['notice']['const']
    assert graph.get('additionalProperties') is not True
    edge = schemas['EvidenceGraphEdge']
    assert set(edge['required']) == {'from_kind', 'from_id', 'to_kind', 'to_id', 'relation'}
    assert 'get' in paths['/v1/properties/{property_id}/evidence-graph']
    assert 'post' not in paths['/v1/properties/{property_id}/evidence-graph']
    assert 'put' not in paths['/v1/properties/{property_id}/evidence-graph']
    assert 'delete' not in paths['/v1/properties/{property_id}/evidence-graph']
    assert schemas['ReviewRecord']['properties']['title_effect']['const'] == 'none'
    assert 'claim_id' in schemas['ReviewCreate']['properties']
    assert 'claim_id' in schemas['ReviewRecord']['properties']
    assert 'document_id' in schemas['ReviewCreate']['properties']
    assert 'document_id' in schemas['ReviewRecord']['properties']
    assert 'identifier_id' in schemas['ReviewCreate']['properties']
    assert 'identifier_id' in schemas['ReviewRecord']['properties']
    assert schemas['ReviewRecord']['properties']['title_effect']['const'] == 'none'
    assert schemas['SourceRecord']['properties']['rights_status']['const'] == 'unknown'
    assert 'rights_status' not in schemas['SourceCreate']['properties']
    assert schemas['SourceCreate']['additionalProperties'] is False
    claim_create = schemas['ClaimCreate']
    assert set(claim_create['required']) == {'statement'}
    assert 'source_id' in claim_create['properties']
    assert claim_create['additionalProperties'] is False
    claim_record = schemas['ClaimRecord']
    assert claim_record['properties']['kind']['const'] == 'user_claim'
    assert claim_record['properties']['verification_status']['const'] == 'unverified'
    assert 'source_id' in claim_record['properties']
    assert 'source_id' in schemas['PacketClaim']['properties']
    assert '/v1/properties/{property_id}/documents/{document_id}/attribution' in paths
    doc = schemas['DocumentRecord']['properties']
    assert 'claim_id' in doc and 'source_id' in doc and 'identifier_id' in doc
    attribution = schemas['DocumentAttribution']
    assert attribution['additionalProperties'] is False
    assert set(attribution['properties']) == {'claim_id', 'source_id', 'identifier_id'}
    packet_docs = schemas['EvidencePacket']['properties']['documents']
    assert packet_docs['items']['$ref'] == '#/components/schemas/DocumentRecord'
    assert _schema_values(schemas['IdentifierCreate']['properties']['scheme']) == {'internal', 'survey', 'municipal', 'khata'}
    assert _schema_values(schemas['ReviewCreate']['properties']['disposition']) == {'recorded', 'abstained'}
    assert schemas['ConsentCreate']['properties']['purpose']['const'] == 'passport_export'
    audit = schemas['AuditRecord']['properties']
    assert set(audit) == {'event_type', 'actor_subject', 'recorded_at', 'delivered_at'}
    assert 'document.attributed' in _schema_values(schemas['AuditRecord']['properties']['event_type'])
