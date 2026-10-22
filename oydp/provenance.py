"""Evidence assertions preserve uncertainty; no title certification."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class EvidenceKind(StrEnum):
    USER_CLAIM = 'user_claim'
    OBSERVATION = 'observation'
    PROFESSIONAL_REVIEW = 'professional_review'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class Assertion:
    id: UUID
    tenant_id: UUID
    property_id: UUID
    kind: EvidenceKind
    statement: str
    jurisdiction: str
    recorded_at: datetime
    source_reference: str | None = None
    observed_at: datetime | None = None
    reviewer_reference: str | None = None

    def __post_init__(self):
        if not isinstance(self.kind, EvidenceKind):
            raise ValueError('Invalid evidence kind')
        if not self.statement.strip() or not self.jurisdiction.strip():
            raise ValueError('Statement and jurisdiction required')
        if len(self.statement) > 10000 or len(self.jurisdiction) > 200:
            raise ValueError('Input exceeds limit')
        for stamp in (self.recorded_at, self.observed_at):
            if stamp is not None and (stamp.tzinfo is None or stamp.utcoffset() is None):
                raise ValueError('Timestamps must include timezone')
        if self.kind in (EvidenceKind.OBSERVATION, EvidenceKind.PROFESSIONAL_REVIEW):
            if not self.source_reference or not self.source_reference.strip():
                raise ValueError('Source reference required')
            if self.observed_at is None:
                raise ValueError('Observation date required')
        if self.kind == EvidenceKind.PROFESSIONAL_REVIEW:
            if not self.reviewer_reference or not self.reviewer_reference.strip():
                raise ValueError('Attributable reviewer required')
        if self.observed_at is not None and self.observed_at > self.recorded_at:
            raise ValueError('Observation cannot postdate recording')
