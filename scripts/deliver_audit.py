"""Deliver undelivered audit-outbox rows to a local JSONL sink.

Uses the migration/owner connection. The sink receives identifiers and event
types only. Run it only against a database you operate. This does not create
an independent immutable archive.
"""
import json
import os

import psycopg
from psycopg.rows import dict_row


def deliver(dsn, sink, limit=100):
    if limit < 1 or limit > 5000:
        raise ValueError('Delivery batch must be between 1 and 5000')
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        rows = conn.execute("""SELECT id, event_id, tenant_id, property_id, event_type, created_at
          FROM public.audit_outbox WHERE delivered_at IS NULL
          ORDER BY created_at, id LIMIT %s FOR UPDATE SKIP LOCKED""", (limit,)).fetchall()
        with open(sink, 'a', encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps({
                    'event_id': str(row['event_id']),
                    'tenant_id': str(row['tenant_id']),
                    'property_id': str(row['property_id']),
                    'event_type': row['event_type'],
                    'created_at': row['created_at'].isoformat(),
                }, ensure_ascii=True) + '\n')
        if rows:
            conn.execute("""UPDATE public.audit_outbox
              SET delivered_at=clock_timestamp(), attempt_count=attempt_count+1
              WHERE id = ANY(%s) AND delivered_at IS NULL""", ([row['id'] for row in rows],))
        return len(rows)


if __name__ == '__main__':
    count = deliver(os.environ['MIGRATION_DATABASE_URL'], os.environ['AUDIT_SINK_PATH'], int(os.environ.get('AUDIT_DELIVER_LIMIT', '100')))
    print(f'delivered {count}')
