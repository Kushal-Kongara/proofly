"""Shared enums and building blocks used across data contracts."""

from enum import Enum


class VerificationStatus(str, Enum):
    """User's review status for an AI-derived fact."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DocumentType(str, Enum):
    I20 = "i20"
    I94 = "i94"
    EAD = "ead"
    F1_APPROVAL = "f1_approval"
    VISA_STAMP = "visa_stamp"
    RESUME = "resume"
    EMPLOYMENT_LETTER = "employment_letter"
    AWARD = "award"
    JUDGING_INVITATION = "judging_invitation"
    OTHER = "other"


class ImmigrationStatusType(str, Enum):
    """Immigration classification only — NOT a period of employment authorization.

    OPT and STEM OPT are periods of employment authorization held *under* an
    underlying classification (almost always F-1), not classifications of
    their own. Model those with EmploymentAuthorization instead.
    """

    F1 = "f1"
    H1B = "h1b"
    O1A = "o1a"
    OTHER = "other"


class EmploymentAuthorizationType(str, Enum):
    POST_COMPLETION_OPT = "post_completion_opt"
    STEM_OPT_EXTENSION = "stem_opt_extension"
    OTHER = "other"


class TimelineEventType(str, Enum):
    STATUS_START = "status_start"
    STATUS_END = "status_end"
    EMPLOYMENT_AUTH_START = "employment_auth_start"
    EMPLOYMENT_AUTH_END = "employment_auth_end"
    FILING_DEADLINE = "filing_deadline"
    DOCUMENT_EXPIRATION = "document_expiration"
    EMPLOYMENT_START = "employment_start"
    OTHER = "other"


class O1CriterionCode(str, Enum):
    """The eight regulatory criteria for O-1A extraordinary ability, 8 CFR 214.2(o)."""

    AWARDS = "awards"
    MEMBERSHIP = "membership"
    PUBLISHED_MATERIAL = "published_material"
    JUDGING = "judging"
    ORIGINAL_CONTRIBUTION = "original_contribution"
    SCHOLARLY_ARTICLES = "scholarly_articles"
    CRITICAL_EMPLOYMENT = "critical_employment"
    HIGH_REMUNERATION = "high_remuneration"
