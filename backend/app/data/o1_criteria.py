"""Static, version-controlled O-1A evidence criteria (8 CFR 214.2(o)(3)(iii)
and the USCIS Policy Manual, Volume 2, Part M, Chapter 4).

This is application data, not model output — `app/services/o1_assessment.py`
sources criterion names/descriptions from here exclusively, so a Featherless
response can never replace or reword an official criterion definition.
Update `O1_CRITERIA_LAST_REVIEWED` whenever this file is edited so the
frontend/README can show reviewers how fresh the static text is.
"""

from __future__ import annotations

from datetime import date

from app.schemas.common import O1CriterionCode
from app.schemas.o1_assessment import O1CriterionDefinition, O1InformationalCategory

O1_CRITERIA_LAST_REVIEWED = date(2026, 8, 15)

O1_OFFICIAL_SOURCES: list[str] = [
    "https://www.uscis.gov/working-in-the-united-states/temporary-workers/o-1-visa-individuals-with-extraordinary-ability-or-achievement",
    "https://www.uscis.gov/policy-manual/volume-2-part-m-chapter-4",
]

O1_CRITERIA: list[O1CriterionDefinition] = [
    O1CriterionDefinition(
        code=O1CriterionCode.AWARDS,
        name="Awards",
        regulatory_description=(
            "Evidence of receipt of nationally or internationally recognized prizes or "
            "awards for excellence in the field of endeavor."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.MEMBERSHIP,
        name="Membership",
        regulatory_description=(
            "Evidence of membership in associations in the field which require outstanding "
            "achievement of their members, as judged by recognized national or international "
            "experts."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.PUBLISHED_MATERIAL,
        name="Published material",
        regulatory_description=(
            "Evidence of published material in professional or major trade publications or "
            "major media about the beneficiary, relating to the beneficiary's work in the field."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.JUDGING,
        name="Judging",
        regulatory_description=(
            "Evidence of participation, either individually or on a panel, as a judge of the "
            "work of others in the same or an allied field of specialization."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.ORIGINAL_CONTRIBUTION,
        name="Original contributions",
        regulatory_description=(
            "Evidence of the beneficiary's original scientific, scholarly, or business-related "
            "contributions of major significance in the field."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.SCHOLARLY_ARTICLES,
        name="Scholarly authorship",
        regulatory_description=(
            "Evidence of the beneficiary's authorship of scholarly articles in professional "
            "journals or other major media in the field."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.CRITICAL_EMPLOYMENT,
        name="Critical role",
        regulatory_description=(
            "Evidence of employment in a critical or essential capacity for an organization or "
            "establishment that has a distinguished reputation."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
    O1CriterionDefinition(
        code=O1CriterionCode.HIGH_REMUNERATION,
        name="High remuneration",
        regulatory_description=(
            "Evidence that the beneficiary has commanded, or will command, a high salary or "
            "other significantly high remuneration in relation to others in the field."
        ),
        official_sources=O1_OFFICIAL_SOURCES,
    ),
]

O1_CRITERIA_BY_CODE: dict[O1CriterionCode, O1CriterionDefinition] = {c.code: c for c in O1_CRITERIA}

O1_ONE_TIME_ACHIEVEMENT = O1InformationalCategory(
    name="One-time major internationally recognized achievement",
    description=(
        "A beneficiary who has received a major, internationally recognized award (comparable "
        "to a Nobel Prize) may qualify without meeting the eight-criteria framework above. This "
        "is informational only — Proofly never infers a one-time major achievement from an "
        "ordinary award or recognition."
    ),
    official_sources=O1_OFFICIAL_SOURCES,
)

O1_COMPARABLE_EVIDENCE = O1InformationalCategory(
    name="Comparable evidence",
    description=(
        "If one of the eight standard criteria does not readily apply to the beneficiary's "
        "occupation, comparable evidence may be submitted to establish eligibility instead. "
        "This is informational only — identifying that comparable evidence may apply is not a "
        "determination that it does."
    ),
    official_sources=O1_OFFICIAL_SOURCES,
)

# Generic, criterion-appropriate suggestions used whenever the model doesn't
# supply (or only partially supplies) suggested evidence for a criterion.
# Static application data, not model output.
O1_DEFAULT_SUGGESTED_EVIDENCE: dict[O1CriterionCode, list[str]] = {
    O1CriterionCode.AWARDS: [
        "Award selection criteria or judging standards from the issuing organization",
        "Information describing the size/competitiveness of the applicant pool",
        "Independent media or industry coverage recognizing the award",
    ],
    O1CriterionCode.MEMBERSHIP: [
        "Membership organization's published admission criteria",
        "Documentation showing admission requires outstanding achievement judged by experts",
    ],
    O1CriterionCode.PUBLISHED_MATERIAL: [
        "Published articles or features that are about the beneficiary and their work",
        "Circulation/readership information for the publication or outlet",
    ],
    O1CriterionCode.JUDGING: [
        "Organizer confirmation of a completed judging role",
        "Completed scorecards or judging records (with sensitive information removed)",
        "Event program or records listing the judging role",
    ],
    O1CriterionCode.ORIGINAL_CONTRIBUTION: [
        "Evidence of independent adoption or use of the contribution",
        "Measurable impact data (citations, patents, revenue, customer use)",
        "Independent expert evaluation of the contribution's significance",
    ],
    O1CriterionCode.SCHOLARLY_ARTICLES: [
        "Copies of published scholarly articles with author byline",
        "Citation counts or other independent measures of scholarly impact",
    ],
    O1CriterionCode.CRITICAL_EMPLOYMENT: [
        "Documentation of the organization's distinguished reputation (awards, rankings, media)",
        "Organizational chart or role description showing the critical/essential nature of the position",
    ],
    O1CriterionCode.HIGH_REMUNERATION: [
        "Compensation documentation (offer letter, pay stubs, tax records)",
        "An appropriate salary comparison benchmark for the field and region",
    ],
}
