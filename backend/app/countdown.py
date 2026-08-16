"""Countdown helpers that keep the "days remaining" concept scoped to
concrete, dated things — employment authorization and visa stamps — and
deliberately unable to produce a number for a D/S immigration status, where
no such number exists.
"""

from datetime import date

from app.schemas.employment_authorization import EmploymentAuthorization
from app.schemas.immigration_status import ImmigrationStatus
from app.schemas.visa_stamp import VisaStamp


def days_until(target_date: date | None, reference_date: date) -> int | None:
    if target_date is None:
        return None
    return (target_date - reference_date).days


def authorized_stay_countdown_days(status: ImmigrationStatus, reference_date: date) -> int | None:
    """Days remaining in this immigration classification's authorized stay.

    Always None for a D/S admission ("duration of status") — there is no
    fixed end date to count down to, by design.
    """
    if status.duration_of_status:
        return None
    return days_until(status.end_date, reference_date)


def employment_authorization_countdown_days(
    authorization: EmploymentAuthorization, reference_date: date
) -> int:
    """Days remaining on an EAD. EAD end dates are always fixed, so this
    always returns a number.
    """
    return days_until(authorization.end_date, reference_date)  # type: ignore[return-value]


def visa_validity_countdown_days(visa: VisaStamp, reference_date: date) -> int:
    """Days until the visa stamp expires.

    A valid visa permits the holder to request admission at a U.S. port of
    entry; it does not guarantee admission or determine authorized stay.
    This figure must never be read as, or substituted for,
    authorized_stay_countdown_days.
    """
    return days_until(visa.expiration_date, reference_date)  # type: ignore[return-value]
