from pydantic import BaseModel

from app.schemas.common import O1CriterionCode


class O1Criterion(BaseModel):
    """One of the eight regulatory O-1A criteria and the user's current standing against it."""

    id: str
    code: O1CriterionCode
    name: str
    description: str
    satisfied: bool = False
    evidence_item_ids: list[str] = []
