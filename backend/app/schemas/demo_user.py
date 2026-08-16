from datetime import date, datetime

from pydantic import BaseModel


class DemoUser(BaseModel):
    """A synthetic demo user. No authentication in the hackathon build."""

    id: str
    full_name: str
    email: str
    country_of_citizenship: str
    date_of_birth: date | None = None
    created_at: datetime
