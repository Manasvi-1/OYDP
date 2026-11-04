# Private documents — API 0.6.0

The parallel branch's `009_private_documents.sql` was not added. `010_document_quarantine.sql` is the canonical document table. The notes below describe the branch that was merged for history. Accepted bytes are encrypted with AES-GCM and written under `DOCUMENT_STORAGE_DIR`. The key is `DOCUMENT_ENCRYPTION_KEY`, 32 bytes as hex. Both are required or uploads fail closed.

## Gate

The upload body is raw bytes with `Content-Length` at most 10 MiB. Magic bytes must be PDF, PNG, or JPEG. The EICAR test string and PDF markers `/JavaScript`, `/JS`, `/OpenAction`, `/Launch`, and `/EmbeddedFile` are rejected. This is a synchronous content gate, not a sandbox or an antivirus product. A production scanner is an owner decision.

Rejected type or active content is recorded as `status=rejected` with a code and no stored bytes. Empty or oversized bodies return 422 and are not recorded. Clean files can be downloaded only by the creator, after the ciphertext is decrypted and its SHA-256 matches the stored digest. A read grant does not grant the file. The download name is `document.pdf`, `document.png`, or `document.jpg`.

## Rollback

No down migration. Preserve document rows and any encrypted files. 0.5.0 application code does not serve these routes. Re-provision the runtime role so it can select and insert document rows and cannot update them.
