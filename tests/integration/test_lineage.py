"""Evidence lineage against a disposable PostgreSQL database."""
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from psycopg.conninfo import make_conninfo

from scripts.migrate import migrate, provision_runtime

DSN = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='TEST_DATABASE_URL is required for real PostgreSQL tests')
PASSWORD = 'synthetic-test-only-password-32-chars'


@pytest.fixture(scope='module', autouse=True)
def database():
    migrate(DSN)
    provision_runtime(DSN, PASSWORD)
    yield
    with psycopg.connect(DSN) as conn:
        conn.execute("DELETE FROM property_audit_events WHERE actor_subject LIKE 'lineage-%'")
        conn.execute("DELETE FROM evidence_assertions WHERE created_by LIKE 'lineage-%'")
        conn.execute("DELETE FROM property_identifiers WHERE created_by LIKE 'lineage-%'")
        conn.execute("DELETE FROM evidence_sources WHERE created_by LIKE 'lineage-%'")
        conn.execute("DELETE FROM properties WHERE created_by LIKE 'lineage-%'")
        conn.execute("DELETE FROM tenant_memberships WHERE subject_id LIKE 'lineage-%'")


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import require_mfa, verified_subject
    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    app.dependency_overrides[verified_subject] = lambda: 'lineage-alice'
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def as_subject(subject):
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides[verified_subject] = lambda: subject


def workspace(role='owner', subject='lineage-alice'):
    tenant = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute('INSERT INTO tenant_memberships VALUES (%s,%s,%s)', (tenant, subject, role))
    return tenant


def create_property(api, tenant, label='Lineage candidate'):
    response = api.post('/v1/properties', headers={'X-Tenant-ID': str(tenant)}, json={'label': label, 'jurisdiction': 'Bengaluru Urban'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_source_identifier_and_evidence_are_attributed(api):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    source = api.post(f'/v1/properties/{property_id}/sources', headers=headers, json={
        'name': 'Seller packet', 'source_class': 'user_supplied', 'locator': 'file note 1'})
    assert source.status_code == 201, source.text
    assert source.json()['created_by'] == 'lineage-alice'
    identifier = api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={
        'scheme': 'survey_number', 'identifier_value': '12/3'})
    assert identifier.status_code == 201, identifier.text
    assert identifier.json()['superseded_at'] is None
    evidence = api.post(f'/v1/properties/{property_id}/evidence', headers=headers, json={
        'assertion_type': 'site description',
        'assertion_text': 'The packet calls this a 30 by 40 site.',
        'source_kind': 'user_claim',
        'source_id': source.json()['id'],
    })
    assert evidence.status_code == 201, evidence.text
    body = evidence.json()
    assert body['review_status'] == 'unreviewed' and body['source_kind'] == 'user_claim'
    listed = api.get(f'/v1/properties/{property_id}/evidence', headers=headers).json()
    assert listed['items'][0]['id'] == body['id'] and listed['next_cursor'] is None
    with psycopg.connect(make_conninfo(DSN, user='oydp_app', password=PASSWORD)) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        conn.execute("SELECT set_config('app.subject_id', 'lineage-alice', true)")
        events = conn.execute("SELECT event_type FROM property_audit_events WHERE property_id=%s AND event_type<>'property.created' ORDER BY event_type", (property_id,)).fetchall()
    assert events == [('evidence.recorded',), ('identifier.recorded',), ('source.recorded',)]


def test_identifier_conflict_and_supersede(api):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    first = api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={'scheme': 'khata', 'identifier_value': 'old'})
    assert first.status_code == 201, first.text
    conflict = api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={'scheme': 'khata', 'identifier_value': 'new'})
    assert conflict.status_code == 409
    assert 'old' not in conflict.text and 'new' not in conflict.text
    other = api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={'scheme': 'municipal_reference', 'identifier_value': 'ward-1'})
    assert other.status_code == 201, other.text
    replaced = api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={
        'scheme': 'khata', 'identifier_value': 'new', 'supersede': True})
    assert replaced.status_code == 201, replaced.text
    history = api.get(f'/v1/properties/{property_id}/identifiers?limit=10', headers=headers).json()['items']
    current = [item for item in history if item['scheme'] == 'khata' and item['superseded_at'] is None]
    previous = [item for item in history if item['scheme'] == 'khata' and item['superseded_at'] is not None]
    assert [item['identifier_value'] for item in current] == ['new']
    assert [item['identifier_value'] for item in previous] == ['old']


def test_reader_and_other_tenant_cannot_write_or_read(api):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    other = workspace(subject='lineage-mallory')
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'lineage-reader','viewer')", (tenant,))
    as_subject('lineage-reader')
    assert api.get(f'/v1/properties/{property_id}/sources', headers=headers).status_code == 404
    assert api.post(f'/v1/properties/{property_id}/sources', headers=headers, json={'name': 'x', 'source_class': 'user_supplied'}).status_code == 404
    as_subject('lineage-mallory')
    assert api.get(f'/v1/properties/{property_id}/identifiers', headers={'X-Tenant-ID': str(other)}).status_code == 404
    as_subject('lineage-alice')
    assert api.post(f'/v1/properties/{property_id}/evidence', headers={'X-Tenant-ID': str(other)}, json={
        'assertion_type': 'note', 'assertion_text': 'no', 'source_kind': 'user_claim'}).status_code == 403


def test_downgraded_creator_cannot_append(api):
    tenant = workspace(role='viewer')
    headers = {'X-Tenant-ID': str(tenant)}
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE tenant_memberships SET role='owner' WHERE subject_id='lineage-alice' AND tenant_id=%s", (tenant,))
    property_id = create_property(api, tenant)
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE tenant_memberships SET role='viewer' WHERE subject_id='lineage-alice' AND tenant_id=%s", (tenant,))
    assert api.post(f'/v1/properties/{property_id}/sources', headers=headers, json={'name': 'later', 'source_class': 'published_reference'}).status_code == 403


def test_mfa_and_forged_official_status_rejected(api):
    from app.main import app
    from app.auth import require_mfa
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    app.dependency_overrides[require_mfa] = lambda: (_ for _ in ()).throw(HTTPException(403, 'MFA access token required'))
    assert api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={'scheme': 'local_label', 'identifier_value': 'A'}).status_code == 403
    app.dependency_overrides[require_mfa] = lambda: True
    forged = api.post(f'/v1/properties/{property_id}/evidence', headers=headers, json={
        'assertion_type': 'title', 'assertion_text': 'official', 'source_kind': 'official_observation', 'source_reference': 'portal'})
    assert forged.status_code == 422
    promoted = api.post(f'/v1/properties/{property_id}/evidence', headers=headers, json={
        'assertion_type': 'note', 'assertion_text': 'text', 'source_kind': 'user_claim', 'review_status': 'recorded'})
    assert promoted.status_code == 422
    missing_note = api.post(f'/v1/properties/{property_id}/evidence', headers=headers, json={
        'assertion_type': 'review', 'assertion_text': 'looks consistent', 'source_kind': 'professional_review'})
    assert missing_note.status_code == 422
    noted = api.post(f'/v1/properties/{property_id}/evidence', headers=headers, json={
        'assertion_type': 'review', 'assertion_text': 'looks consistent with the packet', 'source_kind': 'professional_review', 'source_reference': 'reviewer note, not a licence'})
    assert noted.status_code == 201, noted.text
    assert noted.json()['review_status'] == 'recorded'


def test_runtime_cannot_rewrite_identifier_or_insert_official_observation(api):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    created = api.post(f'/v1/properties/{property_id}/identifiers', headers=headers, json={'scheme': 'survey_number', 'identifier_value': '1'})
    assert created.status_code == 201, created.text
    def runtime():
        conn = psycopg.connect(make_conninfo(DSN, user='oydp_app', password=PASSWORD))
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        conn.execute("SELECT set_config('app.subject_id', 'lineage-alice', true)")
        return conn
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime() as conn:
        conn.execute("UPDATE property_identifiers SET identifier_value='stolen' WHERE id=%s", (created.json()['id'],))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime() as conn:
        conn.execute("""INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind,source_reference,review_status)
          VALUES (%s,%s,'title','official','official_observation','portal','unreviewed')""", (tenant, property_id))


def test_bad_source_link_and_audit_failure_roll_back(api):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    missing = api.post(f'/v1/properties/{property_id}/evidence', headers=headers, json={
        'assertion_type': 'note', 'assertion_text': 'text', 'source_kind': 'user_claim', 'source_id': str(uuid4())})
    assert missing.status_code == 422
    with psycopg.connect(DSN) as conn:
        conn.execute("REVOKE INSERT ON property_audit_events FROM oydp_app")
    try:
        denied = api.post(f'/v1/properties/{property_id}/sources', headers=headers, json={'name': 'lost', 'source_class': 'user_supplied'})
        assert denied.status_code == 503
        page = api.get(f'/v1/properties/{property_id}/sources', headers=headers)
        assert page.status_code == 200 and page.json()['items'] == []
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('GRANT INSERT ON property_audit_events TO oydp_app')
