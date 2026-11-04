# Audit outbox — API 0.7.0

Migration `010_audit_outbox.sql` adds `audit_outbox` and a security-definer trigger. Every `property_audit_events` insert also inserts an outbox row in the same transaction. Existing events are backfilled. The runtime role can read the outbox through the property visibility policy and cannot update it.

`scripts/deliver_audit.py` reads undelivered rows with the migration connection and appends JSON lines containing the event id, tenant, property, event type, and time. It does not copy claim or document text. A second run does not emit a delivered row again. After `delivered_at` is set, the row cannot be changed. This sink is a local file, not an independent immutable archive.

`GET /v1/properties/{id}/audit` returns the same event fields to a member who can already read the property. `delivered_at` is null until the worker runs.

No down migration is provided. Preserve the outbox if application code moves back to 0.6.0. Re-provision the runtime role so it can execute the enqueue function.
