from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from oydp.auth import TokenVerifier
from oydp.api import create_app
from oydp.repository import Unavailable

ISSUER = 'https://identity.example.test'
AUDIENCE = 'oydp-api'

@pytest.fixture(scope='session')
def keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return key, public


def token(keys, subject=None, **overrides):
    now = datetime.now(timezone.utc)
    claims = dict(sub=str(subject or uuid4()), iss=ISSUER, aud=AUDIENCE,
                  iat=now, exp=now+timedelta(minutes=5), amr=['mfa'])
    claims.update(overrides)
    return jwt.encode(claims, keys[0], algorithm='RS256')


def verifier(keys):
    return TokenVerifier(keys[1], ISSUER, AUDIENCE)


def test_signature_and_subject(keys):
    subject = uuid4()
    result = verifier(keys).verify(token(keys, subject))
    assert result.subject == subject and result.mfa


@pytest.mark.parametrize('overrides', [
    {'iss':'https://wrong.example.test'}, {'aud':'wrong'}, {'sub':'invalid'},
    {'exp':0}, {'iat':datetime.now(timezone.utc)+timedelta(hours=1)},
    {'amr':'mfa'}, {'amr':[True]},
])
def test_invalid_tokens_rejected(keys, overrides):
    with pytest.raises((ValueError, jwt.PyJWTError)):
        verifier(keys).verify(token(keys, **overrides))


def test_wrong_key_rejected(keys):
    wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.InvalidSignatureError):
        verifier(keys).verify(token((wrong, keys[1])))


def test_algorithm_confusion_rejected(keys):
    bad = jwt.encode({'sub':str(uuid4())}, 'x'*64, algorithm='HS256')
    with pytest.raises(jwt.InvalidAlgorithmError):
        verifier(keys).verify(bad)


class NeverRepository:
    def __getattr__(self, name):
        raise AssertionError('Unauthorized request reached persistence')


@pytest.fixture
def client(keys):
    return TestClient(create_app(NeverRepository(), verifier(keys)))


def headers(keys, **overrides):
    return {'Authorization':'Bearer '+token(keys, **overrides), 'X-Tenant-ID':str(uuid4())}


def test_missing_auth(client):
    assert client.get('/v1/properties').status_code == 401


def test_forged_auth(client):
    assert client.get('/v1/properties',headers={'Authorization':'Bearer fake'}).status_code == 401


def test_mfa_gate(client, keys):
    r = client.post('/v1/properties',headers=headers(keys, amr=[]),json={'name':'Candidate'})
    assert r.status_code == 403


@pytest.mark.parametrize('body', [{'name':' '}, {'name':'a','tenant_id':str(uuid4())},
    {'name':'a','verified':True}, {'name':'a'*201}, {'name':'a','jurisdiction':''}])
def test_input_boundaries(client, keys, body):
    r=client.post('/v1/properties',headers=headers(keys),json=body)
    assert r.status_code == 422 and r.json() == {'detail':'Invalid request'}


def test_claim_cannot_be_promoted(client, keys):
    r=client.post(f'/v1/properties/{uuid4()}/claims',headers=headers(keys),
                  json={'statement':'Private text','kind':'official_verified'})
    assert r.status_code == 422 and 'Private text' not in r.text


@pytest.mark.parametrize('query', ['limit=101','limit=0','offset=-1','offset=10001'])
def test_bounded_pagination(client, keys, query):
    assert client.get('/v1/properties?'+query, headers=headers(keys)).status_code == 422


def test_private_response_headers(client):
    r=client.get('/v1/properties')
    assert r.headers['cache-control']=='no-store'
    assert r.headers['x-content-type-options']=='nosniff'


def test_openapi_contract(client):
    spec=client.get('/openapi.json').json()
    assert '/v1/properties/{property_id}/claims' in spec['paths']
    assert spec['components']['schemas']['PropertyInput']['additionalProperties'] is False
    assert client.get('/docs').status_code == 404


def test_missing_and_denied_same_response(keys):
    class Denied:
        def get(self,*args): raise Unavailable()
    c=TestClient(create_app(Denied(),verifier(keys)))
    assert c.get('/v1/properties/'+str(uuid4()),headers=headers(keys)).json()=={'detail':'Resource unavailable'}


@pytest.mark.parametrize('method',['put','delete'])
def test_access_requires_mfa(client,keys,method):
    kwargs={'headers':headers(keys,amr=[])}
    if method=='put':
        kwargs['json']={'actions':['property:read'],'expires_at':'2026-10-24T00:00:00Z'}
    assert getattr(client,method)(f'/v1/properties/{uuid4()}/access/{uuid4()}',**kwargs).status_code==403


@pytest.mark.parametrize('body',[
    {'actions':['admin'],'expires_at':'2026-10-24T00:00:00Z'},
    {'actions':[],'expires_at':'2026-10-24T00:00:00Z'},
    {'actions':['property:read'],'expires_at':'2026-10-24T00:00:00'},
    {'actions':['property:read'],'expires_at':'2026-10-24T00:00:00Z','verified':True},
])
def test_access_input_rejected(client,keys,body):
    r=client.put(f'/v1/properties/{uuid4()}/access/{uuid4()}',headers=headers(keys),json=body)
    assert r.status_code==422
