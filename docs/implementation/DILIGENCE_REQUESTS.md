# Diligence requests — API 0.8.0

Migration `014_diligence_requests.sql` adds workspace requests and notes. The text is untrusted. A request is not an offer, a payment, or a legal conclusion. `closed` only means the workspace status changed.

The creator with an owner or editor role and an MFA token can open and close a request. Anyone who can already read the property, including a current read grantee, can read requests and add a note while the request is open. A note on a closed or unknown request returns 404. Another tenant receives 404. Writes require MFA. Each change is audited in the same transaction.

No down migration is provided. Re-provision the runtime role for select/insert and for update of `status` and `closed_at` only.
