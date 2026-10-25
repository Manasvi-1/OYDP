"""PostgreSQL persistence; every operation owns a short, transaction-local context."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row


class Unavailable(Exception):
    """Missing or forbidden resource; intentionally indistinguishable."""


class InvalidAccess(Exception):
    """An access expiry or permission set is invalid."""


class Repository:
    def __init__(self, dsn):
        self.dsn = dsn

    @contextmanager
    def transaction(self, tenant, identity):
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            role = conn.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            if role['rolsuper'] or role['rolbypassrls']:
                raise RuntimeError('Runtime role must not bypass RLS')
            conn.execute("SELECT set_config('oydp.tenant_id',%s,true),set_config('oydp.subject_id',%s,true)",
                         (str(tenant), str(identity.subject)))
            member = conn.execute('SELECT active FROM oydp.memberships WHERE tenant_id=%s AND subject_id=%s FOR SHARE',
                                  (tenant, identity.subject)).fetchone()
            if not member or not member['active']:
                raise Unavailable()
            yield conn

    @staticmethod
    def check_grant(conn, tenant, subject, property_id, action):
        grant = conn.execute('''SELECT 1 FROM oydp.grants WHERE tenant_id=%s AND subject_id=%s
            AND property_id=%s AND action=%s AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE''',
            (tenant, subject, property_id, action)).fetchone()
        if not grant:
            raise Unavailable()

    @staticmethod
    def audit(conn, tenant, subject, property_id, event):
        conn.execute('INSERT INTO oydp.audit_outbox(tenant_id,id,property_id,actor_id,event_type) VALUES(%s,%s,%s,%s,%s)',
                     (tenant, uuid4(), property_id, subject, event))

    def create(self, tenant, identity, data):
        with self.transaction(tenant, identity) as conn:
            property_id = uuid4()
            result = conn.execute('''INSERT INTO oydp.properties(tenant_id,id,created_by,name,jurisdiction)
                VALUES(%s,%s,%s,%s,%s) RETURNING id,name,jurisdiction,created_at''',
                (tenant, property_id, identity.subject, data.name, data.jurisdiction)).fetchone()
            for action in ('property:read', 'property:write'):
                conn.execute('''INSERT INTO oydp.grants(tenant_id,property_id,subject_id,action,expires_at)
                    VALUES(%s,%s,%s,%s,%s)''', (tenant, property_id, identity.subject, action,
                                             datetime.now(timezone.utc) + timedelta(days=30)))
            self.audit(conn, tenant, identity.subject, property_id, 'property.created')
            return result

    def list(self, tenant, identity, limit, offset):
        with self.transaction(tenant, identity) as conn:
            return conn.execute('''SELECT p.id,p.name,p.jurisdiction,p.created_at FROM oydp.properties p
                WHERE p.tenant_id=%s AND EXISTS(SELECT 1 FROM oydp.grants g
                WHERE g.tenant_id=p.tenant_id AND g.property_id=p.id AND g.subject_id=%s
                AND g.action='property:read' AND NOT g.revoked AND g.expires_at>clock_timestamp())
                ORDER BY p.created_at DESC,p.id LIMIT %s OFFSET %s''',
                (tenant, identity.subject, limit, offset)).fetchall()

    def get(self, tenant, identity, property_id):
        with self.transaction(tenant, identity) as conn:
            self.check_grant(conn, tenant, identity.subject, property_id, 'property:read')
            result = conn.execute('SELECT id,name,jurisdiction,created_at FROM oydp.properties WHERE tenant_id=%s AND id=%s',
                                  (tenant, property_id)).fetchone()
            if not result:
                raise Unavailable()
            return result

    def claim(self, tenant, identity, property_id, data):
        with self.transaction(tenant, identity) as conn:
            self.check_grant(conn, tenant, identity.subject, property_id, 'property:write')
            result = conn.execute('''INSERT INTO oydp.claims(tenant_id,property_id,id,created_by,statement)
                VALUES(%s,%s,%s,%s,%s) RETURNING id,property_id,created_by,statement,kind,recorded_at''',
                (tenant, property_id, uuid4(), identity.subject, data.statement)).fetchone()
            self.audit(conn, tenant, identity.subject, property_id, 'claim.recorded')
            return result

    def access(self, tenant, identity, property_id, recipient, data=None):
        if not identity.mfa:
            raise Unavailable()
        try:
            with self.transaction(tenant, identity) as conn:
                result = conn.execute('SELECT oydp.set_property_access(%s,%s,%s,%s,%s) AS changed',
                    (tenant, property_id, recipient,
                     sorted(data.actions) if data else [], data.expires_at if data else None)).fetchone()
                return {'changed': result['changed']}
        except psycopg.errors.NoDataFound:
            raise Unavailable() from None
        except psycopg.errors.InvalidParameterValue:
            raise InvalidAccess() from None

    def claims(self, tenant, identity, property_id, limit, offset):
        with self.transaction(tenant, identity) as conn:
            self.check_grant(conn, tenant, identity.subject, property_id, 'property:read')
            return conn.execute('''SELECT id,property_id,created_by,statement,kind,recorded_at FROM oydp.claims
                WHERE tenant_id=%s AND property_id=%s ORDER BY recorded_at,id LIMIT %s OFFSET %s''',
                (tenant, property_id, limit, offset)).fetchall()
