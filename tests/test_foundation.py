import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from oydp.policy import Action, Grant, Principal, Resource, ScanState, authorize
from oydp.provenance import Assertion, EvidenceKind


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        self.p = Principal(uuid4(), uuid4(), True, True)
        self.r = Resource(uuid4(), self.p.tenant, uuid4(), ScanState.PASS)
        self.g = Grant(self.p.subject, self.p.tenant, self.r.property_id,
                       frozenset(Action), self.now + timedelta(hours=1), resource_id=self.r.id)

    def allowed(self, **changes):
        args = dict(principal=self.p, resource=self.r, action=Action.READ,
                    grants=(self.g,), now=self.now)
        args.update(changes)
        return authorize(**args)

    def test_explicit_grant_allows_actions(self):
        for action in Action:
            with self.subTest(action=action):
                self.assertTrue(self.allowed(action=action))

    def test_no_grant_denied(self):
        self.assertFalse(self.allowed(grants=()))

    def test_cross_tenant_denied(self):
        self.assertFalse(self.allowed(resource=replace(self.r, tenant=uuid4())))

    def test_wrong_subject_property_tenant_and_document_denied(self):
        for field in ('subject', 'property_id', 'tenant', 'resource_id'):
            with self.subTest(field=field):
                self.assertFalse(self.allowed(grants=(replace(self.g, **{field: uuid4()}),)))

    def test_revocation_takes_effect(self):
        self.assertTrue(self.allowed())
        self.assertFalse(self.allowed(grants=(replace(self.g, revoked=True),)))

    def test_expiry_boundary_denied(self):
        self.assertFalse(self.allowed(grants=(replace(self.g, expires_at=self.now),)))

    def test_inactive_membership_denied(self):
        self.assertFalse(self.allowed(principal=replace(self.p, active=False)))

    def test_mfa_required_for_sensitive_actions(self):
        for action in (Action.WRITE, Action.DOWNLOAD):
            self.assertFalse(self.allowed(action=action, principal=replace(self.p, mfa=False)))
        self.assertTrue(self.allowed(principal=replace(self.p, mfa=False)))

    def test_download_scan_gate(self):
        for state in (ScanState.QUARANTINED, ScanState.FAIL):
            self.assertFalse(self.allowed(action=Action.DOWNLOAD, resource=replace(self.r, scan_state=state)))

    def test_property_grant_cannot_download_document(self):
        self.assertFalse(self.allowed(action=Action.DOWNLOAD, grants=(replace(self.g, resource_id=None),)))

    def test_action_not_granted_denied(self):
        self.assertFalse(self.allowed(action=Action.WRITE, grants=(replace(self.g, actions=frozenset({Action.READ})),)))

    def test_naive_times_fail_closed(self):
        self.assertFalse(self.allowed(now=self.now.replace(tzinfo=None)))
        self.assertFalse(self.allowed(grants=(replace(self.g, expires_at=self.now.replace(tzinfo=None)),)))

    def test_unknown_action_denied(self):
        self.assertFalse(self.allowed(action='admin:all'))


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        self.a = Assertion(uuid4(), uuid4(), uuid4(), EvidenceKind.USER_CLAIM,
                           'Applicant claims ownership; unverified.', 'KA-unresolved', self.now)

    def test_claim_stays_claim(self):
        self.assertEqual(self.a.kind, EvidenceKind.USER_CLAIM)
        self.assertIsNone(self.a.source_reference)

    def test_observation_requires_source_and_date(self):
        with self.assertRaises(ValueError):
            replace(self.a, kind=EvidenceKind.OBSERVATION)
        with self.assertRaises(ValueError):
            replace(self.a, kind=EvidenceKind.OBSERVATION, source_reference='source-1')
        self.assertEqual(replace(self.a, kind=EvidenceKind.OBSERVATION,
                         source_reference='source-1', observed_at=self.now).kind, EvidenceKind.OBSERVATION)

    def test_review_requires_reviewer(self):
        with self.assertRaises(ValueError):
            replace(self.a, kind=EvidenceKind.PROFESSIONAL_REVIEW,
                    source_reference='source-1', observed_at=self.now)

    def test_unknown_preserved(self):
        self.assertEqual(replace(self.a, kind=EvidenceKind.UNKNOWN).kind, EvidenceKind.UNKNOWN)

    def test_invalid_inputs(self):
        for changes in ({'statement': ' '}, {'jurisdiction': ''}, {'kind': 'verified'},
                        {'recorded_at': self.now.replace(tzinfo=None)},
                        {'observed_at': self.now + timedelta(days=1)},
                        {'statement': 'a' * 10001}):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                replace(self.a, **changes)


if __name__ == '__main__':
    unittest.main()
