# Private documents — API 0.6.0+

Canonical document storage is migration `010_document_quarantine.sql` plus `apps/api/app/documents.py`. The parallel branch's `009_private_documents.sql` was not added; those version numbers and table names already belong to other canonical migrations.

## Gate and storage

- Upload body is raw bytes. Declared `Content-Length` and actual size are capped at **1 MiB** (`MAX_UPLOAD_BYTES`).
- Magic bytes must be PDF, PNG, or JPEG. Type mismatch, empty body, or oversize returns 4xx and stores nothing.
- Accepted bytes are sealed with AES-GCM. The key is `DOCUMENT_STORAGE_KEY` (32-byte urlsafe-base64). Missing or invalid key fails closed.
- Rows start at `scan_state=quarantined`. Ciphertext is never selected through ordinary SELECT grants to `oydp_app`.

## Scanner

`get_document_scanner()` currently returns `None`. An absent, failing, or unexpected scanner cannot mark a document `pass`. The scan endpoint and `record_document_scan` stay fail-closed. There is no bundled antivirus product and no environment flag that fakes a clean scan.

Download (`GET .../content`) is allowed only when `scan_state == 'pass'`. A read grant does not release ciphertext. Until a real scanner adapter is configured, uploads remain quarantined.

## Rollback

No down migration. Preserve document rows and ciphertext. Re-provision the runtime role so it can select metadata columns, insert quarantine rows, and execute the document SECURITY DEFINER helpers, and cannot update scan state except through those helpers.
